"""Command-line interface."""

import sys
import datetime
import subprocess
import os

import click
from loguru import logger

from flask import Flask, render_template, redirect, url_for, request
from werkzeug.wrappers.response import Response

# shared imports
import shared.constants as con
from shared.models import State, CameraAngle
import rift_console.drsApi as drsApi
import rift_console.RiftTelemetry
import rift_console.image_processing

# TODO-s
# - Autorefresh (maybe javascript)
# - Map schöner machen
# - Elemente kleiner machen
# - restliche API endpoints


##### LOGGING #####
logger.remove()
logger.add(sink=sys.stderr, level=con.RIFT_LOG_LEVEL, backtrace=True, diagnose=True)
logger.add(
    sink=con.RIFT_LOG_LOCATION,
    rotation="00:00",
    level="DEBUG",
    backtrace=True,
    diagnose=True,
)


app = Flask(__name__)
melvin = rift_console.RiftTelemetry.RiftTelemetry()


# Main Page
@app.route("/", methods=["GET"])
def index() -> str:
    # when refreshing pull updated telemetry
    drsApi.update_telemetry(melvin)

    return render_template(
        "console.html",
        width_x=melvin.width_x,
        height_y=melvin.height_y,
        battery=melvin.battery,
        max_battery=melvin.max_battery,
        fuel=melvin.fuel,
        vx=melvin.vx,
        vy=melvin.vy,
        target_vx=melvin.target_vx,
        target_vy=melvin.target_vy,
        angle=melvin.angle,
        simulation_speed=melvin.simulation_speed,
        is_network_simulated=melvin.is_network_simulation_active,
        timestamp=melvin.timestamp.strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        ),  # timezone doesnt change, so it can be exclude from output
        timedelta=(
            datetime.datetime.now(datetime.timezone.utc) - melvin.timestamp
        ).total_seconds(),
        new_image_folder_name=melvin.new_image_folder_name,
        old_x=melvin.old_pos[0],
        old_y=melvin.old_pos[1],
        older_x=melvin.older_pos[0],
        older_y=melvin.older_pos[1],
        oldest_x=melvin.oldest_pos[0],
        oldest_y=melvin.oldest_pos[1],
        state=melvin.state,
        pre_transition_state=melvin.pre_transition_state,
        planed_transition_state=melvin.planed_transition_state,
        last_backup_time=melvin.last_backup_time,
    )


"""
# TODO need help, to autorefresh
# ja das mit dem Threading ist irgendwie doch nicht so einfach :P
def call_telemetry() -> None:
    while True:
        print("Updating Telemtry")

        # TODO use javascript for autorefresh, add a alive light or something to show when connection failed
        drsApi.update_telemetry(melvin)
        time.sleep(3)
"""


# Wrapper for all Image Stichting and Copying
@app.route("/image_stitch_button", methods=["POST"])
def image_stitch_button() -> Response:
    # USES LOKAL PATHS
    user_input = request.form.get("source_location")
    source_path = con.IMAGE_PATH + user_input + "/"
    result_path = con.PANORAMA_PATH + user_input

    logger.info(f"TRY Stiched Image from {source_path} into {result_path}")

    rift_console.image_processing.automated_processing(
        image_path=source_path, output_path=result_path
    )

    logger.info(f"Stiched Image from {source_path} into {result_path}")

    # afterwards refresh page (which includes updating telemetry)
    return redirect(url_for("index"))


# Wrapper for all Image Stichting and Copying
@app.route("/image_pull_button", methods=["POST"])
def image_pull_button() -> Response:
    user_input = request.form.get("target_location")
    dir_path = con.IMAGE_PATH + user_input

    try:
        subprocess.run(["mkdir", dir_path], check=True)
        logger.info(f"image_manip_active created folder: {dir_path}")

    except subprocess.CalledProcessError as e:
        logger.warning(f"image_manip_buttons could not mkdir: {e}")

    # make sure an ssh config for "console" exists
    try:
        subprocess.run(
            ["scp", "console:/shared/CIARC/logs/melvonaut/images/*.png", dir_path],
            check=True,
        )
        logger.info(f"image_manip_active copied to: {dir_path}")

    except subprocess.CalledProcessError as e:
        logger.warning(f"image_manip_buttons scp failed: {e}")

    entries = os.listdir(dir_path)

    # Filter out directories and only count files
    file_count = sum(
        1 for entry in entries if os.path.isfile(os.path.join(dir_path, entry))
    )
    logger.info(f"Copied {file_count} Images")

    melvin.nextStitch_folder_name(user_input)

    # afterwards refresh page (which includes updating telemetry)
    return redirect(url_for("index"))


# Wrapper for all Simulation Manipulation buttons
@app.route("/sim_manip_buttons", methods=["POST"])
def sim_manip_buttons() -> Response:
    # read which button was pressed
    button = request.form.get("button", type=str)
    match button:
        case "refresh":
            pass
        case "reset":
            drsApi.reset(melvin)
        case "save":
            drsApi.save_backup(melvin)
        case "load":
            drsApi.load_backup()

    # afterwards refresh page (which includes updating telemetry)
    return redirect(url_for("index"))


# Slider
@app.route("/slider", methods=["POST"])
def slider_button() -> Response:
    slider_value = request.form.get("speed", default=20, type=int)
    is_network_simulation = "enableSim" in request.form

    drsApi.change_simulation_speed(
        melvin=melvin,
        is_network_simulation=is_network_simulation,
        user_speed_multiplier=slider_value,
    )

    return redirect(url_for("index"))


# State Changer
@app.route("/state_changer", methods=["POST"])
def state_buttons() -> Response:
    state = request.form.get("state", default=State.Unknown, type=State)

    lens = melvin.angle
    vx = melvin.vx
    vy = melvin.vy

    # noch nicht so happy mit dem if here TODO
    if melvin.state == State.Acquisition and state == State.Acquisition:
        lens = CameraAngle(request.form["options"])
        vx = request.form.get("vx", default=3, type=int)
        vy = request.form.get("vy", default=3, type=int)
        melvin.target_vx = vx
        melvin.target_vy = vy
        logger.info(f"Used Control API to change: vx: {vx}, vy: {vy}, lens: {lens}")

    drsApi.control(
        melvin=melvin, vel_x=vx, vel_y=vy, cameraAngle=lens, target_state=State(state)
    )

    return redirect(url_for("index"))


@click.group()
@click.version_option()
def main() -> None:
    """Rift Console."""
    pass


@main.command()
def run_server() -> None:
    """Run the Flask development server on port 8000."""
    click.echo("Starting Flask development server on port 8000...")

    # thread = threading.Thread(target=call_telemetry)
    # thread.start()

    drsApi.update_telemetry(melvin)
    # used to disable network simulation at start time
    if melvin.is_network_simulation_active:
        drsApi.change_simulation_speed(
            melvin=melvin,
            is_network_simulation=False,
            user_speed_multiplier=melvin.simulation_speed,
        )

    app.run(port=8000, debug=True)


@main.command()
def cli_only() -> None:
    """Original Rift Console CLI command"""
    click.echo("Rift Console CLI.")


if __name__ == "__main__":
    main(prog_name="Rift Console")  # pragma: no cover

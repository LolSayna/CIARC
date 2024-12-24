"""Command-line interface."""

import sys
import datetime
import subprocess
import os
import random

import click
from loguru import logger

from quart import Quart, render_template, redirect, url_for, request, jsonify
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


app = Quart(__name__)
melvin = rift_console.RiftTelemetry.RiftTelemetry()


# Main Page
@app.route("/", methods=["GET"])
async def index() -> str:
    # when refreshing pull updated telemetry
    drsApi.update_telemetry(melvin)

    if melvin.timestamp is not None:
        formatted_timestamp = str(
            melvin.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")
        )  # timezone doesnt change, so it can be exclude from output

        formatted_timedelta = str(
            (
                datetime.datetime.now(datetime.timezone.utc) - melvin.timestamp
            ).total_seconds()
        )

        formatted_last_backup_time = str(melvin.timestamp.strftime("%H:%M"))
    else:
        formatted_timestamp = "No timestamp available"
        formatted_timedelta = "No timestamp available"
        formatted_last_backup_time = "Unkown"

    return await render_template(
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
        timestamp=formatted_timestamp,
        timedelta=formatted_timedelta,
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
        last_backup_time=formatted_last_backup_time,
        z_obj_list=melvin.z_obj_list
    )

@app.route('/update')
def update():
    # This function will return a new random number for demonstration purposes.
    new_number = random.randint(0, 100)
    return jsonify({'number': new_number})


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



@app.route('/media')
async def media():
    # List of image filenames you want to display
    images = [
        'media/phase1.png',
        'media/phase2_part.png',
        'media/phase2_done_v1.png'
    ]
    return await render_template('media.html', images=images)


# TODO add better file handling structures, auto enter last copyed file name into stitching

# Wrapper for all Image Stichting and Copying
@app.route("/image_stitch_button", methods=["POST"])
async def image_stitch_button() -> Response:
    # USES LOKAL PATHS
    form = await request.form
    user_input = form.get("source_location")
    source_path = con.IMAGE_PATH + str(user_input)

    # logging inside image_processing
    rift_console.image_processing.automated_processing(
        image_path=source_path
    )
    # logging inside image_processing

    # afterwards refresh page (which includes updating telemetry)
    return redirect(url_for("index"))


# Wrapper for all Image Stichting and Copying
@app.route("/image_pull_button", methods=["POST"])
async def image_pull_button() -> Response:
    form = await request.form
    user_input = form.get("target_location")
    dir_path = con.IMAGE_PATH + str(user_input)

    try:
        subprocess.run(["mkdir", dir_path], check=True)
        logger.debug(f"image_manip_active created folder: {dir_path}")

    except subprocess.CalledProcessError as e:
        logger.warning(f"image_manip_buttons could not mkdir: {e}")

    # make sure an ssh config for "console" exists
    try:
        subprocess.run(
            ["scp", "console:/shared/CIARC/logs/melvonaut/images/*.png", dir_path],
            check=True,
        )
        logger.debug(f"image_manip_active copied to: {dir_path}")

    except subprocess.CalledProcessError as e:
        logger.warning(f"image_manip_buttons scp failed: {e}")

    entries = os.listdir(dir_path)

    # Filter out directories and only count files
    file_count = sum(
        1 for entry in entries if os.path.isfile(os.path.join(dir_path, entry))
    )
    logger.warning(f"Copied {file_count} Images from console.")

    # afterwards refresh page (which includes updating telemetry)
    return redirect(url_for("index"))


# Wrapper for all Simulation Manipulation buttons
@app.route("/sim_manip_buttons", methods=["POST"])
async def sim_manip_buttons() -> Response:
    # read which button was pressed
    form = await request.form
    button = form.get("button", type=str)
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
@app.route("/slider_button", methods=["POST"])
async def slider_button() -> Response:
    form = await request.form
    slider_value = form.get("speed", default=20, type=int)
    is_network_simulation = "enableSim" in form

    drsApi.change_simulation_speed(
        melvin=melvin,
        is_network_simulation=is_network_simulation,
        user_speed_multiplier=slider_value,
    )

    return redirect(url_for("index"))


# State Changer
@app.route("/state_changer", methods=["POST"])
async def state_buttons() -> Response:
    form = await request.form
    state = form.get("state", default=State.Unknown, type=State)

    lens = melvin.angle
    vx = melvin.vx
    vy = melvin.vy

    # noch nicht so happy mit dem if here TODO
    if melvin.state == State.Acquisition and state == State.Acquisition:
        lens = CameraAngle(str(form.get("options")))
        vx = form.get("vx", default=3, type=int)
        vy = form.get("vy", default=3, type=int)
        melvin.target_vx = vx
        melvin.target_vy = vy

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
    click.echo("Starting Quart development server on port 8000...")

    # thread = threading.Thread(target=call_telemetry)
    # thread.start()

    drsApi.update_telemetry(melvin)
    click.echo("Updated Telemetry")
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

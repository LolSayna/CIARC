"""Command-line interface."""

import sys
import datetime
import subprocess
import os

import click
from loguru import logger

from quart import Quart, render_template, redirect, url_for, request, flash
from werkzeug.wrappers.response import Response

# shared imports
import rift_console.rift_console
import shared.constants as con
from shared.models import State, CameraAngle, lens_size_by_angle
import rift_console.drsApi as drsApi
import rift_console.rift_telemetry
import rift_console.image_processing
import rift_console.ciarc_api as ciarc_api

# TODO-s
# - Autorefresh (maybe javascript)
# - Map schöner machen
# - Elemente kleiner machen
# - restliche API endpoints


##### LOGGING #####
con.RIFT_LOG_LEVEL = "INFO"
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
app.secret_key = "yoursecret_key" 
melvin = rift_console.rift_telemetry.RiftTelemetry()
console = rift_console.rift_console.RiftConsole()


@app.route("/main", methods=["GET"])
async def new_index():
    if console.live_telemetry:
        return await render_template(
            "main.html",
            last_backup_date=console.last_backup_date,
            is_network_simulation=console.is_network_simulation,
            user_speed_multiplier=console.user_speed_multiplier,
            timestamp=console.live_telemetry.timestamp.isoformat(),
            state=console.live_telemetry.state,
            angle=console.live_telemetry.angle,
            width_x=console.live_telemetry.width_x,
            height_y=console.live_telemetry.height_y,
            vx=console.live_telemetry.vx,
            vy=console.live_telemetry.vy,
            fuel=console.live_telemetry.fuel,
            battery=console.live_telemetry.battery,
            max_battery=console.live_telemetry.max_battery,
            distance_covered=console.live_telemetry.distance_covered,
            area_covered_narrow=console.live_telemetry.area_covered.narrow,
            area_covered_normal=console.live_telemetry.area_covered.normal,
            area_covered_wide=console.live_telemetry.area_covered.wide,
            active_time=console.live_telemetry.active_time,
            images_taken=console.live_telemetry.images_taken,
            objectives_done=console.live_telemetry.objectives_done,
            objectives_points=console.live_telemetry.objectives_points,
            data_volume_sent=console.live_telemetry.data_volume.data_volume_sent,
            data_volume_received=console.live_telemetry.data_volume.data_volume_received,
            prev_state=console.prev_state,  # keep track of history
            next_state=console.next_state,   # if in transition
            slots_used=console.slots_used,
            slots=console.slots
        )
    else:
        return await render_template(
            "main.html",
            last_backup_date=console.last_backup_date,
            is_network_simulation=console.is_network_simulation,
            user_speed_multiplier=console.user_speed_multiplier,
            prev_state=State.Unknown,
            next_state=State.Unknown,
            state=State.Unknown
        )


@app.route("/book_slot/<int:slot_id>", methods=["POST"])
async def book_slot(slot_id: int) -> Response:

    # read which button was pressed
    form = await request.form
    button = form.get("button", type=str)

    if button == "book":
        ciarc_api.book_slot(slot_id=slot_id, enabled=True)
    else:
        ciarc_api.book_slot(slot_id=slot_id, enabled=False)

    update_telemetry()

    return redirect(url_for("new_index"))

# Wrapper to change Melvin Status
@app.route("/satellite_handler", methods=["POST"])
async def satellite_handler() -> Response:
    global console

    # read which button was pressed
    form = await request.form
    button = form.get("button", type=str)

    # keep track of next and prev state
    old_state = State.Unknown
    if console.live_telemetry:
        old_state = console.live_telemetry.state

    match button:
        case "telemetry":
            pass
        case "acquisition":
            if ciarc_api.change_state(State.Acquisition):
                console.prev_state = old_state
                console.next_state = State.Acquisition
            else:
                await flash("Could not change State")
        case "charge":
            if ciarc_api.change_state(State.Charge):
                console.prev_state = old_state
                console.next_state = State.Charge
            else:
                await flash("Could not change State")
        case "communication":
            if ciarc_api.change_state(State.Communication):
                console.prev_state = old_state
                console.next_state = State.Communication
            else:
                await flash("Could not change State")
        case "narrow":
            if not ciarc_api.change_angle(CameraAngle.Narrow):
                await flash("Could not change Camera Angle")
        case "normal":
            if not ciarc_api.change_angle(CameraAngle.Normal):
                await flash("Could not change Camera Angle")
        case "wide":
            if not ciarc_api.change_angle(CameraAngle.Wide):
                await flash("Could not change Camera Angle")
        case "velocity":
            vel_x = form.get("vel_x", type=float)
            vel_y = form.get("vel_y", type=float)
            if not ciarc_api.change_velocity(vel_x=vel_x, vel_y=vel_y):
                await flash("Could not change Velocity")
        case _:
            logger.error(f"Unknown button pressed: {button}")
    
    update_telemetry()
    return redirect(url_for("new_index"))

# Wrapper for all Simulation Manipulation buttons
@app.route("/control_handler", methods=["POST"])
async def control_handler() -> Response:
    global console

    # read which button was pressed
    form = await request.form
    button = form.get("button", type=str)

    match button:
        case "reset":
            ciarc_api.reset()
            console = rift_console.rift_console.RiftConsole()
            new_tel = ciarc_api.live_observation()
            if new_tel:
                console.live_telemetry = new_tel
                console.user_speed_multiplier = new_tel.simulation_speed
        case "load":
            ciarc_api.load_backup(console.last_backup_date)
            console.live_telemetry = None
            new_tel = ciarc_api.live_observation()
            if new_tel:
                console.live_telemetry = new_tel
                console.user_speed_multiplier = new_tel.simulation_speed
        case "save":
            ciarc_api.save_backup()
            console.last_backup_date = ciarc_api.save_backup()
        case "on_sim":
            if console.user_speed_multiplier:
                ciarc_api.change_simulation_env(
                    is_network_simulation=True,
                    user_speed_multiplier=console.user_speed_multiplier,
                )
            else:
                ciarc_api.change_simulation_env(is_network_simulation=True)
                logger.warning("Reset simulation speed to 1.")
            console.is_network_simulation = True
        case "off_sim":
            if console.user_speed_multiplier:
                ciarc_api.change_simulation_env(
                    is_network_simulation=False,
                    user_speed_multiplier=console.user_speed_multiplier,
                )
            else:
                ciarc_api.change_simulation_env(is_network_simulation=False)
                logger.warning("Reset simulation speed to 1.")
            console.is_network_simulation = False
        case "sim_speed":
            speed = form.get("sim_speed", type=int)
            if console.is_network_simulation is not None:
                ciarc_api.change_simulation_env(
                    is_network_simulation=console.is_network_simulation,
                    user_speed_multiplier=speed,
                )
            else:
                ciarc_api.change_simulation_env(user_speed_multiplier=speed)
                logger.warning("Disabled network simulation.")
            console.user_speed_multiplier = speed
        case _:
            logger.error(f"Unknown button pressed: {button}")

    return redirect(url_for("new_index"))

# Pulls API after some changes
def update_telemetry():
    global console
    (new_tel, slots_used, slots) = ciarc_api.live_observation()
    if new_tel:
        console.live_telemetry = new_tel
        console.slots_used = slots_used
        console.slots = slots
        console.user_speed_multiplier = new_tel.simulation_speed

        if console.live_telemetry.state != State.Transition:
            console.next_state = State.Unknown



# OLD CODE!


# Main Page
@app.route("/", methods=["GET"])
async def index() -> str:
    # ciarc_api.load_backup(datetime.datetime.now())
    # ciarc_api.change_simulation_speed(user_speed_multiplier=5)
    # ciarc_api.set_network_sim(is_network_simulation=False)

    # when refreshing pull updated telemetry
    drsApi.update_telemetry(melvin)

    # ciarc_api.change_state(CameraAngle.Narrow)
    # ciarc_api.change_velocity(7.2,4.2)

    # TODO add check for if it worked
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

    lens_size = lens_size_by_angle(melvin.angle)

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
        state=melvin.state,
        pre_transition_state=melvin.pre_transition_state,
        planed_transition_state=melvin.planed_transition_state,
        last_backup_time=formatted_last_backup_time,
        z_obj_list=melvin.z_obj_list,
        drawnObjectives=melvin.drawnObjectives,
        scaledX=melvin.width_x / con.SCALING_FACTOR,
        scaledY=melvin.height_y / con.SCALING_FACTOR,
        scaledCameraZone=lens_size / con.SCALING_FACTOR,
        predTraj=[
            (int(x / con.SCALING_FACTOR), int(y / con.SCALING_FACTOR))
            for x, y in melvin.predTraj
        ],
        pastTraj=[
            (int(x / con.SCALING_FACTOR), int(y / con.SCALING_FACTOR))
            for x, y in melvin.pastTraj
        ],
    )


@app.route("/media")
async def media():
    # List of image filenames you want to display
    images = ["media/phase1.png", "media/phase2_part.png", "media/phase2_done_v1.png"]
    return await render_template("media.html", images=images)


# TODO add better file handling structures, auto enter last copyed file name into stitching


# Wrapper for all Image Stichting and Copying
@app.route("/image_stitch_button", methods=["POST"])
async def image_stitch_button() -> Response:
    # USES LOKAL PATHS
    form = await request.form
    user_input = form.get("source_location")
    source_path = con.IMAGE_PATH + str(user_input)

    # logging inside image_processing
    rift_console.image_processing.automated_stitching(local_path=source_path)
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

    """
    drsApi.change_simulation_speed(
        melvin=melvin,
        is_network_simulation=is_network_simulation,
        user_speed_multiplier=slider_value,
    )
    """
    ciarc_api.change_simulation_speed(user_speed_multiplier=slider_value)
    ciarc_api.change_network_sim(is_network_simulation=is_network_simulation)

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

    ciarc_api.live_observation()
    # ciarc_api.change_velocity(5.4,4.2)

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

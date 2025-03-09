"""Command-line interface."""

import sys
import datetime
import os

import click
from loguru import logger

from quart import Quart, render_template, redirect, url_for, request, flash
from werkzeug.wrappers.response import Response

# shared imports
import rift_console.rift_console
import shared.constants as con
from shared.models import State, CameraAngle, lens_size_by_angle, live_utc
import rift_console.image_processing
import rift_console.ciarc_api as ciarc_api

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
console = rift_console.rift_console.RiftConsole()


@app.route("/media")
async def media() -> str:
    # List of image filenames you want to display

    images = os.listdir("src/rift_console/static/media/")
    images = ["media/" + s for s in images]
    logger.warning(f"Showing images: {images}")
    return await render_template("media.html", images=images)


@app.route("/", methods=["GET"])
async def index() -> str:
    if console.live_telemetry:
        return await render_template(
            "main.html",
            last_backup_date=console.last_backup_date.isoformat()[:-13]
            if console.last_backup_date
            else "",
            is_network_simulation=console.is_network_simulation,
            user_speed_multiplier=console.user_speed_multiplier,
            # live telemtry
            timestamp=console.live_telemetry.timestamp.isoformat()[:-6],
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
            # keep track of state history
            prev_state=console.prev_state,
            next_state=console.next_state,
            slots_used=console.slots_used,
            # tables
            slots=console.slots,
            zoned_objectives=console.zoned_objectives,
            beacon_objectives=console.beacon_objectives,
            achievements=console.achievements,
            # slot times
            next_slot_start=console.slots[0].start.strftime("%H:%M:%S"),
            slot_ends=console.slots[0].end.strftime("%H:%M:%S"),
            # drawn map
            draw_zoned_obj=console.get_draw_zoned_obj(),
            camera_size=lens_size_by_angle(console.live_telemetry.angle),
            past_traj=console.past_traj,
            future_traj=console.future_traj,
        )
    else:
        return await render_template(
            "main.html",
            last_backup_date=console.last_backup_date,
            is_network_simulation=console.is_network_simulation,
            user_speed_multiplier=console.user_speed_multiplier,
            prev_state=State.Unknown,
            next_state=State.Unknown,
            state=State.Unknown,
            # need default to prevent crash
            draw_zoned_obj=[],
            past_traj=[],
            future_traj=[],
            width_x=0,
            height_y=0,
        )


# Upload world map/images/beacon position
@app.route("/results", methods=["POST"])
async def results() -> Response:
    # read which button was pressed
    form = await request.form
    button = form.get("button", type=str)

    match button:
        case "worldmap":
            image_path = form.get("path_world", type=str) or ""
            if not os.path.isfile(path=image_path):
                await flash(
                    f"Cant upload world map, file: {image_path} does not exist."
                )
                logger.warning(
                    f"Cant upload world map, file: {image_path} does not exist."
                )
                return redirect(url_for("index"))

            res = ciarc_api.upload_worldmap(image_path=image_path)

            if res:
                await flash(res)
                if res.startswith("Image uploaded successfully"):
                    await flash(
                        f"Worldmap - {image_path} - {live_utc().strftime("%d/%m/%Y")}."
                    )
                    logger.warning(
                        f"Worldmap uploaded - {image_path} - {live_utc().strftime("%d/%m/%Y")}."
                    )

        case "obj":
            image_path = form.get("path_obj", type=str) or ""
            id = form.get("objective_id", type=int) or 0

            if not os.path.isfile(image_path):
                await flash(
                    f"Cant upload objective {id}, file: {image_path} does not exist."
                )
                logger.warning(
                    f"Cant upload objective {id}, file: {image_path} does not exist."
                )
                return redirect(url_for("index"))

            res = ciarc_api.upload_objective(image_path=image_path, objective_id=id)

            if res:
                await flash(res)
                if res.startswith("Image uploaded successfully"):
                    await flash(f"Objective {id} - {image_path}")
                    logger.warning(f"Objective {id} uploaded - {image_path}")
            else:
                await flash(f"Could not upload objective {id} - {image_path}")

        case "beacon":
            id = form.get("beacon_id", type=int) or 0
            height = form.get("height", type=int) or 0
            width = form.get("width", type=int) or 0
            res = ciarc_api.send_beacon(
                beacon_id=id,
                height=height,
                width=width,
            )
            if res:
                status: str = res["status"]
                await flash(status)
                if status.startswith(
                    "The beacon could not be found around the given location"
                ):
                    await flash(
                        f"Attempts made: {res["attempts_made"]} of 3, Location was ({height},{width})"
                    )
                if status.startswith("No more rescue attempts left"):
                    await flash(f"for EBT: {id}")

        case _:
            logger.error(f"Unknown button pressed: {button}")

    update_telemetry()

    return redirect(url_for("index"))


# Add/Modify zoned_objectives
@app.route("/obj_mod", methods=["POST"])
async def obj_mod() -> Response:
    # read which button was pressed
    form = await request.form
    button = form.get("button", type=str)

    match button:
        case "zoned":
            secret = form.get("secret", type=str)
            if secret == "True":
                ciarc_api.add_modify_zoned_objective(
                    id=form.get("obj_id", type=int) or 0,
                    name=form.get("name", type=str) or "name",
                    start=datetime.datetime.fromisoformat(
                        form.get("start", type=str) or "2025-01-01T00:00"
                    ),
                    end=datetime.datetime.fromisoformat(
                        form.get("end", type=str) or "2025-01-01T00:00"
                    ),
                    optic_required=CameraAngle(
                        form.get("angle", type=str) or CameraAngle.Unknown
                    ),
                    secret=True,
                    zone=(0, 0, 0, 0),
                    coverage_required=form.get("coverage_required", type=float) or 0.99,
                    description=form.get("description", type=str) or "desc",
                )
            else:
                ciarc_api.add_modify_zoned_objective(
                    id=form.get("obj_id", type=int) or 0,
                    name=form.get("name", type=str) or "name",
                    start=datetime.datetime.fromisoformat(
                        form.get("start", type=str) or "2025-01-01T00:00"
                    ),
                    end=datetime.datetime.fromisoformat(
                        form.get("end", type=str) or "2025-01-01T00:00"
                    ),
                    optic_required=CameraAngle(
                        form.get("angle", type=str) or CameraAngle.Unknown
                    ),
                    secret=False,
                    zone=(
                        form.get("x1", type=int) or 0,
                        form.get("y1", type=int) or 0,
                        form.get("x2", type=int) or 0,
                        form.get("y2", type=int) or 0,
                    ),
                    coverage_required=form.get("coverage_required", type=float) or 0.99,
                    description=form.get("description", type=str) or "desc",
                )
        case "ebt":
            ciarc_api.add_modify_ebt_objective(
                id=form.get("obj_id", type=int) or 0,
                name=form.get("name", type=str) or "name",
                start=datetime.datetime.fromisoformat(
                    form.get("start_ebt", type=str) or "2025-01-01T00:00"
                ),
                end=datetime.datetime.fromisoformat(
                    form.get("end_ebt", type=str) or "2025-01-01T00:00"
                ),
                description=form.get("description", type=str) or "desc",
                beacon_height=form.get("beacon_height", type=int) or 0,
                beacon_width=form.get("beacon_width", type=int) or 0,
            )
        case _:
            logger.error(f"Unknown button pressed: {button}")

    update_telemetry()

    return redirect(url_for("index"))


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

    return redirect(url_for("index"))


@app.route("/del_obj/<int:obj_id>", methods=["POST"])
async def del_obj(obj_id: int) -> Response:
    ciarc_api.delete_objective(id=obj_id)
    update_telemetry()

    return redirect(url_for("index"))


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
            if vel_x and vel_y:
                if not ciarc_api.change_velocity(vel_x=vel_x, vel_y=vel_y):
                    await flash("Could not change Velocity")
            else:
                logger.warning("Cant change velocity since vel_x/vel_y not set!")

        case _:
            logger.error(f"Unknown button pressed: {button}")

    update_telemetry()
    return redirect(url_for("index"))


# Wrapper for all Simulation Manipulation buttons
@app.route("/control_handler", methods=["POST"])
async def control_handler() -> Response:
    global console

    # read which button was pressed
    form = await request.form
    button = form.get("button")

    match button:
        case "reset":
            ciarc_api.reset()
            console = rift_console.rift_console.RiftConsole()
        case "load":
            ciarc_api.load_backup(console.last_backup_date)
            console.live_telemetry = None
        case "save":
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
            if speed:
                if console.is_network_simulation is not None:
                    ciarc_api.change_simulation_env(
                        is_network_simulation=console.is_network_simulation,
                        user_speed_multiplier=speed,
                    )
                else:
                    ciarc_api.change_simulation_env(user_speed_multiplier=speed)
                    logger.warning("Disabled network simulation.")
                console.user_speed_multiplier = speed
            else:
                logger.warning("Cant change sim_speed since speed not set!")
        case _:
            logger.error(f"Unknown button pressed: {button}")

    update_telemetry()
    return redirect(url_for("index"))


# Pulls API after some changes
def update_telemetry() -> None:
    global console
    res = ciarc_api.live_observation()
    if res:
        (
            new_tel,
            slots_used,
            slots,
            zoned_objectives,
            beacon_objectives,
            achievements,
        ) = res
        console.live_telemetry = new_tel
        console.slots_used = slots_used
        console.slots = slots
        console.zoned_objectives = zoned_objectives
        console.beacon_objectives = beacon_objectives
        console.achievements = achievements
        console.user_speed_multiplier = new_tel.simulation_speed
        (console.past_traj, console.future_traj) = console.predict_trajektorie()

        if console.live_telemetry and console.live_telemetry.state != State.Transition:
            console.next_state = State.Unknown


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

    click.echo("Updated Telemetry")
    ciarc_api.live_observation()

    app.run(port=3000, debug=True, host="0.0.0.0")


@main.command()
def cli_only() -> None:
    """Original Rift Console CLI command"""
    click.echo("Rift Console CLI.")


if __name__ == "__main__":
    main(prog_name="Rift Console")  # pragma: no cover

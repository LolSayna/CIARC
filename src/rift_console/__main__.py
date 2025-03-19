"""Command-line interface."""

from pathlib import Path
import pathlib
import sys
import datetime
import os

import click
from loguru import logger

from quart import (
    Quart,
    render_template,
    redirect,
    send_from_directory,
    url_for,
    request,
    flash,
)
from werkzeug.wrappers.response import Response
from hypercorn.config import Config
import asyncio
from hypercorn.asyncio import serve

# shared imports
from rift_console.image_helper import get_angle, get_date
import rift_console.rift_console
import shared.constants as con
from shared.models import State, CameraAngle, lens_size_by_angle, live_utc
import rift_console.image_processing
import rift_console.ciarc_api as ciarc_api
import rift_console.melvin_api as melvin_api

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


@app.route(f"/{con.CONSOLE_LIVE_PATH}/<path:filename>")
async def uploaded_file_live(filename):  # type: ignore
    return await send_from_directory(con.CONSOLE_LIVE_PATH, filename)


@app.route(f"/{con.CONSOLE_DOWNLOAD_PATH}/<path:filename>")
async def uploaded_file_download(filename):  # type: ignore
    return await send_from_directory(con.CONSOLE_DOWNLOAD_PATH, filename)


@app.route("/stitches")
async def stitches() -> str:
    return await render_template("live.html")


def get_console_images() -> list[str]:
    # list all images
    images = os.listdir(con.CONSOLE_DOWNLOAD_PATH)
    # filter to only png
    images = [s for s in images if s.endswith(".png")]

    return images

@app.route("/downloads")
async def downloads() -> str:
    images = get_console_images()

    # sort by timestamp
    images.sort(
        key=lambda x: get_date(x),
        reverse=True,
    )
    
    # only take first CONSOLE_IMAGE_VIEWER_LIMIT
    images = images[: con.CONSOLE_IMAGE_VIEWER_LIMIT]

    # find the dates of each image
    dates = set()
    for image in images:
        dates.add(get_date(image)[:10])
    dates_list = list(dates)
    dates_list.sort(reverse=True)

    image_tupel = [(image, get_date(image)[:10], get_angle(image)) for image in images]

    count = len(images)
    narrow = sum(CameraAngle.Narrow in i for i in images)
    normal = sum(CameraAngle.Normal in i for i in images)
    wide = sum(CameraAngle.Wide in i for i in images)
    logger.warning(
        f"Showing {len(image_tupel)} images, from {len(dates_list)} different dates."
    )
    # logger.info(f"Images: {images}")
    return await render_template(
        "downloads.html",
        image_tupel=image_tupel,
        count=count,
        narrow=narrow,
        normal=normal,
        wide=wide,
        dates=dates_list,
    )


@app.route("/live")
async def live() -> str:
    # list all images
    images = os.listdir(con.CONSOLE_LIVE_PATH)
    # filter to only png
    images = [s for s in images if s.endswith(".png")]

    # sort by date modifyed, starting with the newest
    images.sort(
        key=lambda x: os.path.getmtime(Path(con.CONSOLE_LIVE_PATH) / x), reverse=True
    )
    # only take first CONSOLE_IMAGE_VIEWER_LIMIT
    images = images[: con.CONSOLE_IMAGE_VIEWER_LIMIT]

    count = len(images)
    narrow = sum(CameraAngle.Narrow in i for i in images)
    normal = sum(CameraAngle.Normal in i for i in images)
    wide = sum(CameraAngle.Wide in i for i in images)
    logger.warning(f"Showing {count} images.")
    # logger.info(f"Images: {images}")
    return await render_template(
        "live.html", images=images, count=count, narrow=narrow, normal=normal, wide=wide
    )


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
            area_covered_narrow=f"{console.live_telemetry.area_covered.narrow * 100 :.2f}",  # convert percantage
            area_covered_normal=f"{console.live_telemetry.area_covered.normal * 100 :.2f}",  # convert percantage
            area_covered_wide=f"{console.live_telemetry.area_covered.wide * 100 :.2f}",  # convert percantage
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
            # melvonaut api
            api=console.live_melvonaut_api,
            melvonaut_image_count=console.melvonaut_image_count,
            console_image_count=console.console_image_count,
            console_image_dates=console.console_image_dates,
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
            # melvonaut api
            api=console.live_melvonaut_api,
            melvonaut_image_count=console.melvonaut_image_count,
            console_image_count=console.console_image_count,
            console_image_dates=console.console_image_dates,
        )


@app.route("/melvonaut_api", methods=["POST"])
async def melvonaut_api() -> Response:
    global console

    # read which button was pressed
    form = await request.form
    button = form.get("button", type=str)

    match button:
        case "status":
            console.live_melvonaut_api = melvin_api.live_melvonaut()
            if not console.live_melvonaut_api:
                await flash("Could not contact Melvonaut API - live_melvonaut.")
        case "count":
            folder = pathlib.Path(con.CONSOLE_DOWNLOAD_PATH)
            console.console_image_count = sum(
                file.is_file() for file in folder.rglob("*.png")
            )

            # find the dates of each image
            dates = set()
            for image in folder.rglob("*.png"):
                dates.add(get_date(image.name)[:10])
            dates_list = list(dates)
            dates_list.sort(reverse=True)
            console.console_image_dates = dates_list
            logger.info(f"Counted images on console, found {console.console_image_count} from {len(console.console_image_dates)} different dates.")

            images = melvin_api.list_images()
            if type(images) is list:
                console.melvonaut_image_count = len(images)
            else:
                await flash("Could not contact Melvonaut API - count.")
        case "sync":
            images = melvin_api.list_images()
            if type(images) is list:
                console.melvonaut_image_count = len(images)
                success = 0
                failed = 0
                already_there = 0
                for image in images:
                    if os.path.isfile(con.CONSOLE_DOWNLOAD_PATH + image):
                        already_there += 1
                        logger.info(f'File "{image}" exists, not downloaded')
                        continue
                    r = melvin_api.get_download_save_image(image)
                    if r:
                        with open(
                            con.CONSOLE_DOWNLOAD_PATH + image,
                            "wb",
                        ) as f:
                            f.write(r.content)
                        success += 1
                        # logger.info(f'Downloaded "{image}" success!')
                    else:
                        failed += 1
                        logger.warning(f'File "{image}" failed!')
                await flash(
                    f"Downloaded Images from Melvonaut, success: {success}, failed: {failed}, already exisiting: {already_there}"
                )
            else:
                await flash("Could not contact Melvonaut API - count.")

            folder = pathlib.Path(con.CONSOLE_DOWNLOAD_PATH)
            console.console_image_count = sum(
                file.is_file() for file in folder.rglob("*.png")
            )

        case "clear":
            if melvin_api.clear_images():
                if console.melvonaut_image_count != -1:
                    await flash(f"Cleared {console.melvonaut_image_count} images.")
                else:
                    await flash("Cleared all images.")
                console.melvonaut_image_count = 0
            else:
                await flash("Clearing of images failed!")

        case "sync_logs":
            logs = melvin_api.list_logs()
            dir = "logs-" + live_utc().strftime("%Y-%m-%dT%H:%M:%S")
            path = Path(con.CONSOLE_FROM_MELVONAUT_PATH + dir)
            if not path.exists():
                path.mkdir()
            if type(logs) is list:
                console.melvonaut_image_count = len(logs)
                success = 0
                failed = 0
                already_there = 0
                for log in logs:
                    r = melvin_api.get_download_save_log(log)
                    if r:
                        with open(
                            con.CONSOLE_FROM_MELVONAUT_PATH + dir + "/" + log,
                            "wb",
                        ) as f:
                            f.write(r.content)
                        success += 1
                        # logger.info(f'Downloaded "{log}" success!')
                    else:
                        failed += 1
                        logger.warning(f'File "{log}" failed!')
                await flash(
                    f"Downloaded Logs from Melvonaut, success: {success}, failed: {failed} to {con.CONSOLE_FROM_MELVONAUT_PATH + dir}"
                )
            else:
                await flash("Could not contact Melvonaut API - count.")

            folder = pathlib.Path(con.CONSOLE_DOWNLOAD_PATH)
            console.console_image_count = sum(
                file.is_file() for file in folder.rglob("*.png")
            )

        case "clear_logs":
            if melvin_api.clear_logs():
                await flash("Cleared all logs.")
            else:
                await flash("Clearing of logs failed!")

        case "down_telemetry":
            res = melvin_api.download_telemetry()
            await flash(res)
        case "clear_telemetry":
            res = melvin_api.clear_telemetry()
            await flash(res)

        case "down_events":
            res = melvin_api.download_events()
            await flash(res)
        case "clear_events":
            res = melvin_api.clear_events()
            await flash(res)
        case _:
            logger.error(f"Unknown button pressed: {button}")
            await flash("Unknown button pressed.")

    return redirect(url_for("index"))


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
        case "stitch":
            choose_date = form.get("choose_date", type=str)
            if not choose_date:
                logger.warning("Tried to stitch worldmap but no date given.")
                await flash("Tried to stitch worldmap but no date given.")

            images = get_console_images()
            filtered_images = []
            for image in images:
                if choose_date in image:
                    filtered_images.append(image)
            logger.warning(f"Starting stitching, found {len(images)} images and {len(filtered_images)} with right day.")
            await flash(f"Starting stitching of {len(filtered_images)} images.")

            panorama = rift_console.image_processing.stitch_images(image_path=con.CONSOLE_DOWNLOAD_PATH, image_name_list=filtered_images)

            remove_offset = (
                con.STITCHING_BORDER,
                con.STITCHING_BORDER,
                con.WORLD_X + con.STITCHING_BORDER,
                con.WORLD_Y + con.STITCHING_BORDER,
            )
            panorama = panorama.crop(remove_offset)

            space = ""
            count = 0
            path = f"{con.CONSOLE_STICHED_PATH}worldmap_{choose_date}{space}.png"
            while os.path.isfile(path):
                count += 1
                space = "_" + str(count)
                path = f"{con.CONSOLE_STICHED_PATH}worldmap_{choose_date}{space}.png"

            panorama.save(path)

            logger.warning(f"Saved {choose_date} panorama of {len(filtered_images)} images to {path}")
            await flash(f"Saved {choose_date} panorama of {len(filtered_images)} images to {path}")
        case _:
            logger.error(f"Unknown button pressed: {button}")
            await flash("Unknown button pressed.")

    await update_telemetry()

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
            await flash("Unknown button pressed.")

    await update_telemetry()

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

    await update_telemetry()

    return redirect(url_for("index"))


@app.route("/del_obj/<int:obj_id>", methods=["POST"])
async def del_obj(obj_id: int) -> Response:
    ciarc_api.delete_objective(id=obj_id)
    await update_telemetry()

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
        case "image":
            await update_telemetry()
            if console.live_telemetry:
                t = ciarc_api.console_api_image(console.live_telemetry.angle)
                if t:
                    await flash(
                        f"Got image @{con.CONSOLE_LIVE_PATH}live_{console.live_telemetry.angle}_{t}.png"
                    )
                else:
                    await flash("Could not get image, not in acquistion mode?")
            else:
                await flash("No Telemetry, cant take image!")
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
            await flash("Unknown button pressed.")

    await update_telemetry()
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
            console.prev_state = State.Unknown
            console.next_state = State.Unknown
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
            await flash("Unknown button pressed.")

    await update_telemetry()
    return redirect(url_for("index"))


# Pulls API after some changes
async def update_telemetry() -> None:
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

    else:
        await flash("Could not contact CIARC API.")


@click.group()
@click.version_option()
def main() -> None:
    """Rift Console."""
    pass


@main.command()
def run_server() -> None:
    """Run the Flask development server on port 3000."""
    click.echo("Starting Quart server on port 3000...")

    # thread = threading.Thread(target=call_telemetry)
    # thread.start()

    config = Config()
    config.bind = ["0.0.0.0:3000"]

    asyncio.run(serve(app, config))

    # old run command
    # app.run(port=3000, debug=False, host="0.0.0.0")


@main.command()
def cli_only() -> None:
    """Original Rift Console CLI command, to run via poetry on a different port"""
    click.echo("Starting Quart server on port 4000...")

    config = Config()
    config.bind = ["0.0.0.0:4000"]

    asyncio.run(serve(app, config))


if __name__ == "__main__":
    main(prog_name="Rift Console")  # pragma: no cover

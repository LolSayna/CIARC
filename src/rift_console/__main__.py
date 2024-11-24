"""Command-line interface."""

import datetime
import sys
import time
import requests

import click
from loguru import logger

from flask import Flask, render_template, redirect, url_for, request
from werkzeug.wrappers.response import Response

# shared imports
import shared.constants as con
from shared.models import State, Telemetry, CameraAngle
import rift_console.drsApi as drsApi

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


# not sure of ich das mit den Klassen so mag wie es jetzt ist TODO
class RiftTelemetry(Telemetry):
    fuel: float = 100.0
    battery: float = 100
    state: State = State.Unknown
    active_time: float = -1
    angle: CameraAngle = CameraAngle.Unknown

    width_x: int = -1
    height_y: int = -1
    vx: float = -1
    vy: float = -1
    simulation_speed: int = 1
    max_battery: float = 100

    old_pos: tuple[int, int] = (-1, -1)
    older_pos: tuple[int, int] = (-1, -1)
    oldest_pos: tuple[int, int] = (-1, -1)
    last_timestamp: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)
    pre_transition_state: State = State.Unknown
    planed_transition_state: State = State.Unknown

    # manually managed by drsAPI.change_simulation_speed()
    is_network_simulation_active: bool = True

    def reset(self) -> None:
        with requests.Session() as s:
            r = s.get(con.RESET_ENDPOINT)

        if r.status_code == 200:
            logger.info("Reset successful")
        else:
            logger.warning("Reset failed")
            logger.debug(r)

        self.update_telemetry()

    def update_telemetry(self) -> None:
        # print("A")
        with requests.Session() as s:
            r = s.get(con.OBSERVATION_ENDPOINT)

        if r.status_code == 200:
            logger.debug("Observation successful")
        else:
            logger.warning("Observation failed")
            logger.debug(r)
            return

        data = r.json()

        # TODO check if data is valid
        # print(data)

        self.active_time = data["active_time"]
        self.battery = data["battery"]
        self.fuel = data["fuel"]
        self.state = data["state"]
        self.width_x = data["width_x"]
        self.height_y = data["height_y"]
        self.vx = data["vx"]
        self.vy = data["vy"]
        self.simulation_speed = data["simulation_speed"]
        self.timestamp = datetime.datetime.fromisoformat(data["timestamp"])
        self.angle = data["angle"]
        self.max_battery = data["max_battery"]

        # if the last timestamp is longer then 10s ago shift around
        if (self.timestamp - self.last_timestamp).total_seconds() > 10:
            self.last_timestamp = self.timestamp
            self.oldest_pos = self.older_pos
            self.older_pos = self.old_pos
            self.old_pos = (self.width_x, self.height_y)

        # TODO fix bug with error state
        # if next state is safe mode, store last valid state
        # if self.state == State.Transition and self.state != State.Safe and data['state'] == State.Safe:
        #    self.pre_transition_state = self.state

        self.state = data["state"]

        if self.state != State.Transition:
            self.planed_transition_state = State.Unknown

        """
        print(self.timestamp)
        print(self.last_timestamp)
        print(self.old_pos)
        print(self.older_pos)
        print(self.oldest_pos)
        """

        return

    # only change the state, nothing else
    def change_state(self, target_state: State) -> None:
        body = {
            "vel_x": self.vx,
            "vel_y": self.vy,
            "camera_angle": self.angle,
            "state": str(target_state),
        }

        self.pre_transition_state = self.state

        with requests.Session() as s:
            r = s.put(con.CONTROL_ENDPOINT, json=body)

        if r.status_code == 200:
            logger.debug("Control successful")
        else:
            logger.warning("Control failed")
            logger.debug(r)
            return

        self.planed_transition_state = target_state
        print("Changing to: " + target_state)
        self.update_telemetry()
        return


app = Flask(__name__)
melvin = RiftTelemetry()


# Main Page
@app.route("/", methods=["GET"])
def index() -> str:
    # when refreshing pull updated telemetry
    melvin.update_telemetry()

    return render_template(
        "console.html",
        width_x=melvin.width_x,
        height_y=melvin.height_y,
        battery=melvin.battery,
        max_battery=melvin.max_battery,
        fuel=melvin.fuel,
        vx=melvin.vx,
        vy=melvin.vy,
        simulation_speed=melvin.simulation_speed,
        is_network_simulated=melvin.is_network_simulation_active,
        timestamp=melvin.timestamp,
        old_x=melvin.old_pos[0],
        old_y=melvin.old_pos[1],
        older_x=melvin.older_pos[0],
        older_y=melvin.older_pos[1],
        oldest_x=melvin.oldest_pos[0],
        oldest_y=melvin.oldest_pos[1],
        state=melvin.state,
        pre_transition_state=melvin.pre_transition_state,
        planed_transition_state=melvin.planed_transition_state,
    )


# TODO need help, to autorefresh
# ja das mit dem Threading ist irgendwie doch nicht so einfach :P
def call_telemetry() -> None:
    while True:
        print("Updating Telemtry")

        # TODO use javascript for autorefresh, add a alive light or something to show when connection failed
        melvin.update_telemetry()
        time.sleep(3)


# Wrapper for all Simulation Manipulation buttons
@app.route("/sim_manip_buttons", methods=["POST"])
def sim_manip_buttons() -> Response:
    # read which button was pressed
    button = request.form.get("button", type=str)
    match button:
        case "refresh":
            pass
        case "reset":
            melvin.reset()
        case "save":
            drsApi.save_backup()
        case "load":
            drsApi.load_backup()

    # afterwards refresh page (which includes updating telemetry)
    return redirect(url_for("index"))


# Slider
@app.route("/slider", methods=["POST"])
def slider_button() -> Response:
    slider_value = request.form.get("speed", default=20, type=int)
    is_network_simulation = "enableSim" in request.form
    logger.error(f"{slider_value} , {is_network_simulation}")
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

    melvin.change_state(State(state))

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

    # used to disable network simulation at start time
    drsApi.change_simulation_speed(
        melvin=melvin, is_network_simulation=False, user_speed_multiplier=1
    )
    app.run(port=8000, debug=True)


@main.command()
def cli_only() -> None:
    """Original Rift Console CLI command"""
    click.echo("Rift Console CLI.")


if __name__ == "__main__":
    main(prog_name="Rift Console")  # pragma: no cover

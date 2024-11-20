"""Command-line interface."""

import datetime
import sys

import click
from flask import Flask, render_template, redirect, url_for, request
from werkzeug.wrappers.response import Response
import shared.constants as con
from shared.models import State, Telemetry, CameraAngle
from loguru import logger

import time
import requests

##### LOGGING #####
logger.remove()
logger.add(sink=sys.stderr, level="DEBUG", backtrace=True, diagnose=True)
logger.add(
    sink=con.RIFT_LOG_LOCATION,
    rotation="00:00",
    level="DEBUG",
    backtrace=True,
    diagnose=True,
)


def change_simulation_speed(user_speed_multiplier: int) -> None:
    params = {
        "is_network_simulation": "false",
        "user_speed_multiplier": str(user_speed_multiplier),
    }
    with requests.Session() as s:
        r = s.put(con.SIMULATION_ENDPOINT, params=params)
    if r.status_code == 200:
        logger.info(f"Changed simulation speed to {user_speed_multiplier}")
    else:
        logger.warning(f"Simulation Speed change to {user_speed_multiplier} failed")
        logger.debug(r)

    return


class RiftTelemetry(Telemetry):
    # Rather init the values to None then possible making incorrect assumptions.

    def __init__(self) -> None:
        self.fuel = 100
        self.battery = 100
        self.sate = State.Unknown
        self.active_time = -1
        self.angle = CameraAngle.Unknown

        self.width_x = -1
        self.height_y = -1
        self.vx = -1
        self.vy = -1
        self.simulation_speed = 1
        self.max_battery = 100

        self.old_pos = (-1, -1)
        self.older_pos = (-1, -1)
        self.oldest_pos = (-1, -1)
        self.last_timestamp = datetime.datetime.now(datetime.timezone.utc)
        self.pre_transition_state = State.Unknown
        self.planed_transition_state = State.Unknown

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
        # if self.state == State.Transition and self.sate != State.Safe and data['state'] == State.Safe:
        #    self.pre_transition_state = self.sate

        self.sate = data["state"]

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

# TODO-s
# - Autorefresh (maybe javascript)
# - Map schöner machen
# - Elemente kleiner machen
# - restliche API endpoints


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
        timestamp=melvin.timestamp,
        old_x=melvin.old_pos[0],
        old_y=melvin.old_pos[1],
        older_x=melvin.older_pos[0],
        older_y=melvin.older_pos[1],
        oldest_x=melvin.oldest_pos[0],
        oldest_y=melvin.oldest_pos[1],
        state=melvin.sate,
        pre_transition_state=melvin.pre_transition_state,
        planed_transition_state=melvin.planed_transition_state,
    )


# TODO need help, to autorefresh
# ja das mit dem Threading ist irgendwie doch nicht so einfach :P
def call_telemetry() -> None:
    while True:
        print("Updating Telemtry")
        melvin.update_telemetry()
        time.sleep(3)


# /NAME wird nicht weiter verwendet, func name muss in html matchen
@app.route("/telemetry", methods=["POST"])
def refresh_button() -> Response:
    # just refresh the page
    return redirect(url_for("index"))


# Slider
@app.route("/slider", methods=["POST"])
def slider_button() -> Response:
    slider_value = request.form.get("speed", default=20, type=int)
    print(slider_value)
    change_simulation_speed(slider_value)

    return redirect(url_for("index"))


# State Changer
@app.route("/state_changer", methods=["POST"])
def state_buttons() -> Response:
    state = request.form.get("state", default=State.Unknown, type=State)

    melvin.change_state(State(state))

    return redirect(url_for("index"))


# Reset
@app.route("/reset", methods=["POST"])
def reset_button() -> Response:
    melvin.reset()
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
    change_simulation_speed(1)
    app.run(port=8000, debug=True)


@main.command()
def cli_only() -> None:
    """Original Rift Console CLI command"""
    click.echo("Rift Console CLI.")


if __name__ == "__main__":
    main(prog_name="Rift Console")  # pragma: no cover

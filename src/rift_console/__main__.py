"""Command-line interface."""

import click
import datetime
from enum import StrEnum
from flask import Flask, render_template

class State(StrEnum):
    Deployment = "deployment"
    Acquisition = "acquisition"
    Charge = "charge"
    Safe = "safe"
    Communication = "communication"
    Transition = "transition"
    Unknown = "none"

class Melvin():
    active_time: float
    battery: float
    distance_covered: float
    fuel: float
    height_y: float
    images_taken: int
    max_battery: float
    objectives_done: int
    objectives_points: int
    simulation_speed: int
    state: State
    timestamp: datetime.datetime
    vx: float
    vy: float
    width_x: float

app = Flask(__name__)

@app.route("/")
def index() -> str:
    """index"""
    return render_template('console.html', energy=50, fuel=75)


@app.route("/hello")
def hello_world() -> str:
    """Simple Hello World endpoint."""
    return "Hello, World from Rift Console's Flask Server!"




@click.group()
@click.version_option()
def main() -> None:
    """Rift Console."""
    pass


@main.command()
def run_server() -> None:
    """Run the Flask development server on port 8000."""
    click.echo("Starting Flask development server on port 8000...")
    app.run(port=8000, debug=True)


@main.command()
def cli_only() -> None:
    """Original Rift Console CLI command"""
    click.echo("Rift Console CLI.")


if __name__ == "__main__":
    main(prog_name="Rift Console")  # pragma: no cover

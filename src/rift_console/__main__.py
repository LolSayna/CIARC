"""Command-line interface."""

import click
from flask import Flask, render_template
from shared.constants import *
from shared.melvin import *


app = Flask(__name__)
melvin = Melvin()

@app.route("/")
def index() -> str:
    """index"""
    return render_template('console.html', energy=50, fuel=75)


@app.route("/hello")
def hello_world() -> str:
    """Simple Hello World endpoint."""
    return "Hello, World from Rift Console's Flask Server!"


def update_telemtry():
    melvin.active_time += 5
    return



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

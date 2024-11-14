"""Command-line interface."""

import click
from flask import Flask

app = Flask(__name__)


@app.route("/")
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
    app.run(port=8000, debug=False)


@main.command()
def cli_only() -> None:
    """Original Rift Console CLI command"""
    click.echo("Rift Console CLI.")


if __name__ == "__main__":
    main(prog_name="Rift Console")  # pragma: no cover

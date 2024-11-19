"""Command-line interface."""

import click
from flask import *
from shared.constants import *
from shared.melvin import *


app = Flask(__name__)
melvin = Melvin()

app.secret_key = 'your_secure_random_secret_key'

@app.route("/", methods=['GET'])
def index() -> str:
    """index"""
    print(melvin.update_telemtry())
    return render_template('console.html', width_x=melvin.width_x, height_y=melvin.height_y, battery=melvin.battery, fuel=melvin.fuel)


@app.route("/hello")
def hello_world() -> str:
    """Simple Hello World endpoint."""
    return "Hello, World from Rift Console's Flask Server!"


@app.route('/exec', methods=['POST'])
def execute_function():
    # Call your Python function here
    button()
    # Provide feedback to the user
    flash('Updated Telemtry!')
    return redirect(url_for('index'))


def button():
    print("TSET")
    print(melvin.update_telemtry())
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

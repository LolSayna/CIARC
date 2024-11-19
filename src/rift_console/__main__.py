"""Command-line interface."""

import click
from flask import *
from shared.constants import *
from shared.melvin import *


app = Flask(__name__)
melvin = Melvin()

# used for flash func
app.secret_key = 'your_secure_random_secret_key'

# Main Page
@app.route("/", methods=['GET'])
def index() -> str:
    
    # when refreshing pull updated telemetry
    melvin.update_telemetry()
    return render_template('console.html', width_x=melvin.width_x, height_y=melvin.height_y, battery=melvin.battery, fuel=melvin.fuel)



# /NAME wird nicht weiter verwendet, func name muss in html matchen
@app.route('/telemetry', methods=['POST'])
def telemtry_button():
    # just refresh the page
    return redirect(url_for('index'))



@app.route('/reset', methods=['POST'])
def reset_button():
    
    melvin.reset()
    return redirect(url_for('index'))



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

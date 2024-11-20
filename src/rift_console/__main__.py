"""Command-line interface."""

import click
from flask import *
from shared.constants import *
from shared.melvin import *

import threading
import time
import logging


app = Flask(__name__)
melvin = Melvin()

# TODO-s
# - Autorefresh (maybe javascript)
# - Map schöner machen
# - Elemente kleiner machen
# - restliche API endpoints


# Main Page
@app.route("/", methods=['GET'])
def index() -> str:
    
    # when refreshing pull updated telemetry
    melvin.update_telemetry()

    return render_template('console.html', width_x=melvin.width_x, height_y=melvin.height_y, battery=melvin.battery, max_battery=melvin.max_battery, fuel=melvin.fuel,
                           vx = melvin.vx, vy=melvin.vy,
                           simulation_speed=melvin.simulation_speed, timestamp=melvin.timestamp,
                           old_x=melvin.old_pos[0], old_y=melvin.old_pos[1],
                           older_x=melvin.older_pos[0], older_y=melvin.older_pos[1],
                           oldest_x=melvin.oldest_pos[0], oldest_y=melvin.oldest_pos[1],
                           state=melvin.sate, pre_transition_state=melvin.pre_transition_state, planed_transition_state = melvin.planed_transition_state)


# TODO need help, to autorefresh
# ja das mit dem Threading ist irgendwie doch nicht so einfach :P
def call_telemetry():
    while True:
        print("Updating Telemtry")
        melvin.update_telemetry()
        time.sleep(3)


# /NAME wird nicht weiter verwendet, func name muss in html matchen
@app.route('/telemetry', methods=['POST'])
def refresh_button():
    # just refresh the page
    return redirect(url_for('index'))

# Slider
@app.route('/slider', methods=['POST'])
def slider_button():
    
    slider_value = request.form.get('speed', default=20, type=int)
    print(slider_value)
    melvin.change_simulationspeed(slider_value)

    return redirect(url_for('index'))

# State Changer
@app.route('/state_changer', methods=['POST'])
def state_buttons():
    
    state = request.form.get('state', default=State.Unknown, type=str)

    melvin.change_state(State(state))

    return redirect(url_for('index'))

# Reset
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

    thread = threading.Thread(target=call_telemetry)
    #thread.start()


    # used to disable network simulation at start time
    melvin.change_simulationspeed(1)
    app.run(port=8000, debug=True)


@main.command()
def cli_only() -> None:
    """Original Rift Console CLI command"""
    click.echo("Rift Console CLI.")


if __name__ == "__main__":

    main(prog_name="Rift Console")  # pragma: no cover

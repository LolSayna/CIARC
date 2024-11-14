"""Command-line interface."""

import click


@click.command()
@click.version_option()
def main() -> None:
    """Rift Console."""


if __name__ == "__main__":
    main(prog_name="Rift Console")  # pragma: no cover

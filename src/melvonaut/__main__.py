"""Command-line interface."""

import click


@click.command()
@click.version_option()
def main() -> None:
    """Melvonaut."""


if __name__ == "__main__":
    main(prog_name="Melvonaut")  # pragma: no cover

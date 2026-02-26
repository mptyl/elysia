import os
from dotenv import set_key, load_dotenv
from rich import print

load_dotenv()

if "FIRST_START_ELYSIA" not in os.environ:
    print(
        "\n\n[bold green]Starting Elysia for the first time. This may take a minute to complete...[/bold green]\n\n"
    )
    set_key(".env", "FIRST_START_ELYSIA", "1")

import click
import uvicorn


@click.group()
def cli():
    """Main command group for Elysia."""
    pass


@cli.command()
@click.option(
    "--port",
    default=8090,
    help="FastAPI Port",
)
@click.option(
    "--host",
    default="0.0.0.0",
    help="FastAPI Host",
)
@click.option(
    "--reload",
    default=False,
    help="FastAPI Reload (watch for file changes and auto-restart)",
)
def start(port, host, reload):
    """
    Run the FastAPI application.
    """

    uvicorn.run(
        "elysia.api.app:app",
        host=host,
        port=port,
        reload=reload,
        ws="wsproto",
    )


if __name__ == "__main__":
    cli()

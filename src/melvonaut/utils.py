from apprise import NotifyType
from loguru import logger
from shared import constants as con
from melvonaut.settings import settings
import sys
import apprise
from typing import Any

file_log_handler_id = None

## [Logging]


@apprise.decorators.notify(on="melvin")  # type: ignore
def melvin_notifier(
    body: str, title: str, notify_type: NotifyType, *args: Any, **kwargs: dict[str, Any]
) -> None:
    """Melvin-specific notification handler.

    Just prints to stdout.

    Args:
        body (str): The message body.
        title (str): The notification title.
        notify_type (NotifyType): The type of notification.
        *args (Any): Additional arguments.
        **kwargs (dict[str, Any]): Additional keyword arguments.
    """
    print("MELVIN HERE!")


def setup_logging() -> None:
    """Configures the logging system for the application.

    This function removes existing log handlers, sets up terminal logging,
    and configures Apprise notifications for Discord and Melvin events.
    """
    logger.remove()
    logger.add(
        sink=sys.stdout,
        level=settings.TERMINAL_LOGGING_LEVEL,
        backtrace=True,
        diagnose=True,
        enqueue=True,
    )
    notifier = apprise.Apprise()
    if settings.DISCORD_WEBHOOK_TOKEN and settings.DISCORD_ALERTS_ENABLED:
        notifier.add(f"discord://{settings.DISCORD_WEBHOOK_TOKEN}")
        logger.add(notifier.notify, level="ERROR", filter={"apprise": False})  # type: ignore

    if settings.NETWORK_SIM_ENABLED:
        notifier.add("melvin://")
        logger.add(notifier.notify, level="ERROR", filter={"apprise": False})  # type: ignore

    setup_file_logging()


def setup_file_logging() -> None:
    """Configures file-based logging with rotation at midnight.

    If a file log handler already exists, it is removed before adding a new one.
    """
    global file_log_handler_id
    if file_log_handler_id is not None:
        logger.remove(file_log_handler_id)  # type: ignore
    file_log_handler_id = logger.add(
        sink=con.MEL_LOG_LOCATION,
        rotation="00:00",
        level=settings.FILE_LOGGING_LEVEL,
        backtrace=True,
        diagnose=True,
        enqueue=True,
    )

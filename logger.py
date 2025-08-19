import logging
from typing import Union
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

custom_theme = Theme({
    "info": "green",
    "warning": "yellow",
    "error": "bold red",
    "debug": "cyan",
    "time": "dim cyan",
    "path": "magenta",
})

def setup_logging(
        log_file: str = "app.log",
        terminal_width: Union[int, None] = None,
        level: int = logging.INFO
) -> logging.Logger:
    console = Console(width=terminal_width, theme=custom_theme)

    rich_handler = RichHandler(
        show_time=True,
        show_level=True,
        show_path=True,
        markup=True,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        console=console,
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)

    logger = logging.getLogger("cwa")
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(rich_handler)
    logger.addHandler(file_handler)

    return logger
"""Rich console setup and theme."""

from rich.console import Console
from rich.theme import Theme

# Custom theme for the backup utility
BACKUP_THEME = Theme({
    # Primary colors
    "primary": "bold cyan",
    "secondary": "bold blue",
    "accent": "bold magenta",

    # Status colors
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "info": "bold blue",
    "skip": "bold cyan",
    "retry": "bold yellow",
    "failed": "bold red",
    "pull": "white",

    # UI elements
    "panel.border": "cyan",
    "panel.title": "bold cyan",
    "progress.bar": "cyan",
    "progress.complete": "green",
    "progress.remaining": "dim cyan",
    "table.header": "bold cyan",
    "table.border": "dim cyan",

    # Text styles
    "dim": "dim white",
    "timestamp": "dim white",
    "path": "dim blue",
    "package": "bold white",
    "serial": "bold yellow",
    "bytes": "bold green",
    "eta": "bold magenta",
})


def create_console(color_system: str = "auto", force_terminal: bool = True) -> Console:
    """Create configured Rich console.

    legacy_windows=False uses WriteConsoleW so Unicode progress bars,
    spinners and status glyphs render on cmd.exe / PowerShell /
    Windows Terminal instead of crashing with cp1252 encode errors.
    """
    return Console(
        theme=BACKUP_THEME,
        color_system=color_system,
        force_terminal=force_terminal,
        highlight=False,
        legacy_windows=False,
    )


# Global console instance
console = create_console()

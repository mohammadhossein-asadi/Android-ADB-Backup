"""Status panels for device info, summary, errors."""


from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def create_device_panel(device_info: dict, serial: str, connected: bool = True) -> Panel:
    """Create device info panel."""
    status = "[success]● Connected" if connected else "[error]○ Disconnected"

    table = Table.grid(padding=(0, 1))
    table.add_column(style="secondary", justify="right")
    table.add_column(style="white")

    table.add_row("Model:", device_info.get('ro.product.model', 'Unknown'))
    table.add_row("Manufacturer:", device_info.get('ro.product.manufacturer', 'Unknown'))
    table.add_row("Device:", device_info.get('ro.product.device', 'Unknown'))
    table.add_row("Android:", f"{device_info.get('ro.build.version.release', '?')} (SDK {device_info.get('ro.build.version.sdk', '?')})")
    table.add_row("Serial:", serial)

    return Panel(
        table,
        title="[panel.title]Device",
        subtitle=status,
        border_style="panel.border",
        padding=(0, 1),
    )


def create_summary_panel(state, total_mb: float) -> Panel:
    """Create backup summary panel."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="secondary", justify="right")
    table.add_column(style="white")

    table.add_row("Packages:", f"{state.stats.success_packages}/{state.stats.total_packages}")
    table.add_row("APKs:", f"{state.stats.success_apks}/{state.stats.total_apks}")
    table.add_row("Failed:", str(state.stats.failed_packages))
    table.add_row("Skipped:", str(state.stats.skipped_packages))
    table.add_row("Size:", f"{total_mb:.2f} MB")

    return Panel(
        table,
        title="[panel.title]Summary",
        border_style="panel.border",
        padding=(0, 1),
    )


def create_error_panel(errors: list[str]) -> Panel:
    """Create error panel."""
    if not errors:
        return Panel(
            Text("No errors", style="success"),
            title="[panel.title]Errors",
            border_style="panel.border",
            padding=(0, 1),
        )

    text = Text()
    for i, err in enumerate(errors[-5:], 1):
        text.append(f"{i}. ", style="dim")
        text.append(err, style="error")
        text.append("\n")

    return Panel(
        text,
        title="[panel.title]Recent Errors",
        border_style="error",
        padding=(0, 1),
    )


def create_logs_panel(log_lines: list[str]) -> Panel:
    """Create logs tail panel."""
    text = Text()
    for line in log_lines[-10:]:
        text.append(line + "\n", style="dim")

    return Panel(
        text,
        title="[panel.title]Logs (tail)",
        border_style="panel.border",
        padding=(0, 1),
    )

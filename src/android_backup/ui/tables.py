"""Table components for package listing, final summary."""


from rich.table import Table
from rich.text import Text


def create_package_table(packages: list[dict]) -> Table:
    """Create package listing table."""
    table = Table(
        title="[panel.title]Packages to Backup",
        border_style="panel.border",
        header_style="table.header",
        show_lines=True,
    )

    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Package", style="package", min_width=30)
    table.add_column("APKs", style="dim", width=6, justify="right")
    table.add_column("Status", width=10, justify="center")

    for i, pkg in enumerate(packages, 1):
        status_style = {
            'pending': 'warning',
            'ok': 'success',
            'failed': 'failed',
            'skip': 'skip',
        }.get(pkg.get('status', 'pending'), 'info')

        table.add_row(
            str(i),
            pkg['name'],
            str(pkg.get('apk_count', '?')),
            Text(pkg.get('status', 'PENDING').upper(), style=status_style),
        )

    return table


def create_final_summary_table(state, total_mb: float) -> Table:
    """Create final summary table."""
    table = Table(
        title="[panel.title]Backup Complete",
        border_style="panel.border",
        header_style="table.header",
        show_lines=True,
    )

    table.add_column("Metric", style="secondary")
    table.add_column("Value", style="white", justify="right")

    table.add_row("Total Packages", str(state.stats.total_packages))
    table.add_row("Successful", Text(str(state.stats.success_packages), style="success"))
    table.add_row("Failed", Text(str(state.stats.failed_packages), style="failed"))
    table.add_row("Skipped", Text(str(state.stats.skipped_packages), style="skip"))
    table.add_row("Total APKs", str(state.stats.total_apks))
    table.add_row("APKs Successful", Text(str(state.stats.success_apks), style="success"))
    table.add_row("APKs Failed", Text(str(state.stats.failed_apks), style="failed"))
    table.add_row("Total Size", f"{total_mb:.2f} MB")

    return table


def create_failed_packages_table(failed_packages: list[tuple[str, str]]) -> Table:
    """Create table of failed packages."""
    if not failed_packages:
        return None

    table = Table(
        title="[panel.title]Failed Packages",
        border_style="failed",
        header_style="table.header",
        show_lines=True,
    )

    table.add_column("Package", style="package")
    table.add_column("Error", style="error")

    for package, error in failed_packages:
        table.add_row(package, error)

    return table

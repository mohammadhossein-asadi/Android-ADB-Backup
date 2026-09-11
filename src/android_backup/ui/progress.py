"""Progress tracking with Rich - live progress bars, ETA, counters."""

from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
    SpinnerColumn,
)
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from typing import Optional

from .console import console


class BackupProgress:
    """Live progress display for backup operations."""

    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(style="primary"),
            TextColumn("[primary]{task.description}"),
            BarColumn(bar_width=40, style="progress.bar", complete_style="progress.complete"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=False,
        )

        self.overall_task = None
        self.package_task = None
        self.apk_task = None

        # Counters
        self.ok_count = 0
        self.skip_count = 0
        self.fail_count = 0
        self.retry_count = 0
        self.pull_count = 0

        self._live: Optional[Live] = None

    def start(self) -> None:
        """Start the live display."""
        self.overall_task = self.progress.add_task(
            "[primary]Overall Progress",
            total=100,
            visible=True
        )
        self.package_task = self.progress.add_task(
            "[secondary]Package",
            total=100,
            visible=True
        )
        self.apk_task = self.progress.add_task(
            "[accent]Current APK",
            total=100,
            visible=True
        )

        self._live = Live(self._build_layout(), console=console, refresh_per_second=4, screen=True)
        self._live.start()

    def stop(self) -> None:
        """Stop the live display."""
        if self._live:
            self._live.stop()
            self._live = None

    def _build_layout(self) -> Layout:
        """Build the live layout."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="progress", size=8),
            Layout(name="counters", size=3),
            Layout(name="footer", size=3),
        )
        return layout

    def update_overall(self, completed: int, total: int, description: str = "") -> None:
        """Update overall progress."""
        if self.overall_task is not None:
            self.progress.update(
                self.overall_task,
                completed=completed,
                total=total,
                description=description or "[primary]Overall Progress"
            )

    def update_package(self, completed: int, total: int, package_name: str) -> None:
        """Update package progress."""
        if self.package_task is not None:
            self.progress.update(
                self.package_task,
                completed=completed,
                total=total,
                description=f"[secondary]{package_name} ({completed}/{total})"
            )

    def update_apk(self, completed: int, total: int, apk_name: str) -> None:
        """Update current APK progress."""
        if self.apk_task is not None:
            self.progress.update(
                self.apk_task,
                completed=completed,
                total=total,
                description=f"[accent]{apk_name}"
            )

    def increment_ok(self) -> None:
        """Increment OK counter."""
        self.ok_count += 1

    def increment_skip(self) -> None:
        """Increment SKIP counter."""
        self.skip_count += 1

    def increment_fail(self) -> None:
        """Increment FAIL counter."""
        self.fail_count += 1

    def increment_retry(self) -> None:
        """Increment RETRY counter."""
        self.retry_count += 1

    def increment_pull(self) -> None:
        """Increment PULL counter."""
        self.pull_count += 1

    def get_counters_text(self) -> Text:
        """Get formatted counters text."""
        text = Text()
        text.append("✓ OK: ", style="success")
        text.append(str(self.ok_count), style="bold")
        text.append("   ")
        text.append("⊘ SKIP: ", style="skip")
        text.append(str(self.skip_count), style="bold")
        text.append("   ")
        text.append("✗ FAIL: ", style="failed")
        text.append(str(self.fail_count), style="bold")
        text.append("   ")
        text.append("↻ RETRY: ", style="retry")
        text.append(str(self.retry_count), style="bold")
        text.append("   ")
        text.append("⬇ PULL: ", style="pull")
        text.append(str(self.pull_count), style="bold")
        return text

    def _build_layout(self) -> Layout:
        """Build the live layout."""
        layout = Layout()

        # Header
        header = Panel(
            Text("Android ADB Backup Utility v2.1.0", style="primary", justify="center"),
            border_style="panel.border",
            title="[panel.title]Backup in Progress",
            title_align="center",
        )

        # Progress panel
        progress_panel = Panel(
            self.progress,
            border_style="panel.border",
            title="[panel.title]Progress",
            title_align="left",
        )

        # Counters panel
        counters_panel = Panel(
            self.get_counters_text(),
            border_style="panel.border",
            title="[panel.title]Status",
            title_align="left",
        )

        # Footer
        footer = Panel(
            Text("Logs: backup_run.log  •  errors.log", style="dim", justify="center"),
            border_style="panel.border",
        )

        layout.split_column(
            Layout(header, size=3),
            Layout(progress_panel, size=8),
            Layout(counters_panel, size=3),
            Layout(footer, size=3),
        )
        return layout
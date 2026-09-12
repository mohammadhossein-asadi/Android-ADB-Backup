"""CLI entry point."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from ._version import __version__
from .backup.engine import BackupEngine
from .config import Config
from .exceptions import AndroidBackupError

# Create console for CLI output (legacy_windows=False for Unicode-safe Windows output)
cli_console = Console(legacy_windows=False)


@click.command()
@click.version_option(version=__version__, prog_name="android-backup")

# Backup options
@click.option('--backup-root', type=click.Path(path_type=Path), default=None,
              help='Root directory for backups (default: project-relative ./backups or ~/AndroidBackups)')
@click.option('--device-serial', type=str, default=None,
              help='Target device serial (default: auto-detect)')
@click.option('--backup-name', type=str, default=None,
              help='Custom backup folder name suffix')
@click.option('--skip-storage', is_flag=True, default=False,
              help='Skip storage folder backup')
@click.option('--full-sdcard', is_flag=True, default=False,
              help='Backup entire /sdcard (large!)')
@click.option('--force-resume', is_flag=True, default=False,
              help='Auto-resume without prompting')
@click.option('--whatif', is_flag=True, default=False,
              help='Dry-run mode - show what would be backed up')
@click.option('--verify-only', is_flag=True, default=False,
              help='Verify existing backup integrity')
@click.option('--adb-timeout', type=int, default=120,
              help='ADB command timeout in seconds')
@click.option('--max-retries', type=int, default=3,
              help='Maximum retry attempts for failed pulls')
@click.option('--adb-path', type=click.Path(path_type=Path), default=None,
              help='Explicit path to adb executable (overrides auto-detection)')
@click.option('--no-auto-adb', is_flag=True, default=False,
              help='Do not automatically download platform-tools if adb is missing')

# Package selection options
@click.option('--include-packages', type=str, default=None,
              help='Comma-separated package name patterns to include (supports wildcards, e.g., "com.whatsapp,com.telegram*")')
@click.option('--exclude-packages', type=str, default=None,
              help='Comma-separated package name patterns to exclude (supports wildcards, e.g., "*.test,*.debug")')
@click.option('--fetch-display-names/--no-fetch-display-names', default=True,
              help='Fetch and store human-readable app display names')

# Storage selection options
@click.option('--include-storage', type=str, default=None,
              help='Comma-separated storage folder names to include (e.g., "DCIM,Pictures")')
@click.option('--exclude-storage', type=str, default=None,
              help='Comma-separated storage folder names to exclude (e.g., "cache,temp")')
@click.option('--custom-storage', type=str, default=None,
              help='Custom storage folders as "remote:local" pairs (e.g., "/sdcard/MyFolder:MyFolder")')

# Scheduling options (for future daemon mode)
@click.option('--schedule-enabled', is_flag=True, default=False,
              help='Enable scheduled backups (requires daemon mode)')
@click.option('--schedule-cron', type=str, default=None,
              help='Cron expression for scheduled backups (e.g., "0 2 * * *" for daily at 2am)')
@click.option('--schedule-interval-hours', type=int, default=0,
              help='Run backup every N hours (0 to disable)')

# Config
@click.option('--config', type=click.Path(path_type=Path), default=None,
              help='Path to config file')

# UI options
@click.option('--no-color', is_flag=True, default=False,
              help='Disable colored output')
@click.option('--quiet', is_flag=True, default=False,
              help='Minimal output')

def main(
    backup_root: Optional[Path],
    device_serial: Optional[str],
    backup_name: Optional[str],
    skip_storage: bool,
    full_sdcard: bool,
    force_resume: bool,
    whatif: bool,
    verify_only: bool,
    adb_timeout: int,
    max_retries: int,
    adb_path: Optional[Path],
    no_auto_adb: bool,
    include_packages: Optional[str],
    exclude_packages: Optional[str],
    fetch_display_names: bool,
    include_storage: Optional[str],
    exclude_storage: Optional[str],
    custom_storage: Optional[str],
    schedule_enabled: bool,
    schedule_cron: Optional[str],
    schedule_interval_hours: int,
    config: Optional[Path],
    no_color: bool,
    quiet: bool,
) -> None:
    """Android ADB Backup Utility - Cross-platform, non-destructive, resumable backup tool."""

    # Load config
    cfg = Config.load(config)

    # Override with CLI args
    if backup_root:
        cfg.backup.root = backup_root
    if device_serial:
        # Store for device selection
        pass
    if no_color:
        cfg.ui.no_color = True

    cfg.backup.adb_timeout = adb_timeout
    cfg.backup.max_retries = max_retries
    if adb_path:
        cfg.adb.preferred_path = str(adb_path)
    if no_auto_adb:
        cfg.adb.auto_install = False

    # Package selection options
    if include_packages:
        cfg.backup.package_selection.include_patterns = [p.strip() for p in include_packages.split(',') if p.strip()]
    if exclude_packages:
        cfg.backup.package_selection.exclude_patterns = [p.strip() for p in exclude_packages.split(',') if p.strip()]
    cfg.backup.package_selection.fetch_display_names = fetch_display_names

    # Storage selection options
    if include_storage:
        cfg.backup.storage_selection.include_folders = [s.strip() for s in include_storage.split(',') if s.strip()]
    if exclude_storage:
        cfg.backup.storage_selection.exclude_folders = [s.strip() for s in exclude_storage.split(',') if s.strip()]
    if custom_storage:
        custom_folders = []
        for pair in custom_storage.split(','):
            pair = pair.strip()
            if ':' in pair:
                remote, local = pair.split(':', 1)
                custom_folders.append((remote.strip(), local.strip()))
        cfg.backup.storage_selection.custom_folders = custom_folders

    # Scheduling options
    cfg.backup.schedule.enabled = schedule_enabled
    if schedule_cron:
        cfg.backup.schedule.cron_expression = schedule_cron
    if schedule_interval_hours:
        cfg.backup.schedule.run_interval_hours = schedule_interval_hours

    # Create engine
    engine = BackupEngine(cfg, whatif=whatif, verify_only=verify_only)

    # Run async
    try:
        exit_code = asyncio.run(engine.run())
        sys.exit(exit_code)
    except AndroidBackupError as e:
        cli_console.print(f"[error]{e.message}[/]")
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        cli_console.print("\n[warning]Interrupted[/]")
        sys.exit(130)
    except Exception as e:
        cli_console.print(f"[error]Unexpected error: {e}[/]")
        sys.exit(1)


if __name__ == '__main__':
    main()

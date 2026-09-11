"""CLI entry point."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from .config import Config
from .backup.engine import BackupEngine
from .exceptions import AndroidBackupError
from ._version import __version__


# Create console for CLI output
cli_console = Console()


@click.command()
@click.version_option(version=__version__, prog_name="android-backup")

# Backup options
@click.option('--backup-root', type=click.Path(path_type=Path), default=None,
              help='Root directory for backups (default: ~/AndroidBackups)')
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
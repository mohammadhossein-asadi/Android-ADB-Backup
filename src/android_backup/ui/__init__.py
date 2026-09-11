"""UI package initialization."""

from .console import console, create_console, BACKUP_THEME
from .progress import BackupProgress
from .panels import (
    create_device_panel,
    create_summary_panel,
    create_error_panel,
    create_logs_panel,
)
from .tables import (
    create_package_table,
    create_final_summary_table,
    create_failed_packages_table,
)
from .prompts import (
    select_device,
    confirm_resume,
    confirm_full_sdcard,
    prompt_device_serial,
)

__all__ = [
    'console',
    'create_console',
    'BACKUP_THEME',
    'BackupProgress',
    'create_device_panel',
    'create_summary_panel',
    'create_error_panel',
    'create_logs_panel',
    'create_package_table',
    'create_final_summary_table',
    'create_failed_packages_table',
    'select_device',
    'confirm_resume',
    'confirm_full_sdcard',
    'prompt_device_serial',
]
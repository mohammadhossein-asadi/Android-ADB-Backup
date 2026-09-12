"""Storage backup module."""

import fnmatch
from pathlib import Path
from typing import Optional

from ..adb import ADBCommands
from .state import StorageEntry

# Common storage folders to backup
COMMON_FOLDERS = [
    ("/sdcard/DCIM", "DCIM"),
    ("/sdcard/Pictures", "Pictures"),
    ("/sdcard/Movies", "Movies"),
    ("/sdcard/Download", "Download"),
    ("/sdcard/Documents", "Documents"),
    ("/sdcard/Music", "Music"),
    ("/sdcard/Android/media", "Android_media"),
]


class StorageBackup:
    """Handle storage folder backup."""

    def __init__(
        self,
        commands: ADBCommands,
        max_retries: int = 2,
        include_folders: Optional[list[str]] = None,
        exclude_folders: Optional[list[str]] = None,
        custom_folders: Optional[list[tuple[str, str]]] = None
    ):
        self.commands = commands
        self.max_retries = max_retries
        self.include_folders = include_folders or []
        self.exclude_folders = exclude_folders or []
        self.custom_folders = custom_folders or []

    def _should_backup_folder(self, local_name: str) -> bool:
        """Check if a folder should be backed up based on include/exclude patterns."""
        # If include folders specified, folder must match at least one
        if self.include_folders:
            matched = any(fnmatch.fnmatch(local_name, pattern) for pattern in self.include_folders)
            if not matched:
                return False
        # If exclude folders specified, folder must not match any
        if self.exclude_folders:
            if any(fnmatch.fnmatch(local_name, pattern) for pattern in self.exclude_folders):
                return False
        return True

    async def backup_folder(
        self,
        serial: str,
        remote_folder: str,
        local_folder: Path,
        state_entry: Optional[StorageEntry] = None
    ) -> StorageEntry:
        """Backup a single storage folder."""
        # Check if already completed (resume)
        if state_entry and state_entry.success:
            return StorageEntry(success=True, skipped=True, message="already backed up")

        # Check remote exists
        exists = await self.commands.check_remote_exists(serial, remote_folder)
        if not exists:
            return StorageEntry(
                success=False,
                skipped=True,
                message="inaccessible or missing"
            )

        # Retry logic
        for attempt in range(1, self.max_retries + 1):
            if attempt > 1:
                import asyncio
                await asyncio.sleep(2)

            result = await self.commands.pull_folder(serial, remote_folder, local_folder)

            if result.success:
                return StorageEntry(success=True, skipped=False, message="ok")

        return StorageEntry(
            success=False,
            skipped=False,
            message=f"failed after {self.max_retries} attempts"
        )

    async def backup_all(
        self,
        serial: str,
        storage_dir: Path,
        state: dict[str, StorageEntry],
        full_sdcard: bool = False,
        confirm_full: bool = True
    ) -> dict[str, StorageEntry]:
        """Backup all common storage folders."""
        results = {}
        internal_root = storage_dir / 'Internal_Storage'
        internal_root.mkdir(parents=True, exist_ok=True)

        # Backup common folders with filtering
        for remote, local_name in COMMON_FOLDERS:
            if not self._should_backup_folder(local_name):
                results[remote] = StorageEntry(success=True, skipped=True, message="excluded by filter")
                continue
            local_target = internal_root / local_name
            state_entry = state.get(remote)
            result = await self.backup_folder(serial, remote, local_target, state_entry)
            results[remote] = result

        # Backup custom folders
        for remote, local_name in self.custom_folders:
            local_target = internal_root / local_name
            state_entry = state.get(remote)
            result = await self.backup_folder(serial, remote, local_target, state_entry)
            results[remote] = result

        # Full sdcard backup
        if full_sdcard:
            full_local = storage_dir / 'Full_Internal_Storage'
            state_entry = state.get('/sdcard')
            result = await self.backup_folder(serial, '/sdcard', full_local, state_entry)
            results['/sdcard'] = result

        return results

"""Storage backup module."""

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

    def __init__(self, commands: ADBCommands, max_retries: int = 2):
        self.commands = commands
        self.max_retries = max_retries

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

        for remote, local_name in COMMON_FOLDERS:
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

"""Backup state management for resume capability."""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..utils import sanitize_filename


@dataclass
class APKEntry:
    """Single APK file entry."""
    file: str
    remote: str
    size: int
    sha256: str
    success: bool = True


@dataclass
class PackageEntry:
    """Package backup entry."""
    status: str  # PENDING, OK, FAILED, SKIP
    message: str = ""
    apks: list[APKEntry] = field(default_factory=list)


@dataclass
class StorageEntry:
    """Storage folder backup entry."""
    success: bool
    skipped: bool = False
    message: str = ""


@dataclass
class BackupStats:
    """Backup statistics."""
    total_packages: int = 0
    success_packages: int = 0
    failed_packages: int = 0
    skipped_packages: int = 0
    total_apks: int = 0
    success_apks: int = 0
    failed_apks: int = 0
    total_bytes: int = 0


@dataclass
class BackupState:
    """Complete backup state for resume."""
    version: str = "2.1.0"
    serial: str = ""
    backup_dir: str = ""
    started: str = ""
    completed: bool = False
    device_info: dict = field(default_factory=dict)
    packages: dict[str, PackageEntry] = field(default_factory=dict)
    storage: dict[str, StorageEntry] = field(default_factory=dict)
    stats: BackupStats = field(default_factory=BackupStats)

    @classmethod
    def create(cls, serial: str, backup_dir: Path, device_info: dict) -> 'BackupState':
        """Create new backup state."""
        return cls(
            serial=serial,
            backup_dir=str(backup_dir),
            started=datetime.now().isoformat(),
            device_info=device_info,
        )

    def to_json(self) -> str:
        """Serialize to JSON."""
        # Convert to dict with proper serialization
        data = {
            'version': self.version,
            'serial': self.serial,
            'backup_dir': self.backup_dir,
            'started': self.started,
            'completed': self.completed,
            'device_info': self.device_info,
            'packages': {
                pkg: {
                    'status': entry.status,
                    'message': entry.message,
                    'apks': [asdict(apk) for apk in entry.apks]
                }
                for pkg, entry in self.packages.items()
            },
            'storage': {
                path: asdict(entry) for path, entry in self.storage.items()
            },
            'stats': asdict(self.stats),
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'BackupState':
        """Deserialize from JSON."""
        data = json.loads(json_str)
        state = cls(
            version=data.get('version', '2.1.0'),
            serial=data.get('serial', ''),
            backup_dir=data.get('backup_dir', ''),
            started=data.get('started', ''),
            completed=data.get('completed', False),
            device_info=data.get('device_info', {}),
            stats=BackupStats(**data.get('stats', {})),
        )

        # Restore packages
        for pkg, pkg_data in data.get('packages', {}).items():
            state.packages[pkg] = PackageEntry(
                status=pkg_data['status'],
                message=pkg_data.get('message', ''),
                apks=[APKEntry(**apk) for apk in pkg_data.get('apks', [])]
            )

        # Restore storage
        for path, storage_data in data.get('storage', {}).items():
            state.storage[path] = StorageEntry(**storage_data)

        return state

    def save(self, path: Path) -> None:
        """Save state to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding='utf-8')

    @classmethod
    def load(cls, path: Path) -> Optional['BackupState']:
        """Load state from file."""
        if not path.exists():
            return None
        try:
            return cls.from_json(path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, KeyError, TypeError):
            return None


class StateManager:
    """Manage backup state persistence."""

    def __init__(self, backup_dir: Path):
        self.backup_dir = backup_dir
        self.state_file = backup_dir / 'Reports' / 'Backup_State.json'

    def save(self, state: BackupState) -> None:
        """Save state to disk."""
        state.backup_dir = str(self.backup_dir)
        state.save(self.state_file)

    def load(self) -> Optional[BackupState]:
        """Load state from disk."""
        return BackupState.load(self.state_file)

    def find_incomplete_backups(self, serial: str) -> list[Path]:
        """Find incomplete backups for a serial."""
        backups = []
        if not self.backup_dir.parent.exists():
            return backups

        for item in self.backup_dir.parent.iterdir():
            if item.is_dir() and item.name.startswith('Backup_'):
                state_file = item / 'Reports' / 'Backup_State.json'
                if state_file.exists():
                    state = BackupState.load(state_file)
                    if state and state.serial == serial and not state.completed:
                        backups.append(item)

        # Sort by modification time, newest first
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return backups
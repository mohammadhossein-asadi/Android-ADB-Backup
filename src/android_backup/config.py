"""Configuration management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib


@dataclass
class BackupConfig:
    """Backup configuration."""
    root: Path = field(default_factory=lambda: Path.home() / "AndroidBackups")
    adb_timeout: int = 120
    max_retries: int = 3


@dataclass
class UIConfig:
    """UI configuration."""
    theme: str = "dark"  # dark, light, auto
    show_eta: bool = True
    live_update: bool = True
    compact_mode: bool = False
    no_color: bool = False


@dataclass
class ADBConfig:
    """ADB configuration."""
    preferred_path: str = ""


@dataclass
class Config:
    """Main configuration."""
    backup: BackupConfig = field(default_factory=BackupConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    adb: ADBConfig = field(default_factory=ADBConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> 'Config':
        """Load configuration from file."""
        config = cls()

        if config_path is None:
            config_path = Path.home() / '.config' / 'android-backup' / 'config.toml'

        if config_path.exists():
            try:
                with config_path.open('rb') as f:
                    data = tomllib.load(f)

                if 'backup' in data:
                    b = data['backup']
                    config.backup.root = Path(b.get('root', config.backup.root)).expanduser()
                    config.backup.adb_timeout = b.get('adb_timeout', config.backup.adb_timeout)
                    config.backup.max_retries = b.get('max_retries', config.backup.max_retries)

                if 'ui' in data:
                    u = data['ui']
                    config.ui.theme = u.get('theme', config.ui.theme)
                    config.ui.show_eta = u.get('show_eta', config.ui.show_eta)
                    config.ui.live_update = u.get('live_update', config.ui.live_update)
                    config.ui.compact_mode = u.get('compact_mode', config.ui.compact_mode)
                    config.ui.no_color = u.get('no_color', config.ui.no_color)

                if 'adb' in data:
                    a = data['adb']
                    config.adb.preferred_path = a.get('preferred_path', config.adb.preferred_path)

            except Exception:
                pass  # Use defaults on error

        return config

    def save(self, config_path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        if config_path is None:
            config_path = Path.home() / '.config' / 'android-backup' / 'config.toml'

        config_path.parent.mkdir(parents=True, exist_ok=True)

        import tomli_w
        data = {
            'backup': {
                'root': str(self.backup.root),
                'adb_timeout': self.backup.adb_timeout,
                'max_retries': self.backup.max_retries,
            },
            'ui': {
                'theme': self.ui.theme,
                'show_eta': self.ui.show_eta,
                'live_update': self.ui.live_update,
                'compact_mode': self.ui.compact_mode,
                'no_color': self.ui.no_color,
            },
            'adb': {
                'preferred_path': self.adb.preferred_path,
            },
        }

        with config_path.open('wb') as f:
            tomli_w.dump(data, f)
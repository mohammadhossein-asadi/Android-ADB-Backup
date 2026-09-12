"""Configuration management."""

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
    auto_install: bool = True


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
                    config.adb.auto_install = bool(a.get('auto_install', config.adb.auto_install))

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
                'auto_install': self.adb.auto_install,
            },
        }

        try:
            import tomli_w

            with config_path.open('wb') as f:
                tomli_w.dump(data, f)
        except ImportError:
            # Minimal fallback when tomli-w is not installed
            lines = [
                "[backup]",
                f"root = \"{data['backup']['root']}\"",
                f"adb_timeout = {data['backup']['adb_timeout']}",
                f"max_retries = {data['backup']['max_retries']}",
                "",
                "[ui]",
                f"theme = \"{data['ui']['theme']}\"",
                "",
                "[adb]",
                f"preferred_path = \"{data['adb']['preferred_path']}\"",
                f"auto_install = {'true' if data['adb']['auto_install'] else 'false'}",
                "",
            ]
            config_path.write_text("\n".join(lines), encoding="utf-8")

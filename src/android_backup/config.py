"""Configuration management."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib


@dataclass
class PackageSelectionConfig:
    """Package selection configuration."""
    include_patterns: list[str] = field(default_factory=list)  # e.g., ["com.whatsapp", "com.telegram*"]
    exclude_patterns: list[str] = field(default_factory=list)  # e.g., ["*.test", "*.debug"]
    fetch_display_names: bool = True


@dataclass
class StorageSelectionConfig:
    """Storage folder selection configuration."""
    include_folders: list[str] = field(default_factory=list)      # e.g., ["DCIM", "Pictures*"]
    exclude_folders: list[str] = field(default_factory=list)      # e.g., ["*cache*", "*temp*"]
    custom_folders: list[tuple[str, str]] = field(default_factory=list)  # e.g., [("/sdcard/MyFolder", "MyFolder")]


@dataclass
class ScheduleConfig:
    """Scheduling configuration (for future use)."""
    enabled: bool = False
    cron_expression: str = ""  # Standard cron expression
    run_at_startup: bool = False
    run_interval_hours: int = 0  # 0 = disabled


@dataclass
class BackupConfig:
    """Backup configuration."""
    root: Path = field(default_factory=lambda: Path.home() / "AndroidBackups")
    adb_timeout: int = 120
    max_retries: int = 3
    package_selection: PackageSelectionConfig = field(default_factory=PackageSelectionConfig)
    storage_selection: StorageSelectionConfig = field(default_factory=StorageSelectionConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)

    def resolve_root(self, config_file_dir: Optional[Path] = None) -> Path:
        """Resolve backup root path with project-relative fallback.
        
        Resolution order:
        1. Absolute path → use as-is
        2. Starts with ~ → expand user home
        3. Relative path → resolve against:
           a. Config file directory (if loaded from file)
           b. Project root (where pyproject.toml or .git exists)
           c. Current working directory (fallback)
        """
        root = self.root
        if root.is_absolute():
            return root.expanduser()
        
        # Handle tilde expansion
        if str(root).startswith('~'):
            return Path(root).expanduser()
        
        # Relative path - try to resolve against project root
        base_dirs = []
        
        # 1. Config file directory
        if config_file_dir and config_file_dir.exists():
            base_dirs.append(config_file_dir)
        
        # 2. Project root (look for pyproject.toml or .git)
        project_root = self._find_project_root()
        if project_root:
            base_dirs.append(project_root)
        
        # 3. Current working directory
        base_dirs.append(Path.cwd())
        
        for base in base_dirs:
            candidate = (base / root).resolve()
            if candidate.exists() or base in base_dirs[:-1]:  # Allow creating in project root
                return candidate
        
        # Fallback to current working directory
        return (Path.cwd() / root).resolve()
    
    def _find_project_root(self) -> Optional[Path]:
        """Find project root by looking for pyproject.toml or .git."""
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / 'pyproject.toml').exists() or (parent / '.git').exists():
                return parent
        return None


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

        config_file_dir = config_path.parent if config_path.exists() else None

        if config_path.exists():
            try:
                with config_path.open('rb') as f:
                    data = tomllib.load(f)

                if 'backup' in data:
                    b = data['backup']
                    config.backup.root = Path(b.get('root', config.backup.root))
                    config.backup.adb_timeout = b.get('adb_timeout', config.backup.adb_timeout)
                    config.backup.max_retries = b.get('max_retries', config.backup.max_retries)
                    
                    if 'package_selection' in b:
                        ps = b['package_selection']
                        config.backup.package_selection.include_patterns = ps.get('include_patterns', [])
                        config.backup.package_selection.exclude_patterns = ps.get('exclude_patterns', [])
                        config.backup.package_selection.fetch_display_names = ps.get('fetch_display_names', True)
                    
                    if 'storage_selection' in b:
                        ss = b['storage_selection']
                        config.backup.storage_selection.include_folders = ss.get('include_folders', [])
                        config.backup.storage_selection.exclude_folders = ss.get('exclude_folders', [])
                        # custom_folders as list of [remote, local] pairs
                        custom = ss.get('custom_folders', [])
                        config.backup.storage_selection.custom_folders = [tuple(c) for c in custom]
                    
                    if 'schedule' in b:
                        s = b['schedule']
                        config.backup.schedule.enabled = s.get('enabled', False)
                        config.backup.schedule.cron_expression = s.get('cron_expression', '')
                        config.backup.schedule.run_at_startup = s.get('run_at_startup', False)
                        config.backup.schedule.run_interval_hours = s.get('run_interval_hours', 0)

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

        # Resolve the backup root path with project-relative fallback
        config.backup.root = config.backup.resolve_root(config_file_dir)

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
                'package_selection': {
                    'include_patterns': self.backup.package_selection.include_patterns,
                    'exclude_patterns': self.backup.package_selection.exclude_patterns,
                    'fetch_display_names': self.backup.package_selection.fetch_display_names,
                },
                'storage_selection': {
                    'include_folders': self.backup.storage_selection.include_folders,
                    'exclude_folders': self.backup.storage_selection.exclude_folders,
                    'custom_folders': [list(c) for c in self.backup.storage_selection.custom_folders],
                },
                'schedule': {
                    'enabled': self.backup.schedule.enabled,
                    'cron_expression': self.backup.schedule.cron_expression,
                    'run_at_startup': self.backup.schedule.run_at_startup,
                    'run_interval_hours': self.backup.schedule.run_interval_hours,
                },
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
                "[backup.package_selection]",
                f"include_patterns = {self.backup.package_selection.include_patterns}",
                f"exclude_patterns = {self.backup.package_selection.exclude_patterns}",
                f"fetch_display_names = {str(self.backup.package_selection.fetch_display_names).lower()}",
                "",
                "[backup.storage_selection]",
                f"include_folders = {self.backup.storage_selection.include_folders}",
                f"exclude_folders = {self.backup.storage_selection.exclude_folders}",
                f"custom_folders = {[list(c) for c in self.backup.storage_selection.custom_folders]}",
                "",
                "[backup.schedule]",
                f"enabled = {str(self.backup.schedule.enabled).lower()}",
                f"cron_expression = \"{self.backup.schedule.cron_expression}\"",
                f"run_at_startup = {str(self.backup.schedule.run_at_startup).lower()}",
                f"run_interval_hours = {self.backup.schedule.run_interval_hours}",
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

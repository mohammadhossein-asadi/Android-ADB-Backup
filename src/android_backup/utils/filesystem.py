"""Cross-platform filesystem utilities."""

import os
from pathlib import Path
from typing import Union


def ensure_dir(path: Union[str, Path]) -> Path:
    """Create directory if it doesn't exist, return Path."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(name: str) -> str:
    """Sanitize string for use as filename/directory name."""
    # Replace invalid characters with underscore
    invalid = '<>:"/\\|?*'
    for ch in invalid:
        name = name.replace(ch, '_')
    # Remove control characters
    name = ''.join(ch for ch in name if ord(ch) >= 32)
    return name.strip('. ')


def get_backup_root() -> Path:
    """Get default backup root directory."""
    # Use ~/AndroidBackups on all platforms
    return Path.home() / "AndroidBackups"


def get_config_dir() -> Path:
    """Get configuration directory following XDG spec."""
    if os.name == 'nt':  # Windows
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    else:  # macOS, Linux
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    return base / 'android-backup'


def find_adb_candidates() -> list[Path]:
    """Get platform-specific ADB search paths."""
    candidates = []
    script_dir = Path(__file__).parent.parent.parent.parent  # project root

    # 1. Next to script / in project root
    candidates.append(script_dir / ('adb.exe' if os.name == 'nt' else 'adb'))
    candidates.append(script_dir / 'platform-tools' / ('adb.exe' if os.name == 'nt' else 'adb'))

    # 2. Platform-specific common locations
    if os.name == 'nt':  # Windows
        localappdata = Path(os.environ.get('LOCALAPPDATA', ''))
        if localappdata:
            candidates.append(localappdata / 'Android' / 'Sdk' / 'platform-tools' / 'adb.exe')
        # Also check Program Files
        for pf in [os.environ.get('PROGRAMFILES', ''), os.environ.get('PROGRAMFILES(X86)', '')]:
            if pf:
                candidates.append(Path(pf) / 'Android' / 'android-sdk' / 'platform-tools' / 'adb.exe')
    else:  # macOS, Linux
        home = Path.home()
        candidates.append(home / 'Library' / 'Android' / 'sdk' / 'platform-tools' / 'adb')  # macOS
        candidates.append(home / 'Android' / 'Sdk' / 'platform-tools' / 'adb')  # Linux
        candidates.append(Path('/opt/homebrew/bin/adb'))  # macOS ARM Homebrew
        candidates.append(Path('/usr/local/bin/adb'))  # Linux/macOS Intel Homebrew
        candidates.append(Path('/usr/bin/adb'))  # Linux package manager

    # 3. PATH (will be checked by shutil.which)
    return [c for c in candidates if c and c.parent.exists()]


def format_bytes(bytes_value: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format duration as human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m"


def format_speed(bytes_per_sec: float) -> str:
    """Format transfer speed."""
    return f"{format_bytes(bytes_per_sec)}/s"

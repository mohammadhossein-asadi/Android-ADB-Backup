"""ADB discovery - find ADB executable across platforms."""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..utils import find_adb_candidates
from ..exceptions import ADBNotFoundError


class ADBDiscovery:
    """Cross-platform ADB executable discovery."""

    def __init__(self, preferred_path: Optional[str] = None):
        self.preferred_path = Path(preferred_path) if preferred_path else None
        self._cached_path: Optional[Path] = None

    def find(self) -> Path:
        """Find ADB executable, raise ADBNotFoundError if not found."""
        if self._cached_path:
            return self._cached_path

        # 1. Check preferred path from config
        if self.preferred_path and self.preferred_path.exists():
            self._cached_path = self.preferred_path
            return self._cached_path

        # 2. Check PATH via shutil.which
        adb_name = 'adb.exe' if shutil.which('adb.exe') else 'adb'
        path_adb = shutil.which(adb_name)
        if path_adb:
            self._cached_path = Path(path_adb)
            return self._cached_path

        # 3. Check platform-specific candidates
        for candidate in find_adb_candidates():
            if candidate.exists():
                self._cached_path = candidate
                return self._cached_path

        # 4. Not found
        raise ADBNotFoundError(
            "ADB executable not found. Please install Android Platform Tools "
            "and ensure 'adb' is in your PATH, or place adb.exe next to the executable."
        )

    def get_version(self, adb_path: Path) -> str:
        """Get ADB version string."""
        try:
            result = subprocess.run(
                [str(adb_path), 'version'],
                capture_output=True,
                text=True,
                timeout=10,
                encoding='utf-8',
                errors='replace'
            )
            if result.returncode == 0 and result.stdout:
                # Parse version from output like "Android Debug Bridge version 1.0.41"
                for line in result.stdout.splitlines():
                    if 'version' in line.lower():
                        return line.strip()
            return "unknown"
        except (subprocess.SubprocessError, OSError):
            return "unknown"
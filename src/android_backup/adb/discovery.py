"""ADB discovery - find ADB executable across platforms, with automatic setup."""

import os
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from ..exceptions import ADBNotFoundError
from ..utils import (
    find_adb_candidates,
    get_adb_cache_dir,
    get_cached_adb_path,
    get_platform_tools_url,
)

ProgressCallback = Callable[[int, int], None]

MANUAL_INSTALL_HINT = (
    "ADB executable not found. "
    "Automatic download failed or is disabled. "
    "Install Android Platform Tools from https://developer.android.com/tools/releases/platform-tools "
    "and ensure 'adb' is in your PATH, or place adb.exe next to the executable, "
    "or pass --adb-path <path>."
)


class ADBDiscovery:
    """Cross-platform ADB executable discovery with auto-install."""

    def __init__(
        self,
        preferred_path: Optional[str] = None,
        auto_install: bool = True,
    ):
        self.preferred_path = Path(preferred_path).expanduser() if preferred_path else None
        self.auto_install = auto_install
        self._cached_path: Optional[Path] = None

    def find(self, auto_install: Optional[bool] = None) -> Path:
        """Find ADB executable, optionally auto-downloading platform-tools."""
        if self._cached_path and self._cached_path.exists():
            return self._cached_path

        should_auto = self.auto_install if auto_install is None else auto_install
        # Env override: ANDROID_BACKUP_NO_AUTO_ADB=1 disables auto download
        if os.environ.get("ANDROID_BACKUP_NO_AUTO_ADB", "").strip() in ("1", "true", "yes"):
            should_auto = False

        # 1. Preferred path from config / CLI
        if self.preferred_path and self.preferred_path.exists():
            self._cached_path = self.preferred_path
            return self._cached_path

        # 2. Previously auto-downloaded copy (fast path, no network)
        cached = get_cached_adb_path()
        if cached.exists():
            self._cached_path = cached
            return self._cached_path

        # 3. PATH via shutil.which
        for name in ("adb.exe", "adb") if os.name == "nt" else ("adb",):
            path_adb = shutil.which(name)
            if path_adb:
                self._cached_path = Path(path_adb)
                return self._cached_path

        # 4. Platform-specific candidates
        for candidate in find_adb_candidates():
            try:
                if candidate.exists():
                    self._cached_path = candidate
                    return self._cached_path
            except OSError:
                continue

        # 5. Automatic download from Google
        if should_auto:
            try:
                downloaded = self.download_platform_tools()
                if downloaded.exists():
                    self._cached_path = downloaded
                    return self._cached_path
            except Exception as exc:  # noqa: BLE001 - surface as ADBNotFoundError below
                raise ADBNotFoundError(f"{MANUAL_INSTALL_HINT} (auto-download failed: {exc})") from exc

        raise ADBNotFoundError(MANUAL_INSTALL_HINT)

    def ensure(self, auto_install: Optional[bool] = None) -> Path:
        """Alias for find() kept for readability at call sites."""
        return self.find(auto_install=auto_install)

    def download_platform_tools(self, progress: Optional[ProgressCallback] = None) -> Path:
        """Download and extract Google platform-tools, return adb path."""
        _os_key, url = get_platform_tools_url()
        cache_dir = get_adb_cache_dir()
        cache_dir.parent.mkdir(parents=True, exist_ok=True)

        # Reuse existing valid copy
        cached_adb = get_cached_adb_path()
        if cached_adb.exists() and self._looks_like_adb(cached_adb):
            return cached_adb

        with tempfile.TemporaryDirectory(prefix="android-backup-adb-") as tmp:
            zip_path = Path(tmp) / "platform-tools.zip"
            self._download_file(url, zip_path, progress=progress)
            extract_root = Path(tmp) / "extracted"
            extract_root.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_root)

            # Google zips contain top-level `platform-tools/` folder
            src_dir = extract_root / "platform-tools"
            if not src_dir.exists():
                # Fallback: find nested adb binary
                found = list(extract_root.rglob("adb.exe" if os.name == "nt" else "adb"))
                if not found:
                    raise FileNotFoundError("platform-tools archive did not contain adb")
                src_dir = found[0].parent

            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
            shutil.copytree(src_dir, cache_dir)

        adb_path = get_cached_adb_path()
        if os.name != "nt":
            try:
                adb_path.chmod(adb_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            except OSError:
                pass

        if not self._looks_like_adb(adb_path):
            raise FileNotFoundError(f"Downloaded ADB is not usable: {adb_path}")

        return adb_path

    def _download_file(self, url: str, dest: Path, progress: Optional[ProgressCallback] = None) -> None:
        req = urllib.request.Request(url, headers={"User-Agent": "android-adb-backup/2.1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp, dest.open("wb") as out:
            total = resp.headers.get("Content-Length")
            total_int = int(total) if total and total.isdigit() else 0
            downloaded = 0
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if progress:
                    progress(downloaded, total_int)

    def _looks_like_adb(self, adb_path: Path) -> bool:
        try:
            result = subprocess.run(
                [str(adb_path), "version"],
                capture_output=True,
                text=True,
                timeout=15,
                encoding="utf-8",
                errors="replace",
            )
            output = f"{result.stdout}\n{result.stderr}".lower()
            return result.returncode == 0 and "android debug bridge" in output
        except (subprocess.SubprocessError, OSError):
            return False

    def get_version(self, adb_path: Path) -> str:
        """Get ADB version string."""
        try:
            result = subprocess.run(
                [str(adb_path), "version"],
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.splitlines():
                    if "version" in line.lower():
                        return line.strip()
            return "unknown"
        except (subprocess.SubprocessError, OSError):
            return "unknown"

"""Package and APK backup module."""

import asyncio
import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..adb import ADBCommands
from ..utils import validate_apk
from .state import APKEntry, PackageEntry


@dataclass
class PullResult:
    """Result of APK pull operation."""
    success: bool
    local_path: Path
    remote_path: str
    size: int
    sha256: str
    attempts: int
    error: str = ""


class PackageBackup:
    """Handle package listing and APK backup."""

    def __init__(
        self,
        commands: ADBCommands,
        max_retries: int = 3,
        adb_timeout: int = 120,
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
        fetch_display_names: bool = True
    ):
        self.commands = commands
        self.max_retries = max_retries
        self.adb_timeout = adb_timeout
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        self.fetch_display_names = fetch_display_names

    def _should_backup_package(self, package: str) -> bool:
        """Check if a package should be backed up based on include/exclude patterns."""
        # If include patterns specified, package must match at least one
        if self.include_patterns:
            matched = any(fnmatch.fnmatch(package, pattern) for pattern in self.include_patterns)
            if not matched:
                return False
        # If exclude patterns specified, package must not match any
        if self.exclude_patterns:
            if any(fnmatch.fnmatch(package, pattern) for pattern in self.exclude_patterns):
                return False
        return True

    async def _fetch_display_name(self, serial: str, package: str) -> str:
        """Fetch display name for a package."""
        if not self.fetch_display_names:
            return ""
        try:
            return await self.commands.get_package_display_name(serial, package)
        except Exception:
            return ""

    async def list_packages(self, serial: str) -> tuple[list[str], list[str], list[str]]:
        """List all, third-party, and system packages."""
        all_pkgs = await self.commands.list_packages(serial)
        third_party = await self.commands.list_packages(serial, third_party=True)
        system = await self.commands.list_packages(serial, system=True)
        return all_pkgs, third_party, system

    async def pull_apk_with_retry(
        self,
        serial: str,
        remote_path: str,
        local_path: Path
    ) -> PullResult:
        """Pull APK with retry logic."""
        local_path.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, self.max_retries + 1):
            if attempt > 1:
                await asyncio.sleep(2 * (attempt - 1))  # Exponential backoff

            # Remove incomplete previous attempt
            if local_path.exists():
                local_path.unlink()

            result = await self.commands.pull_file(serial, remote_path, local_path, self.adb_timeout)

            if result.success and local_path.exists():
                valid, sha256, size = validate_apk(local_path)
                if valid:
                    return PullResult(
                        success=True,
                        local_path=local_path,
                        remote_path=remote_path,
                        size=size,
                        sha256=sha256 or "",
                        attempts=attempt
                    )

            error = result.stderr or f"exit {result.returncode}"
            if attempt == self.max_retries:
                return PullResult(
                    success=False,
                    local_path=local_path,
                    remote_path=remote_path,
                    size=0,
                    sha256="",
                    attempts=attempt,
                    error=error
                )

        return PullResult(
            success=False,
            local_path=local_path,
            remote_path=remote_path,
            size=0,
            sha256="",
            attempts=self.max_retries,
            error="Max retries exceeded"
        )

    async def backup_package(
        self,
        serial: str,
        package: str,
        apks_dir: Path,
        state_entry: Optional[PackageEntry] = None
    ) -> PackageEntry:
        """Backup a single package (all its APKs)."""
        # Check if package should be backed up
        if not self._should_backup_package(package):
            return PackageEntry(
                status="SKIP",
                message="Package excluded by filter"
            )

        # Get remote APK paths
        remote_paths = await self.commands.get_package_paths(serial, package)

        if not remote_paths:
            return PackageEntry(
                status="FAILED",
                message="pm path returned nothing"
            )

        # Fetch display name
        display_name = await self._fetch_display_name(serial, package)

        entry = PackageEntry(status="PENDING", display_name=display_name)
        pkg_dir = apks_dir / package
        pkg_dir.mkdir(parents=True, exist_ok=True)

        manifest_lines = ["File,RemotePath,SizeBytes,SHA256"]
        all_ok = True

        for idx, remote in enumerate(remote_paths):
            # Determine local filename
            remote_name = Path(remote).name
            if not remote_name or not remote_name.endswith('.apk'):
                remote_name = f"apk_{idx + 1}.apk"

            # Use base.apk for first/base, keep original for splits
            if idx == 0 or remote_name == 'base.apk':
                local_name = 'base.apk'
            else:
                local_name = remote_name

            local_path = pkg_dir / local_name

            # Check if already valid (resume)
            if state_entry and local_path.exists():
                valid, sha256, size = validate_apk(local_path)
                if valid:
                    entry.apks.append(APKEntry(
                        file=local_name,
                        remote=remote,
                        size=size,
                        sha256=sha256,
                        success=True
                    ))
                    manifest_lines.append(f"{local_name},{remote},{size},{sha256}")
                    continue

            # Pull APK
            pull_result = await self.pull_apk_with_retry(serial, remote, local_path)

            if pull_result.success:
                entry.apks.append(APKEntry(
                    file=local_name,
                    remote=pull_result.remote_path,
                    size=pull_result.size,
                    sha256=pull_result.sha256,
                    success=True
                ))
                manifest_lines.append(f"{local_name},{pull_result.remote_path},{pull_result.size},{pull_result.sha256}")
            else:
                entry.apks.append(APKEntry(
                    file=local_name,
                    remote=remote,
                    size=0,
                    sha256="",
                    success=False
                ))
                all_ok = False

        # Write package dump and manifest
        dump_file = pkg_dir / 'package_dump.txt'
        dump_file.write_text(
            f"Package={package}\nRemotePaths:\n" + '\n'.join(remote_paths),
            encoding='utf-8'
        )

        manifest_file = pkg_dir / 'APK_Manifest.csv'
        manifest_file.write_text('\n'.join(manifest_lines), encoding='utf-8')

        entry.status = "OK" if all_ok else "FAILED"
        if not all_ok:
            entry.message = "One or more APKs failed"

        return entry

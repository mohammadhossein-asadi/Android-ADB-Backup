"""ADB command helpers - typed wrappers for common ADB operations."""

from pathlib import Path

from .client import ADBClient, ADBResult


class ADBCommands:
    """High-level ADB command wrappers."""

    def __init__(self, client: ADBClient):
        self.client = client

    async def list_packages(self, serial: str, third_party: bool = False, system: bool = False) -> list[str]:
        """List installed packages."""
        args = ['pm', 'list', 'packages']
        if third_party:
            args.append('-3')
        elif system:
            args.append('-s')

        result = await self.client.run_shell(serial, *args)
        packages = []
        if result.success:
            for line in result.output_lines:
                if line.startswith('package:'):
                    packages.append(line[8:].strip())
        return packages

    async def get_package_paths(self, serial: str, package: str) -> list[str]:
        """Get APK paths for a package."""
        result = await self.client.run_shell(serial, 'pm', 'path', package)
        paths = []
        if result.success:
            for line in result.output_lines:
                if line.startswith('package:'):
                    paths.append(line[8:].strip())
        return paths

    async def get_device_properties(self, serial: str) -> dict[str, str]:
        """Get all relevant device properties."""
        props = [
            'ro.product.manufacturer',
            'ro.product.model',
            'ro.product.device',
            'ro.product.name',
            'ro.build.version.release',
            'ro.build.version.sdk',
            'ro.product.cpu.abi',
            'ro.product.cpu.abilist',
            'ro.build.display.id',
            'ro.build.fingerprint',
            'ro.bootloader',
            'ro.build.version.security_patch',
        ]

        result = {}
        for prop in props:
            r = await self.client.run_shell(serial, 'getprop', prop)
            if r.success and r.stdout.strip():
                result[prop] = r.stdout.strip()
            else:
                result[prop] = ""
        return result

    async def check_remote_exists(self, serial: str, path: str) -> bool:
        """Check if remote path exists."""
        result = await self.client.run_shell(serial, 'ls', '-d', path)
        return result.success and result.stdout.strip() != ""

    async def pull_file(
        self,
        serial: str,
        remote: str,
        local: Path,
        timeout: int = 300
    ) -> ADBResult:
        """Pull a single file with retry logic handled by caller."""
        return await self.client.pull(serial, remote, local, timeout=timeout)

    async def pull_folder(
        self,
        serial: str,
        remote: str,
        local: Path,
        timeout: int = 600
    ) -> ADBResult:
        """Pull a folder recursively."""
        return await self.client.pull(serial, remote, str(local), timeout=timeout)

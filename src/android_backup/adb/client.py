"""ADB client - async subprocess wrapper with timeout and retries."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ADBResult:
    """Result of an ADB command."""
    success: bool
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False

    @property
    def output_lines(self) -> list[str]:
        """Get stdout as list of non-empty lines."""
        return [line for line in self.stdout.splitlines() if line.strip()]

    @property
    def error_lines(self) -> list[str]:
        """Get stderr as list of non-empty lines."""
        return [line for line in self.stderr.splitlines() if line.strip()]


class ADBClient:
    """Async ADB client with timeout, retries, and structured results."""

    def __init__(self, adb_path: Path, default_timeout: int = 120):
        self.adb_path = adb_path
        self.default_timeout = default_timeout

    async def run(
        self,
        *args: str,
        timeout: Optional[int] = None,
        serial: Optional[str] = None
    ) -> ADBResult:
        """Run ADB command with optional device serial."""
        cmd_args = [str(self.adb_path)]
        if serial:
            cmd_args.extend(['-s', serial])
        cmd_args.extend(args)

        return await self._run_command(cmd_args, timeout or self.default_timeout)

    async def run_shell(
        self,
        serial: str,
        *args: str,
        timeout: Optional[int] = None
    ) -> ADBResult:
        """Run ADB shell command on device."""
        return await self.run('shell', *args, timeout=timeout, serial=serial)

    async def pull(
        self,
        serial: str,
        remote: str,
        local: Path,
        timeout: Optional[int] = None
    ) -> ADBResult:
        """Pull file/folder from device."""
        # Ensure local parent directory exists
        local.parent.mkdir(parents=True, exist_ok=True)
        return await self.run('pull', remote, str(local), timeout=timeout or 300, serial=serial)

    async def _run_command(self, cmd_args: list[str], timeout: int) -> ADBResult:
        """Execute command with timeout."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024  # 1MB buffer
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
                return ADBResult(
                    success=proc.returncode == 0,
                    stdout=stdout.decode('utf-8', errors='replace'),
                    stderr=stderr.decode('utf-8', errors='replace'),
                    returncode=proc.returncode or 0
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ADBResult(
                    success=False,
                    stdout="",
                    stderr=f"Command timed out after {timeout}s",
                    returncode=-1,
                    timed_out=True
                )

        except (OSError, asyncio.SubprocessError) as e:
            return ADBResult(
                success=False,
                stdout="",
                stderr=str(e),
                returncode=-2
            )

    async def get_version(self) -> str:
        """Get ADB version."""
        result = await self.run('version')
        if result.success and result.stdout:
            for line in result.stdout.splitlines():
                if 'version' in line.lower():
                    return line.strip()
        return "unknown"

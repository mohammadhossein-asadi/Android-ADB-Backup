"""Device info backup module."""

from pathlib import Path

from ..adb import ADBCommands


class DeviceInfoBackup:
    """Collect and save device information."""

    def __init__(self, commands: ADBCommands):
        self.commands = commands

    async def collect(self, serial: str) -> dict[str, str]:
        """Collect all device properties."""
        return await self.commands.get_device_properties(serial)

    def save(self, backup_dir: Path, device_info: dict[str, str], serial: str) -> None:
        """Save device info to file."""
        info_dir = backup_dir / 'Device_Info'
        info_dir.mkdir(parents=True, exist_ok=True)

        info_file = info_dir / 'device_info.txt'
        lines = [f"Serial={serial}"]
        for key, value in sorted(device_info.items()):
            lines.append(f"{key}={value}")

        info_file.write_text('\n'.join(lines), encoding='utf-8')

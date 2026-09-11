"""Device detection and selection."""

from dataclasses import dataclass
from typing import Optional

from .client import ADBClient, ADBResult


@dataclass
class Device:
    """ADB device information."""
    serial: str
    state: str  # 'device', 'unauthorized', 'offline', etc.
    model: str = ""
    product: str = ""

    @property
    def is_ready(self) -> bool:
        """Check if device is ready for commands."""
        return self.state == 'device'

    @property
    def display_name(self) -> str:
        """Get display name for UI."""
        if self.model:
            return f"{self.model} ({self.serial})"
        return self.serial


class DeviceManager:
    """Manage ADB device detection and selection."""

    def __init__(self, client: ADBClient):
        self.client = client

    async def list_devices(self) -> list[Device]:
        """List all connected devices."""
        result = await self.client.run('devices')
        devices = []

        if not result.success:
            return devices

        for line in result.output_lines:
            if line.startswith('List of devices'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                serial, state = parts[0], parts[1].lower()
                device = Device(serial=serial, state=state)
                devices.append(device)

        return devices

    async def get_ready_devices(self) -> list[Device]:
        """Get only ready (authorized) devices."""
        devices = await self.list_devices()
        return [d for d in devices if d.is_ready]

    async def get_device_info(self, serial: str) -> Device:
        """Get detailed device information."""
        device = Device(serial=serial, state='device')

        # Get model and product
        props = await self._get_properties(serial, [
            'ro.product.model',
            'ro.product.name',
            'ro.product.device',
            'ro.build.version.release',
            'ro.build.version.sdk',
        ])

        device.model = props.get('ro.product.model', '')
        device.product = props.get('ro.product.name', '')

        return device

    async def _get_properties(self, serial: str, props: list[str]) -> dict[str, str]:
        """Get multiple device properties."""
        result = {}
        for prop in props:
            r = await self.client.run_shell(serial, 'getprop', prop)
            if r.success and r.stdout.strip():
                result[prop] = r.stdout.strip()
            else:
                result[prop] = ""
        return result

    async def select_device(
        self,
        preferred_serial: Optional[str] = None,
        interactive: bool = True
    ) -> Optional[Device]:
        """Select device for backup."""
        # Start ADB server
        await self.client.run('start-server')
        await asyncio.sleep(0.5)

        ready_devices = await self.get_ready_devices()

        if not ready_devices:
            return None

        # Check preferred serial
        if preferred_serial:
            for device in ready_devices:
                if device.serial == preferred_serial:
                    return device

        # Single device - auto-select
        if len(ready_devices) == 1:
            return ready_devices[0]

        # Multiple devices - need selection
        if not interactive:
            return None

        # Would be handled by UI layer
        return None
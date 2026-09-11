"""Interactive prompts for device selection, confirmations."""

from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.text import Text
from typing import Optional, List

from .console import console
from ..adb import Device


def select_device(devices: List[Device], preferred: Optional[str] = None) -> Optional[Device]:
    """Interactive device selection."""
    if not devices:
        return None

    if len(devices) == 1:
        console.print(f"[info]Single device found: [package]{devices[0].display_name}[/]")
        return devices[0]

    # Check preferred
    if preferred:
        for d in devices:
            if d.serial == preferred:
                console.print(f"[info]Using preferred device: [package]{d.display_name}[/]")
                return d

    # Interactive selection
    console.print("\n[primary]Multiple devices detected:[/]\n")
    for i, device in enumerate(devices, 1):
        console.print(f"  [secondary]{i}[/]) [package]{device.display_name}[/]")

    while True:
        choice = Prompt.ask(
            "\n[primary]Select device[/]",
            choices=[str(i) for i in range(1, len(devices) + 1)] + [d.serial for d in devices],
            show_choices=False
        )

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx]
        else:
            for d in devices:
                if d.serial == choice:
                    return d

        console.print("[error]Invalid selection. Try again.[/]")


def confirm_resume(backup_path: str) -> bool:
    """Confirm resume of incomplete backup."""
    return Confirm.ask(
        f"[warning]Found incomplete backup at:[/] [path]{backup_path}[/]\n[primary]Resume?[/]",
        default=True
    )


def confirm_full_sdcard() -> bool:
    """Confirm full /sdcard backup."""
    console.print(Panel(
        Text("[warning]Full /sdcard backup can be very large and take a long time.[/]", justify="center"),
        border_style="warning",
        title="[panel.title]Warning",
    ))
    return Confirm.ask("[primary]Proceed with full /sdcard pull?[/]", default=False)


def prompt_device_serial() -> Optional[str]:
    """Prompt for device serial."""
    serial = Prompt.ask("[primary]Enter device serial (or press Enter for auto-detect)[/]", default="")
    return serial if serial else None
"""Report generator - text report and CSV inventory."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from ..backup.state import BackupState


class ReportGenerator:
    """Generate backup reports."""

    def __init__(self, backup_dir: Path):
        self.backup_dir = backup_dir
        self.reports_dir = backup_dir / 'Reports'
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_text_report(
        self,
        state: BackupState,
        end_time: datetime,
        start_time: datetime
    ) -> Path:
        """Generate human-readable text report."""
        duration = end_time - start_time
        total_mb = state.stats.total_bytes / (1024 * 1024)

        lines = [
            "============================================================",
            " Android ADB Backup Report",
            f" Version: {state.version}",
            "============================================================",
            "",
            "IMPORTANT LIMITATIONS",
            "--------------------",
            "This is an ADB application/file backup, NOT a full ROM or partition dump.",
            "Without root/recovery/fastboot, modern Android does not expose:",
            "  /data/data, /data/user, /system, /vendor, /product, /boot, userdata, etc.",
            "Only APKs, package metadata, device props, and accessible /sdcard paths are backed up.",
            "",
            "DEVICE",
            "------",
        ]

        for key, value in state.device_info.items():
            if value:
                lines.append(f"  {key}: {value}")

        lines.extend([
            "",
            "BACKUP",
            "------",
            f"  Destination : {state.backup_dir}",
            f"  Started     : {state.started}",
            f"  Finished    : {end_time.isoformat()}",
            f"  Duration    : {int(duration.total_seconds() // 60)}m {int(duration.total_seconds() % 60)}s",
            "",
            "STATISTICS",
            "----------",
            f"  Packages total   : {state.stats.total_packages}",
            f"  Packages success : {state.stats.success_packages}",
            f"  Packages failed  : {state.stats.failed_packages}",
            f"  Packages skipped : {state.stats.skipped_packages}",
            f"  APKs total       : {state.stats.total_apks}",
            f"  APKs success     : {state.stats.success_apks}",
            f"  APKs failed      : {state.stats.failed_apks}",
            f"  Total size       : {total_mb:.2f} MB ({state.stats.total_bytes} bytes)",
            "",
            "RESTORE",
            "-------",
            "  Scripts: Restore/Restore_Apps.sh/.bat  and  Restore/Restore_Files.sh/.bat",
            "  Restore does NOT uninstall apps or wipe data.",
            "",
            "LOGS",
            "----",
            "  Logs/backup_run.log",
            "  Logs/errors.log",
            "",
            "SAFETY",
            "------",
            "  This tool never factory-resets, unlocks bootloader, flashes, erases,",
            "  or modifies /system, /vendor, /product, /data, or bootloader settings.",
            "",
        ])

        report_path = self.reports_dir / 'Backup_Report.txt'
        report_path.write_text('\n'.join(lines), encoding='utf-8')
        return report_path

    def generate_csv_inventory(self, state: BackupState) -> Path:
        """Generate CSV inventory of packages."""
        csv_path = self.reports_dir / 'Application_Inventory.csv'

        with csv_path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Package', 'Status', 'ApkCount', 'SuccessApks', 'FailedApks', 'Notes'])

            for package in sorted(state.packages.keys()):
                entry = state.packages[package]
                apk_count = len(entry.apks)
                success = sum(1 for a in entry.apks if a.success)
                failed = sum(1 for a in entry.apks if not a.success)
                notes = entry.message.replace(',', ';') if entry.message else ""

                # CSV injection protection
                if package.startswith(('=', '+', '-', '@')):
                    package = "'" + package
                if notes.startswith(('=', '+', '-', '@')):
                    notes = "'" + notes

                writer.writerow([package, entry.status, apk_count, success, failed, notes])

        return csv_path
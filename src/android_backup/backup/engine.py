"""Main backup orchestration engine."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.table import Table

from ..adb import ADBClient, ADBCommands, ADBDiscovery, DeviceManager
from ..backup import (
    BackupState,
    PackageBackup,
    StateManager,
    StorageBackup,
)
from ..config import Config
from ..exceptions import (
    ADBNotFoundError,
    BackupDirectoryError,
    DeviceUnauthorizedError,
    NoDeviceError,
    StateError,
)
from ..report import ReportGenerator
from ..restore import RestoreGenerator
from ..ui import (
    BackupProgress,
    confirm_resume,
    console,
    create_failed_packages_table,
    create_final_summary_table,
)
from ..utils import format_duration


class BackupEngine:
    """Main backup orchestration engine."""

    def __init__(self, config: Config, whatif: bool = False, verify_only: bool = False):
        self.config = config
        self.whatif = whatif
        self.verify_only = verify_only
        self.logger = self._setup_logging()

        # Will be initialized in run()
        self.adb_path: Optional[Path] = None
        self.client: Optional[ADBClient] = None
        self.commands: Optional[ADBCommands] = None
        self.device_manager: Optional[DeviceManager] = None
        self.serial: Optional[str] = None
        self.backup_dir: Optional[Path] = None
        self.state_manager: Optional[StateManager] = None
        self.state: Optional[BackupState] = None
        self.progress: Optional[BackupProgress] = None
        self.start_time: Optional[datetime] = None
        self.failed_packages: list[tuple[str, str]] = []

    def _setup_logging(self) -> logging.Logger:
        """Setup logging."""
        logger = logging.getLogger('android_backup')
        logger.setLevel(logging.DEBUG)

        # File handler will be added when backup_dir is known
        return logger

    def _setup_file_logging(self) -> None:
        """Setup file logging after backup_dir is known."""
        log_dir = self.backup_dir / 'Logs'
        log_dir.mkdir(parents=True, exist_ok=True)

        # Run log
        run_handler = logging.FileHandler(log_dir / 'backup_run.log', encoding='utf-8')
        run_handler.setLevel(logging.INFO)
        run_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s'))

        # Error log
        err_handler = logging.FileHandler(log_dir / 'errors.log', encoding='utf-8')
        err_handler.setLevel(logging.ERROR)
        err_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s'))

        self.logger.addHandler(run_handler)
        self.logger.addHandler(err_handler)

    async def run(self) -> int:
        """Run the backup process."""
        self.start_time = datetime.now()

        try:
            # 1. Discover ADB
            await self._discover_adb()

            # 2. Select device
            await self._select_device()

            # 3. Setup backup directory
            await self._setup_backup_dir()

            # 4. Setup logging
            self._setup_file_logging()

            # 5. Initialize progress UI
            if not self.whatif and not self.verify_only:
                self.progress = BackupProgress()
                self.progress.start()

            # 6. Collect device info
            device_info = await self._collect_device_info()

            # 7. Handle resume
            await self._handle_resume(device_info)

            # 8. Run backup or verify
            if self.verify_only:
                await self._verify_backup()
            elif self.whatif:
                await self._dry_run()
            else:
                await self._run_backup()

            # 9. Generate reports and restore scripts
            if not self.whatif:
                await self._finalize()

            # 10. Show final summary
            self._show_final_summary()

            return 0

        except KeyboardInterrupt:
            console.print("\n[warning]Backup interrupted by user[/]")
            return 130
        except ADBNotFoundError as e:
            console.print(f"[error]{e.message}[/]")
            return e.exit_code
        except NoDeviceError as e:
            console.print(f"[error]{e.message}[/]")
            return e.exit_code
        except DeviceUnauthorizedError as e:
            console.print(f"[error]{e.message}[/]")
            return e.exit_code
        except BackupDirectoryError as e:
            console.print(f"[error]{e.message}[/]")
            return e.exit_code
        except StateError as e:
            console.print(f"[error]{e.message}[/]")
            return e.exit_code
        except Exception as e:
            self.logger.exception("Unexpected error")
            console.print(f"[error]Unexpected error: {e}[/]")
            return 1
        finally:
            if self.progress:
                self.progress.stop()

    async def _discover_adb(self) -> None:
        """Discover ADB executable."""
        discovery = ADBDiscovery(self.config.adb.preferred_path)
        self.adb_path = discovery.find()
        self.client = ADBClient(self.adb_path, self.config.backup.adb_timeout)
        self.commands = ADBCommands(self.client)
        self.device_manager = DeviceManager(self.client)

        version = await self.client.get_version()
        console.print(f"[info]Using ADB: [path]{self.adb_path}[/] ([secondary]{version}[/])")

    async def _select_device(self) -> None:
        """Select target device."""
        device = await self.device_manager.select_device(
            preferred_serial=None,  # Will be overridden by CLI
            interactive=True
        )

        if not device:
            raise NoDeviceError()

        if not device.is_ready:
            if device.state == 'unauthorized':
                raise DeviceUnauthorizedError(device.serial)
            elif device.state == 'offline':
                from ..exceptions import DeviceOfflineError
                raise DeviceOfflineError(device.serial)
            else:
                raise NoDeviceError(f"Device {device.serial} is in state '{device.state}'")

        self.serial = device.serial
        console.print(f"[info]Selected device: [package]{device.display_name}[/]")

    async def _collect_device_info(self) -> dict:
        """Collect device properties."""
        console.print("[info]Collecting device information...")
        return await self.commands.get_device_properties(self.serial)

    async def _setup_backup_dir(self) -> None:
        """Setup backup directory structure."""
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        model = self.state.device_info.get('ro.product.model', 'Unknown') if self.state else 'Unknown'
        safe_model = "".join(c if c.isalnum() or c in '._-' else '_' for c in model)

        # Use backup name from CLI or timestamp
        # This will be overridden by CLI args in main
        backup_name = f"Backup_{safe_model}_{timestamp}"

        self.backup_dir = self.config.backup.root / backup_name

        # Create subdirectories
        dirs = [
            'Device_Info',
            'APKs',
            'Packages',
            'Files/Internal_Storage',
            'Files/Full_Internal_Storage',
            'Reports',
            'Restore',
            'Logs',
        ]
        for d in dirs:
            (self.backup_dir / d).mkdir(parents=True, exist_ok=True)

        self.state_manager = StateManager(self.backup_dir)

    async def _handle_resume(self, device_info: dict) -> None:
        """Handle resume from previous backup."""
        # Find incomplete backups for this serial
        incomplete = self.state_manager.find_incomplete_backups(self.serial)

        if incomplete:
            latest = incomplete[0]
            loaded_state = self.state_manager.load()

            if loaded_state:
                console.print(f"[warning]Found incomplete backup: [path]{latest}[/]")
                if not self.config.ui.no_color:  # Would use force_resume flag
                    resume = confirm_resume(str(latest))
                else:
                    resume = True

                if resume:
                    self.backup_dir = latest
                    self.state = loaded_state
                    self.state.device_info = device_info  # Update with fresh info
                    self.state_manager = StateManager(self.backup_dir)
                    console.print("[success]Resuming previous backup...[/]")
                    return

        # New backup
        self.state = BackupState.create(self.serial, self.backup_dir, device_info)

    async def _run_backup(self) -> None:
        """Run the main backup process."""
        # Initialize backup modules
        pkg_backup = PackageBackup(
            self.commands,
            max_retries=self.config.backup.max_retries,
            adb_timeout=self.config.backup.adb_timeout
        )
        storage_backup = StorageBackup(self.commands, max_retries=2)

        # List packages
        console.print("[info]Listing packages...")
        all_pkgs, third_party, system_pkgs = await pkg_backup.list_packages(self.serial)

        # Save package lists
        pkg_dir = self.backup_dir / 'Packages'
        (pkg_dir / 'packages_all.txt').write_text('\n'.join(all_pkgs), encoding='utf-8')
        (pkg_dir / 'packages_third_party.txt').write_text('\n'.join(third_party), encoding='utf-8')
        (pkg_dir / 'packages_system.txt').write_text('\n'.join(system_pkgs), encoding='utf-8')

        self.state.stats.total_packages = len(third_party)

        if self.progress:
            self.progress.update_overall(0, len(third_party), "[primary]Backing up packages")

        # Backup each third-party package
        apks_dir = self.backup_dir / 'APKs'
        for idx, package in enumerate(third_party, 1):
            state_entry = self.state.packages.get(package)

            # Skip if already OK
            if state_entry and state_entry.status == "OK":
                if self.progress:
                    self.progress.increment_skip()
                    self.progress.update_overall(idx, len(third_party))
                    self.progress.update_package(idx, len(third_party), package)
                continue

            if self.progress:
                self.progress.update_package(idx, len(third_party), package)
                self.progress.update_overall(idx, len(third_party), "[primary]Backing up packages")

            # Backup package
            result = await pkg_backup.backup_package(
                self.serial,
                package,
                apks_dir,
                state_entry
            )

            self.state.packages[package] = result
            self.state.stats.total_apks += len(result.apks)

            if result.status == "OK":
                self.state.stats.success_packages += 1
                self.state.stats.success_apks += sum(1 for a in result.apks if a.success)
                self.state.stats.total_bytes += sum(a.size for a in result.apks if a.success)
                if self.progress:
                    self.progress.increment_ok()
            else:
                self.state.stats.failed_packages += 1
                self.state.stats.failed_apks += sum(1 for a in result.apks if not a.success)
                self.failed_packages.append((package, result.message))
                if self.progress:
                    self.progress.increment_fail()

            # Save state after each package
            self.state_manager.save(self.state)

        # Storage backup
        if not self.config.ui.no_color:  # Would use skip_storage flag
            console.print("[info]Starting storage backup...")
            storage_results = await storage_backup.backup_all(
                self.serial,
                self.backup_dir / 'Files',
                self.state.storage,
                full_sdcard=False,  # Would use full_sdcard flag
                confirm_full=False
            )
            self.state.storage.update(storage_results)
            self.state_manager.save(self.state)

        # Mark complete
        self.state.completed = True
        self.state_manager.save(self.state)

    async def _dry_run(self) -> None:
        """Dry-run mode - show what would be backed up."""
        pkg_backup = PackageBackup(self.commands)
        all_pkgs, third_party, system_pkgs = await pkg_backup.list_packages(self.serial)

        console.print(f"\n[primary]DRY RUN - Would backup {len(third_party)} packages:[/]\n")

        table = Table(title="Packages", border_style="panel.border")
        table.add_column("#", width=4)
        table.add_column("Package", style="package")
        table.add_column("APKs", justify="right")

        for i, pkg in enumerate(third_party, 1):
            paths = await self.commands.get_package_paths(self.serial, pkg)
            table.add_row(str(i), pkg, str(len(paths)))

        console.print(table)

    async def _verify_backup(self) -> None:
        """Verify existing backup integrity."""
        console.print("[info]Verifying backup integrity...")

        ok_count = 0
        fail_count = 0

        for package, entry in self.state.packages.items():
            pkg_dir = self.backup_dir / 'APKs' / package
            if not pkg_dir.exists():
                console.print(f"[failed]MISSING: {package} - no directory[/]")
                fail_count += 1
                continue

            pkg_ok = True
            for apk_entry in entry.apks:
                apk_path = pkg_dir / apk_entry.file
                if not apk_path.exists():
                    console.print(f"[failed]MISSING: {package}/{apk_entry.file}[/]")
                    pkg_ok = False
                    continue

                # Validate
                from ..utils import validate_apk
                valid, sha256, size = validate_apk(apk_path)
                if not valid:
                    console.print(f"[failed]INVALID: {package}/{apk_entry.file} - bad magic[/]")
                    pkg_ok = False
                    continue

                if sha256 != apk_entry.sha256:
                    console.print(f"[warning]HASH MISMATCH: {package}/{apk_entry.file}[/]")
                    pkg_ok = False
                    continue

            if pkg_ok:
                ok_count += 1
            else:
                fail_count += 1

        console.print(f"\n[success]Verified: {ok_count} OK, {fail_count} failed[/]")

    async def _finalize(self) -> None:
        """Generate reports and restore scripts."""
        console.print("[info]Generating reports...")

        # Reports
        report_gen = ReportGenerator(self.backup_dir)
        end_time = datetime.now()
        report_gen.generate_text_report(self.state, end_time, self.start_time)
        report_gen.generate_csv_inventory(self.state)

        # Restore scripts
        template_dir = Path(__file__).parent.parent / 'restore' / 'templates'
        restore_gen = RestoreGenerator(template_dir)
        restore_gen.generate(self.backup_dir, self.adb_path, self.serial, self.state)

        console.print(f"[success]Reports saved to [path]{self.backup_dir / 'Reports'}[/]")
        console.print(f"[success]Restore scripts saved to [path]{self.backup_dir / 'Restore'}[/]")

    def _show_final_summary(self) -> None:
        """Show final summary."""
        end_time = datetime.now()
        duration = end_time - self.start_time
        total_mb = self.state.stats.total_bytes / (1024 * 1024)

        console.print()
        console.print(create_final_summary_table(self.state, total_mb))

        if self.failed_packages:
            failed_table = create_failed_packages_table(self.failed_packages)
            if failed_table:
                console.print()
                console.print(failed_table)

        console.print(f"\n[success]Backup completed in {format_duration(duration.total_seconds())}[/]")
        console.print(f"[success]Location: [path]{self.backup_dir}[/]")

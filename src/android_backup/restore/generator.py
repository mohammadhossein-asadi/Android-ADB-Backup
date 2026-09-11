"""Restore script generator - cross-platform."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..backup.state import BackupState


class RestoreGenerator:
    """Generate restore scripts for apps and files."""

    def __init__(self, template_dir: Path):
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(
        self,
        backup_dir: Path,
        adb_path: Path,
        serial: str,
        state: BackupState
    ) -> None:
        """Generate restore scripts for current platform."""
        import sys
        is_windows = sys.platform == 'win32'

        restore_dir = backup_dir / 'Restore'
        restore_dir.mkdir(parents=True, exist_ok=True)

        context = {
            'adb_path': str(adb_path),
            'serial': serial,
            'backup_dir': str(backup_dir),
            'is_windows': is_windows,
        }

        if is_windows:
            self._render('restore_apps.bat.j2', restore_dir / 'Restore_Apps.bat', context)
            self._render('restore_files.bat.j2', restore_dir / 'Restore_Files.bat', context)
        else:
            self._render('restore_apps.sh.j2', restore_dir / 'Restore_Apps.sh', context)
            self._render('restore_files.sh.j2', restore_dir / 'Restore_Files.sh', context)
            # Make shell scripts executable
            (restore_dir / 'Restore_Apps.sh').chmod(0o755)
            (restore_dir / 'Restore_Files.sh').chmod(0o755)

    def _render(self, template_name: str, output_path: Path, context: dict) -> None:
        """Render template to file."""
        template = self.env.get_template(template_name)
        output_path.write_text(template.render(**context), encoding='utf-8')

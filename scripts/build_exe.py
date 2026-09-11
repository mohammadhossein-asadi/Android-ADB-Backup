#!/usr/bin/env python3
"""PyInstaller build script for android-adb-backup."""

import subprocess
import sys
from pathlib import Path


def build():
    """Build standalone executable."""
    project_root = Path(__file__).parent.parent
    src_dir = project_root / 'src' / 'android_backup'

    # Get version from pyproject.toml
    import tomllib
    with open(project_root / 'pyproject.toml', 'rb') as f:
        data = tomllib.load(f)
    version = data['project']['version']

    # PyInstaller command
    cmd = [
        'pyinstaller',
        '--onefile',
        '--name', f'android-backup-{version}',
        '--clean',
        '--noconfirm',
        '--collect-all', 'rich',
        '--collect-all', 'click',
        '--collect-all', 'pydantic',
        '--collect-all', 'jinja2',
        '--hidden-import', 'android_backup.adb.discovery',
        '--hidden-import', 'android_backup.adb.client',
        '--hidden-import', 'android_backup.adb.device',
        '--hidden-import', 'android_backup.adb.commands',
        '--hidden-import', 'android_backup.backup.engine',
        '--hidden-import', 'android_backup.backup.device_info',
        '--hidden-import', 'android_backup.backup.packages',
        '--hidden-import', 'android_backup.backup.storage',
        '--hidden-import', 'android_backup.backup.state',
        '--hidden-import', 'android_backup.restore.generator',
        '--hidden-import', 'android_backup.report.generator',
        '--hidden-import', 'android_backup.config',
        '--hidden-import', 'android_backup.utils.filesystem',
        '--hidden-import', 'android_backup.utils.time',
        '--hidden-import', 'android_backup.utils.hashing',
        '--hidden-import', 'android_backup.ui.console',
        '--hidden-import', 'android_backup.ui.progress',
        '--hidden-import', 'android_backup.ui.panels',
        '--hidden-import', 'android_backup.ui.tables',
        '--hidden-import', 'android_backup.ui.prompts',
        '--add-data', f'{src_dir}/restore/templates/*:android_backup/restore/templates',
        str(src_dir / '__main__.py'),
    ]

    print(f"Building android-backup v{version}...")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=project_root)
    if result.returncode == 0:
        print("\n[SUCCESS] Build complete!")
        dist_dir = project_root / 'dist'
        for exe in dist_dir.glob('*'):
            print(f"  Output: {exe}")
    else:
        print("\n[ERROR] Build failed!")
        sys.exit(1)


if __name__ == '__main__':
    build()
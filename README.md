# Android ADB Backup Utility

> **Cross-platform, non-destructive, resumable** Android backup utility with a beautiful live terminal interface.

![Version](https://img.shields.io/badge/version-2.1.0-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## ✨ Features

- **🎨 Beautiful Live Terminal UI** — Real-time progress bars, ETA, live counters, colored panels
- **🔄 Fully Resumable** — Interrupt anytime, resume from exactly where you left off
- **📦 Complete APK Backup** — Base APKs + split APKs (config, architecture, language splits)
- **🛡️ Non-Destructive** — Read-only ADB operations, never modifies device
- **💾 Storage Backup** — Common folders (DCIM, Pictures, Movies, Download, Documents, Music, Android/media) + optional full `/sdcard`
- **🔍 Dry-Run & Verify Modes** — Preview what would be backed up, verify existing backup integrity
- **📊 Rich Reports** — Text report, CSV inventory, JSON state for automation
- **🔧 Cross-Platform** — Native Windows, macOS, Linux support
- **📦 Easy Install** — `pip install` or single executable via PyInstaller

---

## 🚀 Quick Start

### Installation

```bash
# Via pip (recommended)
pip install android-adb-backup

# Or via pipx (isolated environment)
pipx install android-adb-backup

# Or download standalone executable from GitHub Releases
```

### Requirements

- **Android device** with USB debugging enabled
- **ADB** (Android Debug Bridge) installed and in PATH, or placed next to the executable
- **Python 3.9+** (for pip install) — *not needed for standalone executable*

### Usage

```bash
# Interactive backup (auto-detects device)
android-backup

# Skip storage backup
android-backup --skip-storage

# Use specific device
android-backup --device-serial ABC123DEF

# Custom backup name
android-backup --backup-name "before-factory-reset"

# Dry-run: see what would be backed up without doing it
android-backup --whatif

# Verify existing backup integrity
android-backup --verify-only --backup-root ~/Backups/MyPhone

# Auto-resume interrupted backup
android-backup --force-resume

# Full /sdcard backup (large!)
android-backup --full-sdcard
```

---

## 🎮 Terminal UI Preview

```
┌─────────────────────────────────────────────────────────────────────┐
│  Android ADB Backup Utility v2.1.0                    ● Connected  │
├─────────────────────────────────────────────────────────────────────┤
│  Device: Pixel 7 Pro (emulator-5554)           Android 14 • SDK 34 │
├─────────────────────────────────────────────────────────────────────┤
│  ████████████████████████████░░░░░░░░  72%  8.4 MB/s  ETA: 1m 23s │
│  Package: com.google.android.apps.photos (47/65)                   │
│  Current: base.apk → 12.3 MB / 18.7 MB  ████████████░░░░  66%      │
├─────────────────────────────────────────────────────────────────────┤
│  ✓ OK: 42    ⊘ SKIP: 3    ✗ FAIL: 0    ↻ RETRY: 1    ⬇ PULL: 1    │
├─────────────────────────────────────────────────────────────────────┤
│  Logs: backup_run.log  •  errors.log                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Backup Structure

```
Backup_Pixel_7_Pro_before-reset_20260911_143022/
├── Device_Info/
│   └── device_info.txt
├── APKs/
│   └── com.example.app/
│       ├── base.apk
│       ├── split_config.arm64_v8a.apk
│       ├── split_config.en.apk
│       ├── package_dump.txt
│       └── APK_Manifest.csv
├── Packages/
│   ├── packages_all.txt
│   ├── packages_third_party.txt
│   └── packages_system.txt
├── Files/
│   ├── Internal_Storage/
│   │   ├── DCIM/
│   │   ├── Pictures/
│   │   ├── Movies/
│   │   ├── Download/
│   │   ├── Documents/
│   │   ├── Music/
│   │   └── Android_media/
│   └── Full_Internal_Storage/      (if requested)
├── Reports/
│   ├── Backup_Report.txt
│   ├── Application_Inventory.csv
│   └── Backup_State.json
├── Restore/
│   ├── Restore_Apps.sh      (Linux/macOS)
│   ├── Restore_Apps.bat     (Windows)
│   ├── Restore_Files.sh
│   └── Restore_Files.bat
└── Logs/
    ├── backup_run.log
    └── errors.log
```

---

## 🔄 Resume Behavior

- State saved after **every package** to `Reports/Backup_State.json`
- On restart, scans for incomplete backups matching device serial
- **Auto-resume** with `--force-resume` or interactive prompt
- Already-valid APKs (size + ZIP magic + SHA256) are **skipped instantly**
- Storage folders already backed up are **skipped**

---

## 🛡️ Safety Guarantees

The tool **never**:
- Factory resets the device
- Unlocks the bootloader
- Flashes or erases partitions
- Uninstalls apps
- Deletes files on the device
- Modifies `/system`, `/vendor`, `/product`, `/data`, or bootloader settings

**Only read-only ADB commands**: `pull`, `pm path`, `pm list packages`, `getprop`, `ls`, `start-server`, `devices`

---

## 📋 Command Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--backup-root` | dir | `~/AndroidBackups` | Root backup directory |
| `--device-serial` | str | auto | Target device serial |
| `--backup-name` | str | timestamp | Custom backup folder suffix |
| `--skip-storage` | flag | false | Skip all storage folders |
| `--full-sdcard` | flag | false | Backup entire `/sdcard` |
| `--force-resume` | flag | false | Auto-resume without prompt |
| `--whatif` | flag | false | Dry-run mode |
| `--verify-only` | flag | false | Verify existing backup |
| `--adb-timeout` | int | 120 | ADB command timeout (sec) |
| `--max-retries` | int | 3 | Max retry attempts |
| `--config` | file | `~/.config/android-backup/config.toml` | Config file path |
| `--no-color` | flag | false | Disable colored output |
| `--quiet` | flag | false | Minimal output |
| `--version` | flag | false | Show version and exit |

---

## 🔧 Configuration

Config file at `~/.config/android-backup/config.toml`:

```toml
[backup]
root = "~/AndroidBackups"
adb_timeout = 120
max_retries = 3

[ui]
theme = "dark"          # dark, light, auto
show_eta = true
live_update = true
compact_mode = false

[adb]
preferred_path = ""     # Override ADB path
```

---

## 🔀 Restore

Generated scripts in each backup's `Restore/` folder:

```bash
# Linux/macOS
./Restore_Apps.sh
./Restore_Files.sh

# Windows
Restore_Apps.bat
Restore_Files.bat
```

- **Apps**: Uses `adb install` / `adb install-multiple` with `-r -t` (replace, test)
- **Files**: Uses `adb push` to restore to `/sdcard/`
- **Safe**: Never uninstalls or wipes data

---

## 🧪 Development

```bash
# Clone and install in development mode
git clone https://github.com/mohammadhossein-asadi/Android-ADB-Backup
cd Android-ADB-Backup
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Type check
mypy src/android_backup

# Build standalone executable
python scripts/build_exe.py
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## ⚠️ Limitations

- **No private app data** (`/data/data/...`) without root
- **No system partition images** — not a full ROM dump
- Storage limited to ADB-visible `/sdcard` paths
- Some OEMs restrict `pm path` for certain packages
- Large storage trees may need increased timeout

---

*Always verify critical backups. The authors accept no liability for data loss.*
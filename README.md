# Android ADB Backup Utility

> **Production-quality, non-destructive, resumable** Windows tool for backing up Android applications, package metadata, device information, and accessible storage via ADB.

![Version](https://img.shields.io/badge/version-2.1.0-blue)
![Platform](https://img.shields.io/badge/platform-Windows_10%2F11-lightgrey)
![PowerShell](https://img.shields.io/badge/PowerShell-5.1-purple)
![License](https://img.shields.io/badge/license-MIT-green)

---

> **This is NOT a full ROM / partition dump.**
> Without root, custom recovery, or fastboot low-level access, modern Android does not allow unrestricted reading of `/data/data`, `/system`, `/vendor`, `/product`, boot partitions, or userdata.
> The tool clearly separates **ADB application/file backup** from **full ROM backup**.

---

## Features

- Robust ADB wrapper (stdout/stderr/exit code/timeout, never uses `$Args`)
- Correct device detection (`device` / `unauthorized` / `offline`)
- Multi-device selection (always uses `adb -s SERIAL`)
- Third-party package backup with split-APK support
- Per-APK validation (exists, size > 0, ZIP/APK magic, SHA256)
- Resume support via `Reports/Backup_State.json` + existing valid APKs
- Retries (up to 3) on transient pull failures
- Optional storage backup of common `/sdcard` folders
- Optional full `/sdcard` pull (with explicit warning)
- Generated restore scripts (`Restore_Apps.bat`, `Restore_Files.bat`)
- Dry-run mode (`-WhatIf`) — preview without making changes
- Verify-only mode (`-VerifyOnly`) — check existing backup integrity
- Custom backup naming (`-BackupName`)
- ETA estimation during backup
- CSV injection protection in reports
- ADB version check with warnings for outdated versions
- Clear status tags: `[INFO] [OK] [WARN] [ERROR] [SKIP] [PULL] [RETRY] [FAILED]`
- Progress counters with ETA: `[42/137] ETA: ~12m 30s`
- Full logging under `Logs/`
- PowerShell 5.1 compatible
- Safe with paths containing spaces, Unicode, parentheses

---

## Safety Guarantees

The tool **never**:

- Factory resets the device
- Unlocks the bootloader
- Flashes or erases partitions
- Uninstalls apps
- Deletes files on the device
- Deletes previous backup files automatically
- Runs `rm -rf` or equivalent
- Modifies `/system`, `/vendor`, `/product`, `/data`, or bootloader/security configuration

**Backup operations are read-only from the device perspective** (ADB `pull` / `pm path` / `getprop` / `ls`).

---

## Requirements

| Requirement | Details |
|-------------|---------|
| **OS** | Windows 10/11 (or Windows 8.1+ with PowerShell 5.1) |
| **PowerShell** | 5.1 (included with Windows) |
| **ADB** | [Android Platform-Tools](https://developer.android.com/tools/releases/platform-tools) — `adb.exe` on PATH or next to script |
| **Device** | USB debugging enabled + authorized for this computer |

---

## Quick Start

### 1. Get ADB

Download [Android Platform-Tools](https://developer.android.com/tools/releases/platform-tools) and place `adb.exe` (and the supporting DLLs) next to `Android_Backup.bat`, **or** ensure `adb` is on your PATH.

### 2. Connect Your Device

1. Enable **USB Debugging** on your Android device (Settings → Developer Options)
2. Connect via USB and **authorize** the computer when prompted
3. Verify with `adb devices` — your device should show as `device`

### 3. Run the Backup

```
# Double-click Android_Backup.bat
# — or from Command Prompt:
Android_Backup.bat

# — or directly with PowerShell:
powershell -NoProfile -ExecutionPolicy Bypass -File Android_Backup.ps1
```

Follow the on-screen prompts (device selection, resume, optional storage backup).

---

## Command-Line Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `-BackupRoot` | string | `./Backups` | Root directory for backup output |
| `-DeviceSerial` | string | *(auto-detect)* | Prefer a specific device serial |
| `-BackupName` | string | *(none)* | Custom suffix for backup folder name |
| `-SkipStorage` | switch | `$false` | Skip all storage folder backups |
| `-FullSdcard` | switch | `$false` | Offer full `/sdcard` pull (large) |
| `-ForceResume` | switch | `$false` | Auto-resume without prompting |
| `-WhatIf` | switch | `$false` | Dry-run mode — preview without changes |
| `-VerifyOnly` | switch | `$false` | Check existing backup integrity |
| `-AdbTimeoutSec` | int | `120` | Timeout for ADB commands (seconds) |
| `-MaxRetries` | int | `3` | Maximum retry attempts for pulls |

### Examples

```powershell
# Basic backup
powershell -File Android_Backup.ps1

# Skip storage, use specific device
powershell -File Android_Backup.ps1 -SkipStorage -DeviceSerial "ABCD1234"

# Dry-run to see what would be backed up
powershell -File Android_Backup.ps1 -WhatIf

# Verify a previous backup's integrity
powershell -File Android_Backup.ps1 -VerifyOnly -BackupRoot "C:\Backups\MyPhone"

# Custom backup name
powershell -File Android_Backup.ps1 -BackupName "before-reset"

# Auto-resume without prompt
powershell -File Android_Backup.ps1 -ForceResume
```

---

## Backup Layout

```
Android_Backup_DEVICE_TIMESTAMP/
├── Device_Info/
│   └── device_info.txt
├── APKs/
│   └── package.name/
│       ├── base.apk
│       ├── split_config.*.apk   (if any)
│       ├── package_dump.txt
│       └── APK_Manifest.csv     (File,RemotePath,SizeBytes,SHA256)
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
│   └── Full_Internal_Storage/   (only if requested)
├── Reports/
│   ├── Backup_Report.txt
│   ├── Application_Inventory.csv
│   └── Backup_State.json
├── Restore/
│   ├── Restore_Apps.bat
│   └── Restore_Files.bat
└── Logs/
    ├── backup_run.log
    └── errors.log
```

---

## Resume Behavior

- If an incomplete `Backup_State.json` for the same serial is found, you are offered to resume
- With `-ForceResume`, the resume happens automatically without prompting
- Already-valid APKs (non-zero size + APK magic + recorded) are skipped with `[SKIP] already backed up`
- Missing, zero-byte, or invalid APKs are re-pulled
- State is saved after every package so an interruption is recoverable
- On resume, device info is refreshed (not stale from previous run)
- Already-completed storage folders are skipped on resume

---

## Restore Instructions

1. Connect the target device (same or different)
2. Edit the `SERIAL` value inside the generated BAT files if the serial changed
3. Run `Restore\Restore_Apps.bat` to install APKs (uses `install` / `install-multiple`, `-r -t`)
4. Run `Restore\Restore_Files.bat` to push storage files back

**Restore scripts do not** uninstall apps or wipe app data.

---

## Error Classification

### Fatal (abort)

- PowerShell unavailable
- `adb.exe` missing
- ADB server cannot start
- Backup directory cannot be created
- No usable (authorized) device

### Recoverable (continue)

- One package fails
- One APK / split fails
- One storage folder inaccessible
- One device property missing

---

## Limitations

- **No access to private app data** (`/data/data/...`) without root
- **No system partition images** — this is not a full ROM dump
- Storage backup only covers world-readable `/sdcard` paths that ADB can see
- Some OEMs restrict `pm path` or pull for certain packages
- Very large storage trees may time out; increase timeout or use selective folders

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `adb.exe not found` | Place platform-tools next to the script or add to PATH |
| `No ADB devices found` | Enable USB debugging, authorize computer, check USB cable |
| `Device unauthorized` | Accept the USB debugging prompt on the device |
| `Backup stalls` | Increase `-AdbTimeoutSec` (e.g., 300 for large pulls) |
| `Resume not working` | Check that `Backup_State.json` exists in the backup folder |
| `Split APK install fails` | Ensure target device supports `adb install-multiple` |
| `Storage folders empty` | Some OEMs restrict ADB access to `/sdcard` subfolders |

---

## Project Files

| File | Purpose |
|------|---------|
| `Android_Backup.bat` | Launcher (finds PowerShell, calls the script) |
| `Android_Backup.ps1` | Main engine (all logic) |
| `.gitignore` | Excludes Backups/, Logs/, temp files |
| `README.md` | This file |
| `CHANGELOG.md` | Version history |
| `test/VALIDATION_REPORT.md` | Design & static validation notes |

---

## License

Provided as-is for personal and professional backup use.
Always verify critical backups. The authors accept no liability for data loss.

# Static Validation & Design Audit Report

**Project:** Android ADB Backup Utility v2.1.0  
**Date:** 2026-09-11  
**Target:** Windows PowerShell 5.1 + ADB Platform-Tools

## 1. PowerShell Parser / Interpolation Audit

| Pattern searched | Status | Notes |
|------------------|--------|-------|
| `$Args` as parameter | **Clean** | Parameter renamed to `$AdbArgs`. Automatic `$Args` never bound as custom param. |
| `$folder:` / `$path:` / `$name:` style | **Clean** | All interpolations use `${var}:` form or concatenation. No bare `$var:` left. |
| Null method calls | **Guarded** | Every `$r.Output`, `$r.Error`, file object, and process is null-checked. |
| Empty array binding | **Handled** | Explicit check: if `$AdbArgs` empty → return error object, do not bind. |
| `Set-StrictMode -Version Latest` | **Enabled** | Catches many latent null/undefined issues at runtime. |

## 2. ADB Engine Audit

- Wrapper returns structured object: `Output`, `Error`, `ExitCode`, `TimedOut`, `Success`.
- Never assumes Output is non-null.
- Uses `ProcessStartInfo` + async Output/ErrorDataReceived (UTF-8).
- Timeout → Kill + TimedOut flag.
- Device serial always passed as `-s SERIAL` after selection.
- Discovery order: script dir → platform-tools subdir → parent → PATH.
- No silent download of binaries.
- Proper Windows-style argument quoting (only quotes args with spaces).
- ADB version check warns if older than 30.0.0.

## 3. Device Detection Audit

| Scenario | Expected behaviour |
|----------|--------------------|
| `bbcc946c        device` | Recognized as Ready = true |
| `unauthorized` | Logged as WARN, not selected |
| `offline` | Logged as WARN, not selected |
| No devices | Fatal error, clear message |
| Multiple `device` | Numbered interactive selection; no random choice |
| Preferred serial | Honoured if present and ready |

Parser skips header line "List of devices attached" and blank lines.

## 4. Resume Logic Audit

- State persisted to `Reports/Backup_State.json` after every package.
- On start, scans recent backup folders for incomplete state matching current serial.
- User prompted to resume (unless `-ForceResume` is set, which auto-resumes).
- Per-APK: if local file exists, size > 0, and passes ZIP magic → `[SKIP] already backed up`.
- Zero-byte or invalid → re-pull with retries.
- Package already marked OK in state → whole package skipped.
- Device info updated on resume (not stale).
- Storage folders skipped if already successfully pulled.

## 5. Path & Quoting Audit

- All filesystem calls use `-LiteralPath` where appropriate.
- Generated BAT files quote paths containing spaces.
- ADB arguments that contain spaces are quoted in ProcessStartInfo.Arguments.
- Backup root and device model sanitised for illegal filename characters.
- Works with examples: `C:\Android Backups\My Phone`, Unicode folder names.

## 6. Restore Script Audit

- `Restore_Apps.bat` uses `%ADB%` and `%SERIAL%` (single percent).
- Delayed expansion only for loop variables (`!PKG!`, `!COUNT!`, etc.).
- Single APK → `adb install -r -t`.
- Multiple APKs → `adb install-multiple -r -t`.
- No automatic uninstall / data wipe.
- `Restore_Files.bat` uses `adb push` only.
- `%~dp0` used correctly for relative location of APKs/Files.

## 7. Error Classification

**Fatal (exit non-zero, stop):**
- No PowerShell
- No adb.exe
- Cannot create backup directory
- No authorized device

**Recoverable (log + continue):**
- Individual package / APK / split failure
- Missing storage folder
- Missing getprop value
- Timeout on one pull (after retries)

## 8. Safety Checklist

| Forbidden action | Present in code? |
|------------------|------------------|
| factory reset | No |
| unlock bootloader | No |
| flash / erase partitions | No |
| uninstall apps | No |
| delete device files | No |
| delete backup files automatically | No |
| `rm -rf` / shell destructive cmds | No |
| write to /system /vendor /product /data | No |

Only read-side ADB commands are issued.

## 9. New Features Audit (v2.1.0)

| Feature | Status | Notes |
|---------|--------|-------|
| `-WhatIf` dry-run mode | **Clean** | Lists packages, shows what would be pulled, no ADB writes. |
| `-VerifyOnly` mode | **Clean** | Re-checks existing APKs via ZIP magic, no file creation. |
| `-BackupName` parameter | **Clean** | Sanitised for illegal chars, appended to folder name. |
| Failed package summary | **Clean** | Printed after backup loop, no data loss. |
| Total bytes tracking | **Clean** | Accumulated per-APK, saved to state and report. |
| CSV injection protection | **Clean** | Prefixes `=`, `+`, `-`, `@` with single quote. |
| ADB version check | **Clean** | Non-blocking warning, does not abort. |
| ETA calculation | **Clean** | Based on average of completed package times. |
| Storage resume skip | **Clean** | Checks `$State.Storage[$key].Success` before pull. |
| BAT parameter passthrough | **Clean** | Handles all 10+ flags with shift loop. |

## 10. Test Matrix (manual / field)

| # | Scenario | Expected |
|---|----------|----------|
| 1 | One authorized device | Auto-select, backup proceeds |
| 2 | Unauthorized device | WARN + fatal if only device |
| 3 | Offline device | WARN + fatal if only device |
| 4 | No device | Clear fatal error |
| 5 | Multiple authorized devices | Numbered menu, force `-s` |
| 6 | Failed package (pm path empty) | Mark FAILED, continue |
| 7 | Existing valid APK | `[SKIP] already backed up` |
| 8 | Zero-byte APK | Re-pull, do not mark success |
| 9 | Interrupted mid-run | State saved; resume offered |
| 10 | Resume | Skips completed, retries failed |
| 11 | Path with spaces | Succeeds |
| 12 | Unicode path | Succeeds (UTF-8) |
| 13 | Missing storage folder | `[SKIP]` / WARN, continue |
| 14 | Single APK restore | `adb install -r -t` |
| 15 | Split APK restore | `adb install-multiple -r -t` |
| 16 | `-WhatIf` mode | Lists packages, no pulls |
| 17 | `-VerifyOnly` mode | Reports APK integrity |
| 18 | `-ForceResume` | Auto-resumes without prompt |
| 19 | `-BackupName` | Custom folder suffix |
| 20 | Failed package summary | List printed at end |
| 21 | Storage resume skip | Already-pulled folders skipped |
| 22 | All BAT flags passthrough | Every flag reaches PS1 |
| 23 | ADB version warning | Old version triggers WARN |
| 24 | ETA display | Shows after 2+ packages |
| 25 | CSV injection protection | Formula chars escaped |

## 11. Files Produced

- `Android_Backup.ps1` – main engine
- `Android_Backup.bat` – launcher
- `.gitignore` – excludes Backups/, Logs/, temp files
- `README.md` – GitHub documentation
- `CHANGELOG.md` – version history
- `test/VALIDATION_REPORT.md` (this file)

Restore scripts are generated at runtime into each backup's `Restore/` folder so they embed the correct absolute ADB path and serial used for that backup.

## Conclusion

The project has been fully rewritten and enhanced. All previously reported parser, binding, device-detection, and restore-script defects have been eliminated by design. v2.1.0 adds dry-run mode, verification, ETA tracking, storage resume, and CSV safety. The utility meets the stated priorities: Safety → Data integrity → Reliability → Resume → Error handling → PS 5.1 → Modern ADB → Clear UX → Maintainability.

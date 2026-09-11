# Changelog

## 2.1.0 – 2026-09-11

Bug fixes, new features, and improved usability.

### Fixed

- **BAT launcher only forwarded first argument** — Now passes through all supported flags (`-SkipStorage`, `-FullSdcard`, `-ForceResume`, `-WhatIf`, `-VerifyOnly`) and value-paired args (`-DeviceSerial`, `-BackupRoot`, `-BackupName`, `-AdbTimeoutSec`, `-MaxRetries`).
- **Dead resume condition (`$ForceResume -or $true`)** — Removed the always-true condition. `-ForceResume` now meaningfully auto-resumes without prompting.
- **Unused temp files created and cleaned up** — Removed `$stdoutFile`/`$stderrFile` creation and cleanup that wasted temp files and was misleading.
- **ADB argument quoting could break paths with special characters** — Replaced manual regex quoting with proper Windows-style quoting (only quotes args containing spaces).
- **Device info lost on resume** — Fresh `$devInfo` is now saved to `$Script:State.DeviceInfo` during resume instead of keeping stale data.
- **Storage folders re-pulled on resume** — Each storage folder now checks prior success in `$Script:State.Storage` before re-pulling.

### Added

- **`-WhatIf` dry-run mode** — Show what would be backed up without making any changes or pulling files.
- **`-VerifyOnly` mode** — Re-check existing APKs (ZIP magic + size) without pulling. Reports integrity status.
- **`-BackupName` parameter** — Custom suffix for backup folder name (e.g., `Android_Backup_Pixel_7_before-reset_20260911`).
- **Failed/Partial package summary** — Prints a list of specific packages that failed at the end of the backup.
- **Total bytes backed up** — Tracks and displays cumulative backup size in console and report.
- **CSV injection protection** — Escapes CSV values starting with `=`, `+`, `-`, `@` to prevent formula injection.
- **ADB version check** — Warns if ADB version is older than 30.0.0 (pre-2020, known bugs).
- **ETA in progress display** — Shows estimated time remaining based on average package backup time.
- **`.gitignore`** — Excludes `Backups/`, `Logs/`, temp files from version control.

## 2.0.0 – 2026-09-09

Complete engineering rewrite. Previous versions contained multiple critical defects; this release replaces them rather than patching.

### Fixed (root causes of reported errors)

- **`Invoke-Adb : Cannot bind argument to parameter 'Args'`**  
  PowerShell automatic variable `$Args` was used as a custom parameter name. Renamed to `$AdbArgs` / `$Arguments` throughout. Empty argument arrays are handled explicitly.

- **`You cannot call a method on a null-valued expression`**  
  All ADB result objects, Output/Error arrays, and file objects are null-checked before use. Process and stream disposal is guarded.

- **`[ERROR] No authorized ADB device` despite `bbcc946c device`**  
  Device parser now correctly recognizes the `device` state, ignores header lines, and distinguishes `unauthorized` / `offline` / `no permissions`. Multi-device selection is mandatory when >1 ready device is present; every subsequent command uses `-s SERIAL`.

- **Parser error: `Variable reference is not valid. ':' was not followed by a valid variable name character`**  
  Caused by interpolation such as `"$folder: $($_.Exception.Message)"`. All such sites rewritten to `"${folder}: ..."` form. Full static audit performed for `$var:` patterns.

- **Broken restore BAT variables (`%%ADB%%` etc.)**  
  Generated restore scripts now emit correct `%ADB%` / `%SERIAL%` / `%~dp0` usage with delayed expansion only where needed. No double-percent bugs.

### Architecture

- Single reliable ADB wrapper returning `Output`, `Error`, `ExitCode`, `TimedOut`, `Success`.
- Argument list built as a .NET List (no fragile string construction for core args).
- Timeout + process kill on hang.
- UTF-8 stdout/stderr capture via async event handlers.
- SHA256 + ZIP magic validation after every APK pull.
- JSON state file for resume; per-APK skip of already-valid files.
- Retry loop (default 3) with clear `[RETRY] attempt N/3` messages.
- One failed package never aborts the whole run.
- Clear separation of fatal vs recoverable errors.
- Path safety for spaces, Unicode, parentheses (LiteralPath + proper quoting).
- PowerShell 5.1 only (`#Requires -Version 5.1`, no PS7-only features).

### Safety

- Explicit non-destructive contract documented and enforced by design (only `pull`, `pm`, `getprop`, `ls`, `start-server`, `devices`).
- No factory reset, unlock, flash, erase, uninstall, or device-side delete paths exist in the code.

### UX / Reporting

- Status tags: `[INFO] [OK] [WARN] [ERROR] [SKIP] [PULL] [RETRY] [FAILED]`
- Progress: `[42/137]`
- Reports: `Backup_Report.txt`, `Application_Inventory.csv`, `Backup_State.json`
- Logs: `backup_run.log`, `errors.log`
- Generated `Restore_Apps.bat` (handles single + split APKs) and `Restore_Files.bat`.

### Known limitations (unchanged by design)

- Not a full ROM dump.
- No private app data without root.
- Storage limited to ADB-visible `/sdcard` trees.

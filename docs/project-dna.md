# Project DNA — Android ADB Backup

## Project Identity

| Field | Value |
|-------|-------|
| **Project Name** | Android ADB Backup |
| **Repository** | `Android-ADB-Backup` |
| **Type** | CLI Tool (Python + PowerShell/Batch) |
| **Primary Language** | Python 3.11+ |
| **Package Manager** | pip / pyproject.toml |
| **Platform** | Cross-platform (Windows, Linux, macOS) |

---

## Purpose & Problem Statement

**Problem**: Android users lack a simple, reliable way to create complete device backups using ADB without relying on proprietary software or cloud services.

**Solution**: A cross-platform CLI tool that automates ADB backup/restore operations with support for full device backup, app-specific backup, and encrypted archives.

---

## Target Users

- **Primary**: Android power users, developers, privacy-conscious users
- **Secondary**: IT administrators managing device fleets
- **Tertiary**: Users migrating devices or recovering from data loss

---

## Core Features (Implemented)

| Feature | Status | Description |
|---------|--------|-------------|
| Full Device Backup | ✅ Implemented | `adb backup -all -apk -obb -shared` via Python wrapper |
| App-Specific Backup | ✅ Implemented | Target specific packages |
| Restore Functionality | ✅ Implemented | `adb restore` with progress |
| Encryption Support | ✅ Implemented | AES-256 encrypted backup archives |
| Cross-Platform | ✅ Implemented | Windows (batch + Python), Linux/macOS (shell + Python) |
| Interactive Menu | ✅ Implemented | Menu-driven operation selection |
| Logging | ✅ Implemented | Timestamped operation logs |
| Persian Localization | ✅ Implemented | RTL README, Persian UI strings |

---

## Technical Requirements

| Requirement | Detail |
|-------------|--------|
| **Python** | 3.11+ |
| **ADB** | Android Debug Bridge in PATH |
| **Dependencies** | `cryptography`, `tqdm`, `colorama` (see pyproject.toml) |
| **OS** | Windows 10+, Linux, macOS |
| **USB Debugging** | Enabled on target device |

---

## Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| FR-01 | Backup all apps + data + shared storage | ✅ |
| FR-02 | Backup specific package | ✅ |
| FR-03 | Restore from backup file | ✅ |
| FR-04 | Encrypt backup with password | ✅ |
| FR-05 | Decrypt and restore | ✅ |
| FR-06 | List available backups | ✅ |
| FR-07 | Verify backup integrity | ✅ |
| FR-08 | Windows batch wrapper | ✅ |
| FR-09 | Linux/macOS shell wrapper | ✅ |

---

## Non-Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| NFR-01 | Zero external dependencies (stdlib + minimal) | ✅ |
| NFR-02 | No root required | ✅ |
| NFR-03 | Resume interrupted transfers | [NOT IMPLEMENTED] |
| NFR-04 | Progress indication | ✅ (tqdm) |
| NFR-05 | Cross-platform path handling | ✅ |

---

## Business/Technical Objectives

- [ ] Add WiFi ADB support (TCP/IP)
- [ ] Add scheduled/automated backups
- [ ] Support Android 14+ backup restrictions
- [ ] Add backup compression options
- [ ] Create GUI frontend (Tauri/Electron)
- [ ] Package as standalone executable (PyInstaller)

---

## Known Limitations

1. **ADB must be in PATH** - Not bundled
2. **No WiFi ADB** - USB only currently
3. **Android 12+ restrictions** - Some apps opt-out of backup
4. **No incremental backup** - Full backup each time
5. **Single-threaded** - No parallel app backup

---

## Confirmed Decisions

| Decision | Rationale |
|----------|-----------|
| Python + ADB wrapper | Leverage existing ADB, cross-platform |
| `cryptography` for encryption | Standard, audited, Fernet/AES-GCM |
| `tqdm` for progress | Familiar, handles TTY/non-TTY |
| Dual wrapper (bat/sh) | Native feel on each platform |
| pyproject.toml + pip | Modern Python packaging |

---

## Unknown Information / Needs Confirmation

| Question | Priority |
|----------|----------|
| Target Python version minimum? (3.11 vs 3.8) | MEDIUM |
| Bundle ADB binary? | LOW |
| Support for Android 14+ backup agent changes? | HIGH |
| GUI frontend priority? | LOW |

---

*Generated: 2026-10-30 | Stage 1 of 5 | [NEEDS CONFIRMATION] on unknowns*
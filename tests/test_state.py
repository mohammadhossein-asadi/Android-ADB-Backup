"""Tests for backup state management."""

import json
import tempfile
from pathlib import Path

from android_backup.backup.state import (
    BackupState,
    PackageEntry,
    APKEntry,
    StorageEntry,
    BackupStats,
    StateManager,
)


class TestBackupState:
    def test_create_state(self):
        state = BackupState.create("ABC123", Path("/tmp/backup"), {"model": "Pixel 7"})
        assert state.serial == "ABC123"
        assert state.backup_dir == str(Path("/tmp/backup"))
        assert state.device_info["model"] == "Pixel 7"
        assert state.completed is False

    def test_state_serialization(self):
        state = BackupState.create("ABC123", Path("/tmp/backup"), {})
        state.packages["com.test"] = PackageEntry(
            status="OK",
            apks=[APKEntry(file="base.apk", remote="/data/app/test", size=1000, sha256="abc")]
        )
        state.storage["/sdcard/DCIM"] = StorageEntry(success=True)

        json_str = state.to_json()
        parsed = json.loads(json_str)

        assert parsed["serial"] == "ABC123"
        assert parsed["packages"]["com.test"]["status"] == "OK"
        assert parsed["packages"]["com.test"]["apks"][0]["file"] == "base.apk"
        assert parsed["storage"]["/sdcard/DCIM"]["success"] is True

    def test_state_deserialization(self):
        original = BackupState.create("ABC123", Path("/tmp/backup"), {})
        original.packages["com.test"] = PackageEntry(
            status="OK",
            apks=[APKEntry(file="base.apk", remote="/data/app/test", size=1000, sha256="abc")]
        )
        original.storage["/sdcard/DCIM"] = StorageEntry(success=True)

        json_str = original.to_json()
        restored = BackupState.from_json(json_str)

        assert restored.serial == "ABC123"
        assert restored.packages["com.test"].status == "OK"
        assert restored.packages["com.test"].apks[0].file == "base.apk"
        assert restored.storage["/sdcard/DCIM"].success is True

    def test_state_save_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state = BackupState.create("ABC123", Path(tmpdir) / "backup", {})
            state.packages["com.test"] = PackageEntry(status="OK")

            state_file = Path(tmpdir) / "state.json"
            state.save(state_file)

            loaded = BackupState.load(state_file)
            assert loaded is not None
            assert loaded.serial == "ABC123"
            assert "com.test" in loaded.packages


class TestStateManager:
    def test_find_incomplete_backups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_root = Path(tmpdir) / "Backups"
            backup_root.mkdir()

            # Create complete backup (should not be found)
            complete_backup = backup_root / "Backup_Pixel_20260101_120000"
            complete_backup.mkdir()
            (complete_backup / "Reports").mkdir()
            complete_state = BackupState.create("SERIAL1", complete_backup, {})
            complete_state.completed = True
            complete_state.save(complete_backup / "Reports" / "Backup_State.json")

            # Create incomplete backup (should be found)
            incomplete_backup = backup_root / "Backup_Pixel_20260102_120000"
            incomplete_backup.mkdir()
            (incomplete_backup / "Reports").mkdir()
            incomplete_state = BackupState.create("SERIAL1", incomplete_backup, {})
            incomplete_state.completed = False
            incomplete_state.save(incomplete_backup / "Reports" / "Backup_State.json")

            # Different serial (should not be found)
            other_backup = backup_root / "Backup_Pixel_20260103_120000"
            other_backup.mkdir()
            (other_backup / "Reports").mkdir()
            other_state = BackupState.create("SERIAL2", other_backup, {})
            other_state.completed = False
            other_state.save(other_backup / "Reports" / "Backup_State.json")

            manager = StateManager(incomplete_backup)
            found = manager.find_incomplete_backups("SERIAL1")

            assert len(found) == 1
            assert found[0] == incomplete_backup
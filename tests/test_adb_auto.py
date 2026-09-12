"""Tests for automatic ADB discovery and download."""

import io
import os
import zipfile
from pathlib import Path

import pytest

from android_backup.adb.discovery import ADBDiscovery, MANUAL_INSTALL_HINT
from android_backup.exceptions import ADBNotFoundError
from android_backup.utils import get_platform_tools_url


class TestPlatformToolsUrl:
    def test_url_for_current_platform(self):
        key, url = get_platform_tools_url()
        assert key in ("windows", "darwin", "linux")
        assert url.startswith("https://dl.google.com/android/repository/platform-tools-latest-")
        assert url.endswith(".zip")


class TestFindFastPaths:
    def test_preferred_path(self, tmp_path, monkeypatch):
        adb = tmp_path / "adb.exe"
        adb.write_bytes(b"x")
        monkeypatch.delenv("ANDROID_BACKUP_NO_AUTO_ADB", raising=False)
        d = ADBDiscovery(str(adb), auto_install=False)
        assert d.find() == adb

    def test_path_lookup(self, tmp_path, monkeypatch):
        fake_adb = tmp_path / "adb"
        fake_adb.write_bytes(b"x")
        monkeypatch.setattr("shutil.which", lambda name: str(fake_adb))
        monkeypatch.setattr(
            "android_backup.adb.discovery.get_cached_adb_path",
            lambda: tmp_path / "missing-adb",
        )
        monkeypatch.setattr(
            "android_backup.adb.discovery.find_adb_candidates",
            lambda: [],
        )
        monkeypatch.delenv("ANDROID_BACKUP_NO_AUTO_ADB", raising=False)
        d = ADBDiscovery(auto_install=False)
        assert d.find() == fake_adb

    def test_no_auto_raises_helpful_message(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: None)
        monkeypatch.setattr(
            "android_backup.adb.discovery.get_cached_adb_path",
            lambda: tmp_path / "missing-adb",
        )
        monkeypatch.setattr(
            "android_backup.adb.discovery.find_adb_candidates",
            lambda: [],
        )
        d = ADBDiscovery(auto_install=False)
        with pytest.raises(ADBNotFoundError, match="platform-tools"):
            d.find()

    def test_env_disables_auto_install(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: None)
        monkeypatch.setattr(
            "android_backup.adb.discovery.get_cached_adb_path",
            lambda: tmp_path / "missing-adb",
        )
        monkeypatch.setattr(
            "android_backup.adb.discovery.find_adb_candidates",
            lambda: [],
        )
        monkeypatch.setenv("ANDROID_BACKUP_NO_AUTO_ADB", "1")
        d = ADBDiscovery(auto_install=True)
        with pytest.raises(ADBNotFoundError):
            d.find()


class FakeHeaders(dict):
    pass


class FakeResponse:
    def __init__(self, payload: bytes):
        self._io = io.BytesIO(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, n=-1):
        return self._io.read(n)


def _make_platform_tools_zip(is_windows: bool) -> bytes:
    buf = io.BytesIO()
    adb_name = "platform-tools/adb.exe" if is_windows else "platform-tools/adb"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(adb_name, b"fake-adb-binary")
    return buf.getvalue()


class TestDownload:
    def test_download_extracts_adb(self, tmp_path, monkeypatch):
        import android_backup.adb.discovery as disc

        cache_dir = tmp_path / "cache" / "platform-tools"
        adb_name = "adb.exe" if os.name == "nt" else "adb"
        payload = _make_platform_tools_zip(os.name == "nt")

        monkeypatch.setattr(disc, "get_adb_cache_dir", lambda: cache_dir)
        monkeypatch.setattr(disc, "get_cached_adb_path", lambda: cache_dir / adb_name)
        monkeypatch.setattr(disc, "get_platform_tools_url", lambda: ("test", "https://example.test/pt.zip"))
        monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=60: FakeResponse(payload))
        monkeypatch.setattr(ADBDiscovery, "_looks_like_adb", lambda self, p: True)

        d = ADBDiscovery(auto_install=True)
        result = d.download_platform_tools()
        assert result.exists()
        assert result.name == adb_name

    def test_find_uses_auto_download(self, tmp_path, monkeypatch):
        import android_backup.adb.discovery as disc

        adb_path = tmp_path / "adb"
        adb_path.write_bytes(b"fake")

        monkeypatch.setattr("shutil.which", lambda name: None)
        monkeypatch.setattr(
            "android_backup.adb.discovery.get_cached_adb_path",
            lambda: tmp_path / "missing",
        )
        monkeypatch.setattr(
            "android_backup.adb.discovery.find_adb_candidates",
            lambda: [],
        )
        monkeypatch.setattr(
            ADBDiscovery, "download_platform_tools", lambda self, progress=None: adb_path
        )
        monkeypatch.delenv("ANDROID_BACKUP_NO_AUTO_ADB", raising=False)

        d = ADBDiscovery(auto_install=True)
        assert d.find() == adb_path

    def test_manual_hint_present(self):
        assert "platform-tools" in MANUAL_INSTALL_HINT.lower()
        assert "--adb-path" in MANUAL_INSTALL_HINT

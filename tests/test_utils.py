"""Tests for utility modules."""

import tempfile
from pathlib import Path

from android_backup.utils import (
    format_bytes,
    format_duration,
    format_speed,
    ETACalculator,
    format_eta,
    validate_apk,
    compute_sha256,
)


class TestFormatBytes:
    def test_bytes(self):
        assert format_bytes(500) == "500.0 B"

    def test_kilobytes(self):
        assert format_bytes(1536) == "1.5 KB"

    def test_megabytes(self):
        assert format_bytes(2 * 1024 * 1024) == "2.0 MB"

    def test_gigabytes(self):
        assert format_bytes(3 * 1024 * 1024 * 1024) == "3.0 GB"


class TestFormatDuration:
    def test_seconds(self):
        assert format_duration(30) == "30s"

    def test_minutes(self):
        assert format_duration(90) == "1m 30s"

    def test_hours(self):
        assert format_duration(3661) == "1h 1m"


class TestFormatSpeed:
    def test_speed(self):
        assert format_speed(1024) == "1.0 KB/s"


class TestETACalculator:
    def test_eta_calculation(self):
        calc = ETACalculator(window_size=5)
        calc.record_completion(10.0)
        calc.record_completion(12.0)
        calc.record_completion(8.0)
        # Average = 10, remaining = 7, ETA = 70s
        eta = calc.get_eta(3, 10)
        assert eta is not None
        assert 65 < eta < 75

    def test_eta_not_enough_data(self):
        calc = ETACalculator()
        calc.record_completion(10.0)
        assert calc.get_eta(1, 10) is None


class TestFormatETA:
    def test_format_eta_seconds(self):
        assert format_eta(30.0) == "30s"

    def test_format_eta_minutes(self):
        assert format_eta(90.0) == "1m 30s"

    def test_format_eta_hours(self):
        assert format_eta(3661.0) == "1h 1m"

    def test_format_eta_none(self):
        assert format_eta(None) == "calculating..."


class TestValidateAPK:
    def test_valid_apk(self):
        with tempfile.NamedTemporaryFile(suffix='.apk', delete=False) as f:
            # Write ZIP magic bytes
            f.write(b'PK\x03\x04' + b'x' * 100)
            f.flush()
            path = Path(f.name)

        try:
            valid, sha256, size = validate_apk(path)
            assert valid is True
            assert size > 0
            assert sha256 is not None
        finally:
            path.unlink()

    def test_invalid_apk(self):
        with tempfile.NamedTemporaryFile(suffix='.apk', delete=False) as f:
            f.write(b'NOT_APK' + b'x' * 100)
            f.flush()
            path = Path(f.name)

        try:
            valid, sha256, size = validate_apk(path)
            assert valid is False
        finally:
            path.unlink()

    def test_missing_file(self):
        path = Path('/nonexistent/file.apk')
        valid, sha256, size = validate_apk(path)
        assert valid is False


class TestComputeSHA256:
    def test_sha256(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'hello world')
            f.flush()
            path = Path(f.name)

        try:
            sha256 = compute_sha256(path)
            assert sha256 == 'b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9'
        finally:
            path.unlink()

    def test_missing_file(self):
        path = Path('/nonexistent/file.txt')
        sha256 = compute_sha256(path)
        assert sha256 is None
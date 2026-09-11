"""Custom exception hierarchy for Android ADB Backup."""



class AndroidBackupError(Exception):
    """Base exception for all Android Backup errors."""
    def __init__(self, message: str, *, exit_code: int = 1):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class ADBError(AndroidBackupError):
    """ADB-related errors."""
    def __init__(self, message: str, *, exit_code: int = 2, adb_output: str = ""):
        super().__init__(message, exit_code=exit_code)
        self.adb_output = adb_output


class ADBNotFoundError(ADBError):
    """ADB executable not found."""
    def __init__(self, message: str = "ADB executable not found. Install Android Platform Tools and ensure 'adb' is in PATH."):
        super().__init__(message, exit_code=3)


class DeviceError(AndroidBackupError):
    """Device-related errors."""
    def __init__(self, message: str, *, exit_code: int = 4):
        super().__init__(message, exit_code=exit_code)


class NoDeviceError(DeviceError):
    """No ADB devices found."""
    def __init__(self, message: str = "No ADB devices found. Connect a device with USB debugging enabled."):
        super().__init__(message, exit_code=5)


class DeviceUnauthorizedError(DeviceError):
    """Device is unauthorized."""
    def __init__(self, serial: str):
        super().__init__(
            f"Device {serial} is unauthorized. Accept the USB debugging prompt on the device.",
            exit_code=6
        )
        self.serial = serial


class DeviceOfflineError(DeviceError):
    """Device is offline."""
    def __init__(self, serial: str):
        super().__init__(
            f"Device {serial} is offline. Check USB connection and try 'adb kill-server'.",
            exit_code=7
        )
        self.serial = serial


class BackupError(AndroidBackupError):
    """Backup operation errors."""
    def __init__(self, message: str, *, exit_code: int = 8):
        super().__init__(message, exit_code=exit_code)


class BackupDirectoryError(BackupError):
    """Cannot create or access backup directory."""
    def __init__(self, path: str, message: str = ""):
        super().__init__(
            f"Cannot create backup directory: {path}. {message}",
            exit_code=9
        )
        self.path = path


class StateError(BackupError):
    """State file errors."""
    def __init__(self, message: str, *, path: str = "", exit_code: int = 10):
        super().__init__(message, exit_code=exit_code)
        self.path = path


class RestoreError(AndroidBackupError):
    """Restore script generation errors."""
    def __init__(self, message: str, *, exit_code: int = 11):
        super().__init__(message, exit_code=exit_code)


class ConfigurationError(AndroidBackupError):
    """Configuration errors."""
    def __init__(self, message: str, *, exit_code: int = 12):
        super().__init__(message, exit_code=exit_code)

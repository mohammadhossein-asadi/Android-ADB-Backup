@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Android ADB Backup Utility
cd /d "%~dp0"

:: ---------------------------------------------------------------------------
:: Android ADB Backup Launcher (Windows)
:: Non-destructive | Resumable | PowerShell 5.1 compatible
:: ---------------------------------------------------------------------------

echo.
echo ============================================================
echo  Android ADB Backup Utility
echo  Safe, resumable application + storage backup via ADB
echo ============================================================
echo.

:: Locate PowerShell
set "PS="
where powershell >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "delims=" %%P in ('where powershell') do (
        set "PS=%%P"
        goto :FoundPS
    )
)
if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" (
    set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
    goto :FoundPS
)
if exist "%SystemRoot%\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" (
    set "PS=%SystemRoot%\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
    goto :FoundPS
)

echo [ERROR] Windows PowerShell not found.
echo This tool requires Windows PowerShell 5.1.
pause
exit /b 1

:FoundPS
echo [INFO] Using PowerShell: %PS%

:: Pass through all supported flags and arguments
set "EXTRA="
:ParseArgs
if "%~1"=="" goto :DoneArgs
if /i "%~1"=="-SkipStorage" ( set "EXTRA=!EXTRA! -SkipStorage" & shift & goto :ParseArgs )
if /i "%~1"=="-FullSdcard"  ( set "EXTRA=!EXTRA! -FullSdcard"  & shift & goto :ParseArgs )
if /i "%~1"=="-ForceResume" ( set "EXTRA=!EXTRA! -ForceResume" & shift & goto :ParseArgs )
if /i "%~1"=="-WhatIf"      ( set "EXTRA=!EXTRA! -WhatIf"      & shift & goto :ParseArgs )
if /i "%~1"=="-VerifyOnly"  ( set "EXTRA=!EXTRA! -VerifyOnly"  & shift & goto :ParseArgs )
if /i "%~1"=="-DeviceSerial" ( set "EXTRA=!EXTRA! -DeviceSerial "%~2"" & shift & shift & goto :ParseArgs )
if /i "%~1"=="-BackupRoot"   ( set "EXTRA=!EXTRA! -BackupRoot "%~2""   & shift & shift & goto :ParseArgs )
if /i "%~1"=="-BackupName"   ( set "EXTRA=!EXTRA! -BackupName "%~2""   & shift & shift & goto :ParseArgs )
if /i "%~1"=="-AdbTimeoutSec" ( set "EXTRA=!EXTRA! -AdbTimeoutSec %~2" & shift & shift & goto :ParseArgs )
if /i "%~1"=="-MaxRetries"   ( set "EXTRA=!EXTRA! -MaxRetries %~2"   & shift & shift & goto :ParseArgs )
set "EXTRA=!EXTRA! "%~1""
shift
goto :ParseArgs
:DoneArgs

echo [INFO] Launching backup script...
echo.

"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Android_Backup.ps1" %EXTRA%
set "RC=%ERRORLEVEL%"

echo.
if %RC% equ 0 (
    echo [OK] Backup process finished with code 0.
) else (
    echo [ERROR] Backup process exited with code %RC%.
)
echo.
pause
endlocal
exit /b %RC%

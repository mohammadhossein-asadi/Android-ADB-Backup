#Requires -Version 5.1
<#
.SYNOPSIS
    Android ADB Backup Utility - Non-destructive, resumable, production-quality backup tool for Windows.

.DESCRIPTION
    Safely backs up APKs (including split APKs), package metadata, device information,
    and optional accessible storage folders from an authorized Android device via ADB.
    Does NOT perform full ROM/partition dumps. Does NOT modify the device.

.PARAMETER BackupRoot
    Root directory for backup output. Defaults to ./Backups relative to the script.

.PARAMETER DeviceSerial
    Prefer a specific device serial when multiple devices are connected.

.PARAMETER SkipStorage
    Skip all storage folder backups.

.PARAMETER FullSdcard
    Offer full /sdcard pull (large, with explicit warning).

.PARAMETER ForceResume
    Force auto-resume of incomplete backup without prompting.

.PARAMETER WhatIf
    Dry-run mode. Show what would be backed up without making changes.

.PARAMETER VerifyOnly
    Re-check existing APKs without pulling. Reports integrity status.

.PARAMETER BackupName
    Custom suffix for the backup folder name (e.g., "before-reset").

.PARAMETER AdbTimeoutSec
    Timeout for ADB commands in seconds. Default: 120.

.PARAMETER MaxRetries
    Maximum retry attempts for APK pulls. Default: 3.

.NOTES
    Target: Windows PowerShell 5.1
    Safety: Non-destructive. Never factory-resets, flashes, erases, or modifies /system,/vendor,/data, etc.
    Resume: Core feature via Backup_State.json and per-APK validation (size + SHA256).
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$BackupRoot = "",
    [string]$DeviceSerial = "",
    [switch]$SkipStorage,
    [switch]$FullSdcard,
    [switch]$ForceResume,
    [switch]$WhatIf,
    [switch]$VerifyOnly,
    [string]$BackupName = "",
    [int]$AdbTimeoutSec = 120,
    [int]$MaxRetries = 3
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# ---------------------------------------------------------------------------
# Constants & Global State
# ---------------------------------------------------------------------------
$Script:Version = "2.1.0"
$Script:ScriptDir = $PSScriptRoot
if (-not $Script:ScriptDir) { $Script:ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $Script:ScriptDir) { $Script:ScriptDir = (Get-Location).Path }

$Script:AdbPath = $null
$Script:SelectedSerial = $null
$Script:BackupDir = $null
$Script:LogDir = $null
$Script:StateFile = $null
$Script:State = $null
$Script:StartTime = Get-Date
$Script:LogStream = $null
$Script:ErrorLogStream = $null
$Script:TotalBytesBackedUp = 0
$Script:PackageTimes = @()

# ---------------------------------------------------------------------------
# Logging Helpers
# ---------------------------------------------------------------------------
function Write-Log {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [ValidateSet("INFO", "OK", "WARN", "ERROR", "SKIP", "PULL", "RETRY", "FAILED", "DEBUG")]
        [string]$Level = "INFO"
    )
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $line = "[$ts] [$Level] $Message"
    switch ($Level) {
        "ERROR"  { Write-Host $line -ForegroundColor Red }
        "WARN"   { Write-Host $line -ForegroundColor Yellow }
        "OK"     { Write-Host $line -ForegroundColor Green }
        "SKIP"   { Write-Host $line -ForegroundColor Cyan }
        "FAILED" { Write-Host $line -ForegroundColor Magenta }
        "RETRY"  { Write-Host $line -ForegroundColor DarkYellow }
        "PULL"   { Write-Host $line -ForegroundColor White }
        default  { Write-Host $line }
    }
    if ($Script:LogStream) {
        try { $Script:LogStream.WriteLine($line) } catch {}
    }
    if ($Level -eq "ERROR" -or $Level -eq "FAILED") {
        if ($Script:ErrorLogStream) {
            try { $Script:ErrorLogStream.WriteLine($line) } catch {}
        }
    }
}

function Initialize-Logging {
    param([string]$LogDirectory)
    if (-not (Test-Path -LiteralPath $LogDirectory)) {
        New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
    }
    $runLog = Join-Path $LogDirectory "backup_run.log"
    $errLog = Join-Path $LogDirectory "errors.log"
    $Script:LogStream = [System.IO.StreamWriter]::new($runLog, $true, [System.Text.Encoding]::UTF8)
    $Script:LogStream.AutoFlush = $true
    $Script:ErrorLogStream = [System.IO.StreamWriter]::new($errLog, $true, [System.Text.Encoding]::UTF8)
    $Script:ErrorLogStream.AutoFlush = $true
    Write-Log "Logging initialized. Run log: $runLog" "INFO"
}

function Close-Logging {
    if ($Script:LogStream) {
        try { $Script:LogStream.Flush(); $Script:LogStream.Close(); $Script:LogStream.Dispose() } catch {}
        $Script:LogStream = $null
    }
    if ($Script:ErrorLogStream) {
        try { $Script:ErrorLogStream.Flush(); $Script:ErrorLogStream.Close(); $Script:ErrorLogStream.Dispose() } catch {}
        $Script:ErrorLogStream = $null
    }
}

# ---------------------------------------------------------------------------
# ADB Discovery
# ---------------------------------------------------------------------------
function Find-AdbExecutable {
    $candidates = @()
    # 1. Beside the script
    $candidates += Join-Path $Script:ScriptDir "adb.exe"
    $candidates += Join-Path $Script:ScriptDir "platform-tools\adb.exe"
    # 2. Launcher / parent
    $parent = Split-Path -Parent $Script:ScriptDir
    if ($parent) {
        $candidates += Join-Path $parent "adb.exe"
        $candidates += Join-Path $parent "platform-tools\adb.exe"
    }
    # 3. PATH
    $pathCmd = Get-Command "adb.exe" -ErrorAction SilentlyContinue
    if ($pathCmd -and $pathCmd.Source) {
        $candidates += $pathCmd.Source
    }
    $pathCmd2 = Get-Command "adb" -ErrorAction SilentlyContinue
    if ($pathCmd2 -and $pathCmd2.Source) {
        $candidates += $pathCmd2.Source
    }

    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c)) {
            return (Resolve-Path -LiteralPath $c).Path
        }
    }
    return $null
}

# ---------------------------------------------------------------------------
# ADB Version Check
# ---------------------------------------------------------------------------
function Test-AdbVersion {
    $r = Invoke-Adb -AdbArgs @("version") -NoDevice -TimeoutSec 10
    if ($r.Success -and $r.Output.Count -gt 0) {
        $versionLine = $r.Output[0]
        if ($versionLine -match 'Android Debug Bridge version (\d+)\.(\d+)\.(\d+)') {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            $patch = [int]$Matches[3]
            $versionNum = $major * 10000 + $minor * 100 + $patch
            if ($versionNum -lt 30000) {
                Write-Log "ADB version $major.$minor.$patch is older than 30.0.0. Consider updating from https://developer.android.com/tools/releases/platform-tools" "WARN"
            }
            else {
                Write-Log "ADB version: $major.$minor.$patch" "INFO"
            }
            return "$major.$minor.$patch"
        }
    }
    return "unknown"
}

# ---------------------------------------------------------------------------
# Robust ADB Wrapper (never uses $Args automatic variable)
# ---------------------------------------------------------------------------
function Invoke-Adb {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$AdbArgs,

        [string]$DeviceSerial = "",

        [int]$TimeoutSec = 120,

        [string]$WorkingDirectory = "",

        [switch]$NoDevice
    )

    $result = [PSCustomObject]@{
        Output   = @()
        Error    = @()
        ExitCode = -1
        TimedOut = $false
        Success  = $false
    }

    if (-not $Script:AdbPath -or -not (Test-Path -LiteralPath $Script:AdbPath)) {
        $result.Error = @("ADB executable not found or not set.")
        return $result
    }

    # Build argument list carefully (array, never fragile string concatenation for core args)
    $argList = New-Object System.Collections.Generic.List[string]

    if (-not $NoDevice -and $DeviceSerial) {
        $argList.Add("-s")
        $argList.Add($DeviceSerial)
    }

    if ($AdbArgs -and $AdbArgs.Count -gt 0) {
        foreach ($a in $AdbArgs) {
            if ($null -ne $a) {
                $argList.Add([string]$a)
            }
        }
    }

    if ($argList.Count -eq 0) {
        $result.Error = @("No arguments supplied to Invoke-Adb.")
        return $result
    }

    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Script:AdbPath
        # Proper Windows argument quoting: only quote args containing spaces
        $psi.Arguments = ($argList | ForEach-Object {
            if ($_ -match '\s') {
                "`"$_`""
            } else {
                $_
            }
        }) -join " "
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
        if ($WorkingDirectory -and (Test-Path -LiteralPath $WorkingDirectory)) {
            $psi.WorkingDirectory = $WorkingDirectory
        }

        $proc = New-Object System.Diagnostics.Process
        $proc.StartInfo = $psi

        $outBuilder = New-Object System.Text.StringBuilder
        $errBuilder = New-Object System.Text.StringBuilder

        $outEvent = Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -Action {
            if ($null -ne $EventArgs.Data) {
                [void]$Event.MessageData.AppendLine($EventArgs.Data)
            }
        } -MessageData $outBuilder

        $errEvent = Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived -Action {
            if ($null -ne $EventArgs.Data) {
                [void]$Event.MessageData.AppendLine($EventArgs.Data)
            }
        } -MessageData $errBuilder

        [void]$proc.Start()
        $proc.BeginOutputReadLine()
        $proc.BeginErrorReadLine()

        $exited = $proc.WaitForExit($TimeoutSec * 1000)
        if (-not $exited) {
            $result.TimedOut = $true
            try { $proc.Kill() } catch {}
            try { $proc.WaitForExit(5000) } catch {}
            $result.Error = @("ADB command timed out after ${TimeoutSec}s")
            $result.ExitCode = -2
        } else {
            $result.ExitCode = $proc.ExitCode
        }

        # Allow async handlers to finish
        Start-Sleep -Milliseconds 100
        Unregister-Event -SourceIdentifier $outEvent.Name -ErrorAction SilentlyContinue
        Unregister-Event -SourceIdentifier $errEvent.Name -ErrorAction SilentlyContinue

        $outText = $outBuilder.ToString()
        $errText = $errBuilder.ToString()

        # Always store as real [string[]] — never a scalar or space-joined string
        $outLines = New-Object System.Collections.Generic.List[string]
        if ($outText) {
            foreach ($ln in ($outText -split "`r?`n")) {
                if ($null -ne $ln -and $ln -ne "") { $outLines.Add($ln) }
            }
        }
        $result.Output = [string[]]$outLines.ToArray()

        $errLines = New-Object System.Collections.Generic.List[string]
        if ($errText) {
            foreach ($ln in ($errText -split "`r?`n")) {
                if ($null -ne $ln -and $ln -ne "") { $errLines.Add($ln) }
            }
        }
        $result.Error = [string[]]$errLines.ToArray()

        $result.Success = (-not $result.TimedOut) -and ($result.ExitCode -eq 0)
    }
    catch {
        $result.Error = @("Exception invoking ADB: $($_.Exception.Message)")
        $result.ExitCode = -3
        $result.Success = $false
    }
    finally {
        if ($proc -and -not $proc.HasExited) {
            try { $proc.Kill() } catch {}
        }
        if ($proc) { $proc.Dispose() }
    }

    return $result
}

# ---------------------------------------------------------------------------
# Device Detection & Selection
# ---------------------------------------------------------------------------
function Start-AdbServer {
    Write-Log "Starting ADB server..." "INFO"
    $r = Invoke-Adb -AdbArgs @("start-server") -NoDevice -TimeoutSec 30
    if (-not $r.Success) {
        Write-Log "ADB start-server reported issues (may already be running): $($r.Error -join ' | ')" "WARN"
    }
    Start-Sleep -Seconds 1
}

function Get-AdbDevices {
    $r = Invoke-Adb -AdbArgs @("devices") -NoDevice -TimeoutSec 30
    # Always use a generic list so a single device never unwraps to a scalar
    $list = New-Object System.Collections.Generic.List[object]
    if ($r.Output) {
        foreach ($line in @($r.Output)) {
            if ($null -eq $line) { continue }
            $line = ([string]$line).Trim()
            if ($line -eq "" -or $line -match 'List of devices') { continue }
            if ($line -match '^(\S+)\s+(\S+)') {
                $serial = $Matches[1]
                $state  = $Matches[2].ToLowerInvariant()
                $list.Add([PSCustomObject]@{
                    Serial = $serial
                    State  = $state
                    Ready  = ($state -eq "device")
                })
            }
        }
    }
    # Return a flat object array (never $null, never scalar, never nested)
    return @($list.ToArray())
}

function Select-Device {
    param([string]$PreferredSerial = "")

    Start-AdbServer
    # Force array so .Count is always safe under Set-StrictMode
    $devices = @(Get-AdbDevices)

    if ($devices.Count -eq 0) {
        Write-Log "No ADB devices found. Connect a device with USB debugging enabled and authorize this computer." "ERROR"
        return $null
    }

    $ready = @($devices | Where-Object { $_.Ready })
    $other = @($devices | Where-Object { -not $_.Ready })

    if ($other.Count -gt 0) {
        foreach ($d in $other) {
            Write-Log "Device $($d.Serial) is in state '$($d.State)' (not usable until authorized/online)." "WARN"
        }
    }

    if ($ready.Count -eq 0) {
        Write-Log "No authorized/ready ADB device (state 'device'). Found devices but none ready." "ERROR"
        return $null
    }

    if ($PreferredSerial) {
        $match = @($ready | Where-Object { $_.Serial -eq $PreferredSerial }) | Select-Object -First 1
        if ($match) {
            Write-Log "Using preferred device: $($match.Serial)" "OK"
            return $match.Serial
        }
        Write-Log "Preferred serial '$PreferredSerial' not found among ready devices." "WARN"
    }

    if ($ready.Count -eq 1) {
        Write-Log "Single ready device: $($ready[0].Serial)" "OK"
        return $ready[0].Serial
    }

    # Multiple ready devices - interactive selection
    Write-Host ""
    Write-Host "Multiple authorized devices detected:" -ForegroundColor Cyan
    for ($i = 0; $i -lt $ready.Count; $i++) {
        Write-Host ("  [{0}] {1}" -f ($i + 1), $ready[$i].Serial)
    }
    Write-Host ""
    $choice = Read-Host "Enter number (1-$($ready.Count)) or serial"
    if ($choice -match '^\d+$') {
        $idx = [int]$choice - 1
        if ($idx -ge 0 -and $idx -lt $ready.Count) {
            return $ready[$idx].Serial
        }
    }
    $bySerial = @($ready | Where-Object { $_.Serial -eq $choice }) | Select-Object -First 1
    if ($bySerial) { return $bySerial.Serial }

    Write-Log "Invalid selection." "ERROR"
    return $null
}

# ---------------------------------------------------------------------------
# Device Information
# ---------------------------------------------------------------------------
function Get-DeviceProperty {
    param(
        [string]$Serial,
        [string]$Prop
    )
    $r = Invoke-Adb -DeviceSerial $Serial -AdbArgs @("shell", "getprop", $Prop) -TimeoutSec 15
    $out = @($r.Output)
    if ($r.Success -and $out.Count -gt 0) {
        $val = ($out[0] -as [string]).Trim()
        if ($val) { return $val }
    }
    return ""
}

function Get-DeviceInfo {
    param([string]$Serial)

    $props = @(
        "ro.product.manufacturer",
        "ro.product.model",
        "ro.product.device",
        "ro.product.name",
        "ro.build.version.release",
        "ro.build.version.sdk",
        "ro.product.cpu.abi",
        "ro.product.cpu.abilist",
        "ro.build.display.id",
        "ro.build.fingerprint",
        "ro.bootloader",
        "ro.build.version.security_patch"
    )

    $info = [ordered]@{}
    foreach ($p in $props) {
        $info[$p] = Get-DeviceProperty -Serial $Serial -Prop $p
    }
    $info["Serial"] = $Serial
    return $info
}

# ---------------------------------------------------------------------------
# Package Listing & APK Handling
# ---------------------------------------------------------------------------
function Get-PackageList {
    param([string]$Serial)

    $allList = New-Object System.Collections.Generic.List[string]
    $thirdList = New-Object System.Collections.Generic.List[string]
    $systemList = New-Object System.Collections.Generic.List[string]

    $rAll = Invoke-Adb -DeviceSerial $Serial -AdbArgs @("shell", "pm", "list", "packages") -TimeoutSec 60
    if ($rAll.Success -and $rAll.Output) {
        foreach ($line in @($rAll.Output)) {
            if ($null -eq $line) { continue }
            if (([string]$line) -match '^package:(.+)$') {
                $allList.Add($Matches[1].Trim())
            }
        }
    }

    $r3 = Invoke-Adb -DeviceSerial $Serial -AdbArgs @("shell", "pm", "list", "packages", "-3") -TimeoutSec 60
    if ($r3.Success -and $r3.Output) {
        foreach ($line in @($r3.Output)) {
            if ($null -eq $line) { continue }
            if (([string]$line) -match '^package:(.+)$') {
                $thirdList.Add($Matches[1].Trim())
            }
        }
    }

    $rs = Invoke-Adb -DeviceSerial $Serial -AdbArgs @("shell", "pm", "list", "packages", "-s") -TimeoutSec 60
    if ($rs.Success -and $rs.Output) {
        foreach ($line in @($rs.Output)) {
            if ($null -eq $line) { continue }
            if (([string]$line) -match '^package:(.+)$') {
                $systemList.Add($Matches[1].Trim())
            }
        }
    }

    # Always return real arrays (never $null, never scalar)
    return [PSCustomObject]@{
        All        = @($allList | Sort-Object -Unique)
        ThirdParty = @($thirdList | Sort-Object -Unique)
        System     = @($systemList | Sort-Object -Unique)
    }
}

function Get-PackagePaths {
    param(
        [string]$Serial,
        [string]$PackageName
    )
    $pathList = New-Object System.Collections.Generic.List[string]
    $r = Invoke-Adb -DeviceSerial $Serial -AdbArgs @("shell", "pm", "path", $PackageName) -TimeoutSec 30
    if ($r.Success -and $r.Output) {
        $text = (@($r.Output) | ForEach-Object { [string]$_ }) -join "`n"
        $rxMatches = [regex]::Matches($text, 'package:(\S+)')
        foreach ($m in $rxMatches) {
            $p = $m.Groups[1].Value.Trim()
            if ($p -and -not $pathList.Contains($p)) {
                $pathList.Add($p)
            }
        }
    }
    return [string[]]@($pathList.ToArray())
}

function Get-FileSha256 {
    param([string]$FilePath)
    if (-not (Test-Path -LiteralPath $FilePath)) { return $null }
    try {
        $hasher = [System.Security.Cryptography.SHA256]::Create()
        $stream = [System.IO.File]::OpenRead($FilePath)
        try {
            $hashBytes = $hasher.ComputeHash($stream)
            return ([BitConverter]::ToString($hashBytes) -replace '-', '').ToLowerInvariant()
        }
        finally {
            $stream.Close()
            $hasher.Dispose()
        }
    }
    catch {
        return $null
    }
}

function Test-ValidApk {
    param([string]$FilePath)
    if (-not (Test-Path -LiteralPath $FilePath)) { return $false }
    $item = Get-Item -LiteralPath $FilePath -ErrorAction SilentlyContinue
    if (-not $item -or $item.Length -le 0) { return $false }
    try {
        $fs = [System.IO.File]::OpenRead($FilePath)
        try {
            $buf = New-Object byte[] 4
            $read = $fs.Read($buf, 0, 4)
            if ($read -lt 4) { return $false }
            # PK\x03\x04
            if ($buf[0] -eq 0x50 -and $buf[1] -eq 0x4B -and $buf[2] -eq 0x03 -and $buf[3] -eq 0x04) {
                return $true
            }
            return $false
        }
        finally { $fs.Close() }
    }
    catch {
        return $false
    }
}

function Pull-ApkWithRetry {
    param(
        [string]$Serial,
        [string]$RemotePath,
        [string]$LocalPath,
        [int]$MaxAttempts = 3
    )

    $dir = Split-Path -Parent $LocalPath
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        if ($attempt -gt 1) {
            Write-Log "[RETRY] attempt $attempt/$MaxAttempts for $RemotePath" "RETRY"
            Start-Sleep -Seconds (2 * ($attempt - 1))
        }

        # Remove incomplete previous attempt
        if (Test-Path -LiteralPath $LocalPath) {
            Remove-Item -LiteralPath $LocalPath -Force -ErrorAction SilentlyContinue
        }

        $r = Invoke-Adb -DeviceSerial $Serial -AdbArgs @("pull", $RemotePath, $LocalPath) -TimeoutSec $AdbTimeoutSec
        if ($r.Success -and (Test-ValidApk -FilePath $LocalPath)) {
            $size = (Get-Item -LiteralPath $LocalPath).Length
            $hash = Get-FileSha256 -FilePath $LocalPath
            return [PSCustomObject]@{
                Success    = $true
                LocalPath  = $LocalPath
                RemotePath = $RemotePath
                SizeBytes  = $size
                SHA256     = $hash
                Attempts   = $attempt
            }
        }
        else {
            $errMsg = if ($r.Error) { $r.Error -join " | " } else { "exit $($r.ExitCode)" }
            Write-Log "Pull failed (attempt $attempt): $errMsg" "WARN"
            if (Test-Path -LiteralPath $LocalPath) {
                Remove-Item -LiteralPath $LocalPath -Force -ErrorAction SilentlyContinue
            }
        }
    }

    return [PSCustomObject]@{
        Success    = $false
        LocalPath  = $LocalPath
        RemotePath = $RemotePath
        SizeBytes  = 0
        SHA256     = $null
        Attempts   = $MaxAttempts
    }
}

# ---------------------------------------------------------------------------
# State / Resume Management
# ---------------------------------------------------------------------------
function New-BackupState {
    return [ordered]@{
        Version        = $Script:Version
        Serial         = ""
        BackupDir      = ""
        Started        = (Get-Date).ToString("o")
        Completed      = $false
        Packages       = @{}
        Storage        = @{}
        DeviceInfo     = @{}
        Stats          = [ordered]@{
            TotalPackages     = 0
            SuccessPackages   = 0
            FailedPackages    = 0
            SkippedPackages   = 0
            TotalApks         = 0
            SuccessApks       = 0
            FailedApks        = 0
            TotalBytes        = 0
        }
    }
}

function Load-BackupState {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        $json = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
        $obj = $json | ConvertFrom-Json
        $state = New-BackupState
        $state.Serial = $obj.Serial
        $state.BackupDir = $obj.BackupDir
        $state.Started = $obj.Started
        $state.Completed = [bool]$obj.Completed
        if ($obj.DeviceInfo) {
            $obj.DeviceInfo.PSObject.Properties | ForEach-Object { $state.DeviceInfo[$_.Name] = $_.Value }
        }
        if ($obj.Stats) {
            $obj.Stats.PSObject.Properties | ForEach-Object { $state.Stats[$_.Name] = $_.Value }
        }
        if ($obj.Packages) {
            $obj.Packages.PSObject.Properties | ForEach-Object {
                $state.Packages[$_.Name] = $_.Value
            }
        }
        if ($obj.Storage) {
            $obj.Storage.PSObject.Properties | ForEach-Object {
                $state.Storage[$_.Name] = $_.Value
            }
        }
        return $state
    }
    catch {
        Write-Log "Failed to load state file: $($_.Exception.Message)" "WARN"
        return $null
    }
}

function Save-BackupState {
    param($State, [string]$Path)
    try {
        $dir = Split-Path -Parent $Path
        if (-not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
        $json = $State | ConvertTo-Json -Depth 8
        [System.IO.File]::WriteAllText($Path, $json, [System.Text.Encoding]::UTF8)
    }
    catch {
        Write-Log "Failed to save state: $($_.Exception.Message)" "WARN"
    }
}

# ---------------------------------------------------------------------------
# Storage Backup (optional, non-destructive)
# ---------------------------------------------------------------------------
function Backup-StorageFolder {
    param(
        [string]$Serial,
        [string]$RemoteFolder,
        [string]$LocalFolder,
        [int]$MaxAttempts = 2
    )

    if (-not (Test-Path -LiteralPath $LocalFolder)) {
        New-Item -ItemType Directory -Path $LocalFolder -Force | Out-Null
    }

    # Check remote existence first
    $check = Invoke-Adb -DeviceSerial $Serial -AdbArgs @("shell", "ls", $RemoteFolder) -TimeoutSec 20
    if (-not $check.Success) {
        Write-Log "Remote folder inaccessible or missing: $RemoteFolder" "WARN"
        return [PSCustomObject]@{ Success = $false; Skipped = $true; Message = "inaccessible" }
    }

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        if ($attempt -gt 1) {
            Write-Log "[RETRY] storage $RemoteFolder attempt $attempt/$MaxAttempts" "RETRY"
        }
        $r = Invoke-Adb -DeviceSerial $Serial -AdbArgs @("pull", $RemoteFolder, $LocalFolder) -TimeoutSec ([Math]::Max($AdbTimeoutSec, 600))
        if ($r.Success) {
            return [PSCustomObject]@{ Success = $true; Skipped = $false; Message = "ok" }
        }
        Write-Log "Storage pull failed: $($r.Error -join ' | ')" "WARN"
    }
    return [PSCustomObject]@{ Success = $false; Skipped = $false; Message = "failed after retries" }
}

# ---------------------------------------------------------------------------
# Restore Script Generation
# ---------------------------------------------------------------------------
function New-RestoreScripts {
    param(
        [string]$BackupDir,
        [string]$AdbExePath,
        [string]$Serial
    )

    $restoreDir = Join-Path $BackupDir "Restore"
    if (-not (Test-Path -LiteralPath $restoreDir)) {
        New-Item -ItemType Directory -Path $restoreDir -Force | Out-Null
    }

    $adbForBat = $AdbExePath

    # ---- Restore_Apps.bat ----
    $appsBat = @"
@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Android Backup - Restore Apps
cd /d "%~dp0"

set "ADB=$adbForBat"
set "SERIAL=$Serial"

if not exist "%ADB%" (
    echo [ERROR] adb.exe not found at: %ADB%
    echo Place platform-tools next to this script or edit ADB path.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Android App Restore (from this backup)
echo  Device serial: %SERIAL%
echo  This script does NOT uninstall or wipe existing apps.
echo ============================================================
echo.

"%ADB%" start-server >nul 2>&1
"%ADB%" -s %SERIAL% get-state 2>nul | findstr /i "device" >nul
if errorlevel 1 (
    echo [ERROR] Device %SERIAL% is not ready. Authorize USB debugging and retry.
    pause
    exit /b 1
)

set "APKROOT=%~dp0..\APKs"
if not exist "%APKROOT%" (
    echo [ERROR] APKs folder not found: %APKROOT%
    pause
    exit /b 1
)

for /d %%D in ("%APKROOT%\*") do (
    set "PKG=%%~nxD"
    echo.
    echo [INFO] Package: !PKG!
    set "BASE="
    set "SPLITS="
    set "COUNT=0"
    for %%F in ("%%D\*.apk") do (
        set /a COUNT+=1
        if /i "%%~nxF"=="base.apk" (
            set "BASE=%%F"
        ) else (
            set "SPLITS=!SPLITS! "%%F""
        )
    )
    if !COUNT! equ 0 (
        echo [SKIP] No APK files in %%D
    ) else if !COUNT! equ 1 (
        if defined BASE (
            echo [INSTALL] Single APK: !BASE!
            "%ADB%" -s %SERIAL% install -r -t "!BASE!"
        ) else (
            for %%F in ("%%D\*.apk") do (
                echo [INSTALL] Single APK: %%F
                "%ADB%" -s %SERIAL% install -r -t "%%F"
            )
        )
    ) else (
        echo [INSTALL-MULTIPLE] !COUNT! APKs for !PKG!
        if defined BASE (
            "%ADB%" -s %SERIAL% install-multiple -r -t "!BASE!" !SPLITS!
        ) else (
            "%ADB%" -s %SERIAL% install-multiple -r -t !SPLITS!
        )
    )
)

echo.
echo [OK] App restore pass finished.
pause
endlocal
"@

    $appsPath = Join-Path $restoreDir "Restore_Apps.bat"
    [System.IO.File]::WriteAllText($appsPath, $appsBat, [System.Text.Encoding]::ASCII)

    # ---- Restore_Files.bat ----
    $filesBat = @"
@echo off
setlocal EnableExtensions
title Android Backup - Restore Files
cd /d "%~dp0"

set "ADB=$adbForBat"
set "SERIAL=$Serial"

if not exist "%ADB%" (
    echo [ERROR] adb.exe not found at: %ADB%
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Android Storage Restore (from this backup)
echo  Device serial: %SERIAL%
echo  This pushes files back; it does NOT delete device data.
echo ============================================================
echo.

"%ADB%" start-server >nul 2>&1
"%ADB%" -s %SERIAL% get-state 2>nul | findstr /i "device" >nul
if errorlevel 1 (
    echo [ERROR] Device %SERIAL% is not ready.
    pause
    exit /b 1
)

set "FILESROOT=%~dp0..\Files"
if not exist "%FILESROOT%" (
    echo [WARN] Files folder not found. Nothing to restore.
    pause
    exit /b 0
)

if exist "%FILESROOT%\Internal_Storage" (
    echo [PUSH] Internal_Storage ...
    "%ADB%" -s %SERIAL% push "%FILESROOT%\Internal_Storage\." /sdcard/
)

if exist "%FILESROOT%\Full_Internal_Storage" (
    echo [PUSH] Full_Internal_Storage ...
    "%ADB%" -s %SERIAL% push "%FILESROOT%\Full_Internal_Storage\." /sdcard/
)

echo.
echo [OK] File restore pass finished.
pause
endlocal
"@

    $filesPath = Join-Path $restoreDir "Restore_Files.bat"
    [System.IO.File]::WriteAllText($filesPath, $filesBat, [System.Text.Encoding]::ASCII)

    Write-Log "Restore scripts written to $restoreDir" "OK"
}

# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------
function Write-BackupReport {
    param(
        $State,
        [string]$ReportPath,
        [datetime]$EndTime
    )

    $duration = $EndTime - $Script:StartTime
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine("============================================================")
    [void]$sb.AppendLine(" Android ADB Backup Report")
    [void]$sb.AppendLine(" Version: $($Script:Version)")
    [void]$sb.AppendLine("============================================================")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("IMPORTANT LIMITATIONS")
    [void]$sb.AppendLine("--------------------")
    [void]$sb.AppendLine("This is an ADB application/file backup, NOT a full ROM or partition dump.")
    [void]$sb.AppendLine("Without root/recovery/fastboot, modern Android does not expose:")
    [void]$sb.AppendLine("  /data/data, /data/user, /system, /vendor, /product, /boot, userdata, etc.")
    [void]$sb.AppendLine("Only APKs, package metadata, device props, and accessible /sdcard paths are backed up.")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("DEVICE")
    [void]$sb.AppendLine("------")
    if ($State.DeviceInfo) {
        foreach ($k in $State.DeviceInfo.Keys) {
            [void]$sb.AppendLine(("  {0}: {1}" -f $k, $State.DeviceInfo[$k]))
        }
    }
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("BACKUP")
    [void]$sb.AppendLine("------")
    [void]$sb.AppendLine("  Destination : $($State.BackupDir)")
    [void]$sb.AppendLine("  Started     : $($State.Started)")
    [void]$sb.AppendLine("  Finished    : $($EndTime.ToString('o'))")
    [void]$sb.AppendLine("  Duration    : $([int]$duration.TotalMinutes)m $($duration.Seconds)s")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("STATISTICS")
    [void]$sb.AppendLine("----------")
    [void]$sb.AppendLine("  Packages total   : $($State.Stats.TotalPackages)")
    [void]$sb.AppendLine("  Packages success : $($State.Stats.SuccessPackages)")
    [void]$sb.AppendLine("  Packages failed  : $($State.Stats.FailedPackages)")
    [void]$sb.AppendLine("  Packages skipped : $($State.Stats.SkippedPackages)")
    [void]$sb.AppendLine("  APKs total       : $($State.Stats.TotalApks)")
    [void]$sb.AppendLine("  APKs success     : $($State.Stats.SuccessApks)")
    [void]$sb.AppendLine("  APKs failed      : $($State.Stats.FailedApks)")
    $totalMB = [math]::Round($State.Stats.TotalBytes / 1MB, 2)
    [void]$sb.AppendLine("  Total size       : $totalMB MB ($($State.Stats.TotalBytes) bytes)")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("RESTORE")
    [void]$sb.AppendLine("-------")
    [void]$sb.AppendLine("  Scripts: Restore\Restore_Apps.bat  and  Restore\Restore_Files.bat")
    [void]$sb.AppendLine("  Restore does NOT uninstall apps or wipe data.")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("LOGS")
    [void]$sb.AppendLine("----")
    [void]$sb.AppendLine("  Logs\backup_run.log")
    [void]$sb.AppendLine("  Logs\errors.log")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("SAFETY")
    [void]$sb.AppendLine("------")
    [void]$sb.AppendLine("  This tool never factory-resets, unlocks bootloader, flashes, erases,")
    [void]$sb.AppendLine("  or modifies /system, /vendor, /product, /data, or bootloader settings.")
    [void]$sb.AppendLine("")

    $dir = Split-Path -Parent $ReportPath
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($ReportPath, $sb.ToString(), [System.Text.Encoding]::UTF8)
    Write-Log "Report written: $ReportPath" "OK"
}

function Write-InventoryCsv {
    param(
        $State,
        [string]$CsvPath
    )
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("Package,Status,ApkCount,SuccessApks,FailedApks,Notes")
    if ($State.Packages) {
        foreach ($pkg in ($State.Packages.Keys | Sort-Object)) {
            $entry = $State.Packages[$pkg]
            $status = $entry.Status
            $apkCount = 0
            $ok = 0
            $fail = 0
            $notes = ""
            if ($entry.Apks) {
                $apkCount = @($entry.Apks).Count
                foreach ($a in $entry.Apks) {
                    if ($a.Success) { $ok++ } else { $fail++ }
                }
            }
            if ($entry.Message) { $notes = $entry.Message -replace ',', ';' }
            # CSV injection protection: escape values starting with formula characters
            if ($pkg -match '^[=+\-@]') { $pkg = "'$pkg" }
            if ($notes -match '^[=+\-@]') { $notes = "'$notes" }
            $lines.Add(("$pkg,$status,$apkCount,$ok,$fail,$notes"))
        }
    }
    $dir = Split-Path -Parent $CsvPath
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    [System.IO.File]::WriteAllLines($CsvPath, $lines, [System.Text.Encoding]::UTF8)
}

# ---------------------------------------------------------------------------
# ETA Helpers
# ---------------------------------------------------------------------------
function Get-EstimatedTimeRemaining {
    param(
        [int]$Completed,
        [int]$Total,
        [array]$Times
    )
    if ($Completed -lt 2 -or $Times.Count -lt 2) { return $null }
    $avgSeconds = ($Times | Measure-Object -Average).Average
    $remaining = $Total - $Completed
    $etaSeconds = [int]($avgSeconds * $remaining)
    $minutes = [int]([math]::Floor($etaSeconds / 60))
    $seconds = $etaSeconds % 60
    return "${minutes}m ${seconds}s"
}

# ---------------------------------------------------------------------------
# Main Backup Flow
# ---------------------------------------------------------------------------
function Start-AndroidBackup {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host " Android ADB Backup Utility v$($Script:Version)" -ForegroundColor Cyan
    Write-Host " Non-destructive | Resumable | PowerShell 5.1" -ForegroundColor Cyan
    if ($WhatIf) {
        Write-Host " *** DRY-RUN MODE — no files will be pulled ***" -ForegroundColor Yellow
    }
    if ($VerifyOnly) {
        Write-Host " *** VERIFY-ONLY MODE — checking existing backups ***" -ForegroundColor Yellow
    }
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""

    # 1. Locate ADB
    $Script:AdbPath = Find-AdbExecutable
    if (-not $Script:AdbPath) {
        Write-Host "[ERROR] adb.exe not found." -ForegroundColor Red
        Write-Host "Place Android Platform-Tools (adb.exe) next to this script,"
        Write-Host "or ensure adb is on PATH. Download from:"
        Write-Host "  https://developer.android.com/tools/releases/platform-tools"
        return 1
    }
    Write-Log "Using ADB: $($Script:AdbPath)" "OK"

    # 1b. Check ADB version
    $adbVersion = Test-AdbVersion

    # 2. Select device
    $Script:SelectedSerial = Select-Device -PreferredSerial $DeviceSerial
    if (-not $Script:SelectedSerial) {
        Write-Log "No usable device. Aborting." "ERROR"
        return 2
    }
    Write-Log "Selected device serial: $($Script:SelectedSerial)" "OK"

    # 3. Collect device info
    Write-Log "Collecting device properties..." "INFO"
    $devInfo = Get-DeviceInfo -Serial $Script:SelectedSerial
    $modelSafe = "Unknown"
    if ($devInfo["ro.product.model"]) {
        $modelSafe = ($devInfo["ro.product.model"] -replace '[\\/:*?"<>|]', '_').Trim()
    }
    $ts = $Script:StartTime.ToString("yyyyMMdd_HHmmss")
    if ($BackupName) {
        $folderName = "Android_Backup_${modelSafe}_${BackupName}_${ts}"
    }
    else {
        $folderName = "Android_Backup_${modelSafe}_${ts}"
    }

    # 4. Determine backup root
    if (-not $BackupRoot) {
        $BackupRoot = Join-Path $Script:ScriptDir "Backups"
    }
    if (-not (Test-Path -LiteralPath $BackupRoot)) {
        try {
            New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
        }
        catch {
            Write-Log "Cannot create backup root: $BackupRoot - $($_.Exception.Message)" "ERROR"
            return 3
        }
    }

    $Script:BackupDir = Join-Path $BackupRoot $folderName
    # Resume detection
    $existingState = $null
    $candidates = Get-ChildItem -LiteralPath $BackupRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "Android_Backup_*" } |
        Sort-Object LastWriteTime -Descending
    foreach ($c in $candidates) {
        $sf = Join-Path $c.FullName "Reports\Backup_State.json"
        if (Test-Path -LiteralPath $sf) {
            $st = Load-BackupState -Path $sf
            if ($st -and $st.Serial -eq $Script:SelectedSerial -and -not $st.Completed) {
                if ($ForceResume) {
                    Write-Log "Auto-resuming incomplete backup: $($c.FullName)" "OK"
                    $Script:BackupDir = $c.FullName
                    $existingState = $st
                    break
                }
                else {
                    Write-Log "Found incomplete backup for this device: $($c.FullName)" "INFO"
                    $ans = Read-Host "Resume this backup? [Y/n]"
                    if ($ans -eq "" -or $ans -match '^[Yy]') {
                        $Script:BackupDir = $c.FullName
                        $existingState = $st
                        break
                    }
                }
            }
        }
    }

    if (-not (Test-Path -LiteralPath $Script:BackupDir)) {
        New-Item -ItemType Directory -Path $Script:BackupDir -Force | Out-Null
    }

    # Subfolders
    $dirs = @(
        "Device_Info",
        "APKs",
        "Packages",
        "Files\Internal_Storage",
        "Files\Full_Internal_Storage",
        "Reports",
        "Restore",
        "Logs"
    )
    foreach ($d in $dirs) {
        $p = Join-Path $Script:BackupDir $d
        if (-not (Test-Path -LiteralPath $p)) {
            New-Item -ItemType Directory -Path $p -Force | Out-Null
        }
    }

    $Script:LogDir = Join-Path $Script:BackupDir "Logs"
    Initialize-Logging -LogDirectory $Script:LogDir
    $Script:StateFile = Join-Path $Script:BackupDir "Reports\Backup_State.json"

    if ($existingState) {
        $Script:State = $existingState
        $Script:State.BackupDir = $Script:BackupDir
        # Update device info on resume
        $Script:State.DeviceInfo = $devInfo
        Write-Log "Resuming previous backup state (device info updated)." "OK"
    }
    else {
        $Script:State = New-BackupState
        $Script:State.Serial = $Script:SelectedSerial
        $Script:State.BackupDir = $Script:BackupDir
        $Script:State.DeviceInfo = $devInfo
    }

    # Save device info text
    $infoTxt = Join-Path $Script:BackupDir "Device_Info\device_info.txt"
    $infoLines = @("Serial=$($Script:SelectedSerial)")
    foreach ($k in $devInfo.Keys) {
        $infoLines += "$k=$($devInfo[$k])"
    }
    [System.IO.File]::WriteAllLines($infoTxt, $infoLines, [System.Text.Encoding]::UTF8)

    # 5. Package backup
    Write-Log "Listing packages..." "INFO"
    $pkgList = Get-PackageList -Serial $Script:SelectedSerial
    $thirdParty = @($pkgList.ThirdParty)
    $Script:State.Stats.TotalPackages = $thirdParty.Count
    Write-Log "Third-party packages: $($thirdParty.Count)" "INFO"

    # Also dump full package lists
    $pkgDir = Join-Path $Script:BackupDir "Packages"
    $pkgList.All | Set-Content -LiteralPath (Join-Path $pkgDir "packages_all.txt") -Encoding UTF8
    $pkgList.ThirdParty | Set-Content -LiteralPath (Join-Path $pkgDir "packages_third_party.txt") -Encoding UTF8
    $pkgList.System | Set-Content -LiteralPath (Join-Path $pkgDir "packages_system.txt") -Encoding UTF8

    # VerifyOnly mode
    if ($VerifyOnly) {
        Write-Host ""
        Write-Host "VERIFY-ONLY MODE: Checking existing APKs..." -ForegroundColor Cyan
        $verifyOk = 0
        $verifyFail = 0
        foreach ($pkg in $thirdParty) {
            $localPkgDir = Join-Path (Join-Path $Script:BackupDir "APKs") $pkg
            if (-not (Test-Path -LiteralPath $localPkgDir)) {
                Write-Log "[MISSING] $pkg — no local directory" "FAILED"
                $verifyFail++
                continue
            }
            $apkFiles = Get-ChildItem -LiteralPath $localPkgDir -Filter "*.apk" -ErrorAction SilentlyContinue
            if (-not $apkFiles -or $apkFiles.Count -eq 0) {
                Write-Log "[MISSING] $pkg — no APK files" "FAILED"
                $verifyFail++
                continue
            }
            $pkgOk = $true
            foreach ($apk in $apkFiles) {
                if (-not (Test-ValidApk -FilePath $apk.FullName)) {
                    Write-Log "[INVALID] $pkg/$($apk.Name) — failed ZIP magic check" "FAILED"
                    $pkgOk = $false
                }
            }
            if ($pkgOk) {
                $verifyOk++
            }
            else {
                $verifyFail++
            }
        }
        Write-Host ""
        Write-Host "Verification complete: $verifyOk OK, $verifyFail failed out of $($thirdParty.Count) packages" -ForegroundColor $(if ($verifyFail -eq 0) { "Green" } else { "Yellow" })
        Close-Logging
        return 0
    }

    $pkgIndex = 0
    $failedPackages = @()
    $partialPackages = @()
    $pkgStartTime = Get-Date

    foreach ($pkg in $thirdParty) {
        $pkgIndex++
        $progress = "[$pkgIndex/$($thirdParty.Count)]"

        # Resume: already successful?
        if ($Script:State.Packages.ContainsKey($pkg)) {
            $prev = $Script:State.Packages[$pkg]
            if ($prev.Status -eq "OK") {
                Write-Log "$progress [SKIP] already backed up: $pkg" "SKIP"
                $Script:State.Stats.SkippedPackages++
                continue
            }
        }

        Write-Log "$progress Processing $pkg" "INFO"
        $pkgEntry = [ordered]@{
            Status  = "PENDING"
            Message = ""
            Apks    = @()
        }

        $remotePathsRaw = @(Get-PackagePaths -Serial $Script:SelectedSerial -PackageName $pkg)
        $remotePaths = New-Object System.Collections.Generic.List[string]
        foreach ($rp in $remotePathsRaw) {
            if ($null -eq $rp -or $rp -eq "") { continue }
            $rpStr = [string]$rp
            if ($rpStr -match '\s+/(data|mnt|system)/') {
                foreach ($part in ($rpStr -split '\s+')) {
                    $part = $part.Trim()
                    if ($part -match '^/' -and $part -match '\.apk') {
                        if (-not $remotePaths.Contains($part)) { $remotePaths.Add($part) }
                    }
                }
            }
            else {
                $part = $rpStr.Trim()
                if ($part -and -not $remotePaths.Contains($part)) { $remotePaths.Add($part) }
            }
        }
        $remotePaths = @($remotePaths.ToArray())

        if ($remotePaths.Count -eq 0) {
            Write-Log "$progress [FAILED] No paths for $pkg" "FAILED"
            $pkgEntry.Status = "FAILED"
            $pkgEntry.Message = "pm path returned nothing"
            $Script:State.Packages[$pkg] = $pkgEntry
            $Script:State.Stats.FailedPackages++
            $failedPackages += $pkg
            Save-BackupState -State $Script:State -Path $Script:StateFile
            continue
        }

        Write-Log "$progress Found $($remotePaths.Count) APK path(s)" "INFO"

        $localPkgDir = Join-Path (Join-Path $Script:BackupDir "APKs") $pkg
        if (-not (Test-Path -LiteralPath $localPkgDir)) {
            New-Item -ItemType Directory -Path $localPkgDir -Force | Out-Null
        }

        $manifestLines = New-Object System.Collections.Generic.List[string]
        $manifestLines.Add("File,RemotePath,SizeBytes,SHA256")
        $allOk = $true
        $apkIdx = 0

        foreach ($remote in $remotePaths) {
            $apkIdx++
            $Script:State.Stats.TotalApks++
            $fileName = [System.IO.Path]::GetFileName($remote)
            if (-not $fileName) { $fileName = "apk_$apkIdx.apk" }
            if ($fileName -eq "base.apk" -or ($apkIdx -eq 1 -and $fileName -notmatch 'split')) {
                $localName = "base.apk"
            }
            else {
                $localName = $fileName
            }
            $localPath = Join-Path $localPkgDir $localName

            # Resume check for this specific APK
            if ((Test-ValidApk -FilePath $localPath)) {
                $size = (Get-Item -LiteralPath $localPath).Length
                $hash = Get-FileSha256 -FilePath $localPath
                Write-Log "$progress [SKIP] already valid: $localName" "SKIP"
                $pkgEntry.Apks += [PSCustomObject]@{
                    File       = $localName
                    RemotePath = $remote
                    SizeBytes  = $size
                    SHA256     = $hash
                    Success    = $true
                }
                $manifestLines.Add("$localName,$remote,$size,$hash")
                $Script:State.Stats.SuccessApks++
                $Script:TotalBytesBackedUp += $size
                continue
            }

            if ($WhatIf) {
                Write-Log "$progress [DRY-RUN] Would pull: $remote -> $localName" "INFO"
                $pkgEntry.Apks += [PSCustomObject]@{
                    File       = $localName
                    RemotePath = $remote
                    SizeBytes  = 0
                    SHA256     = $null
                    Success    = $true
                }
                continue
            }

            Write-Log "$progress [PULL] $remote -> $localName" "PULL"
            $pullResult = Pull-ApkWithRetry -Serial $Script:SelectedSerial -RemotePath $remote -LocalPath $localPath -MaxAttempts $MaxRetries
            if ($pullResult.Success) {
                Write-Log "$progress [OK] $localName ($($pullResult.SizeBytes) bytes)" "OK"
                $pkgEntry.Apks += [PSCustomObject]@{
                    File       = $localName
                    RemotePath = $pullResult.RemotePath
                    SizeBytes  = $pullResult.SizeBytes
                    SHA256     = $pullResult.SHA256
                    Success    = $true
                }
                $manifestLines.Add("$localName,$($pullResult.RemotePath),$($pullResult.SizeBytes),$($pullResult.SHA256)")
                $Script:State.Stats.SuccessApks++
                $Script:TotalBytesBackedUp += $pullResult.SizeBytes
            }
            else {
                Write-Log "$progress [FAILED] $localName" "FAILED"
                $pkgEntry.Apks += [PSCustomObject]@{
                    File       = $localName
                    RemotePath = $remote
                    SizeBytes  = 0
                    SHA256     = $null
                    Success    = $false
                }
                $allOk = $false
                $Script:State.Stats.FailedApks++
            }
        }

        # Write package dump and manifest
        $dumpPath = Join-Path $localPkgDir "package_dump.txt"
        $dumpContent = @(
            "Package=$pkg"
            "RemotePaths:"
        ) + $remotePaths
        [System.IO.File]::WriteAllLines($dumpPath, $dumpContent, [System.Text.Encoding]::UTF8)

        $manifestPath = Join-Path $localPkgDir "APK_Manifest.csv"
        [System.IO.File]::WriteAllLines($manifestPath, $manifestLines, [System.Text.Encoding]::UTF8)

        if ($allOk) {
            $pkgEntry.Status = "OK"
            $Script:State.Stats.SuccessPackages++
            Write-Log "$progress [OK] $pkg" "OK"
        }
        else {
            $pkgEntry.Status = "FAILED"
            $pkgEntry.Message = "One or more APKs failed"
            $Script:State.Stats.FailedPackages++
            $failedPackages += $pkg
            Write-Log "$progress [FAILED] $pkg (partial)" "FAILED"
        }

        $Script:State.Packages[$pkg] = $pkgEntry
        Save-BackupState -State $Script:State -Path $Script:StateFile

        # Track timing for ETA
        $now = Get-Date
        $elapsed = ($now - $pkgStartTime).TotalSeconds
        $Script:PackageTimes += $elapsed
        $pkgStartTime = $now

        # Show ETA
        $eta = Get-EstimatedTimeRemaining -Completed $pkgIndex -Total $thirdParty.Count -Times $Script:PackageTimes
        if ($eta) {
            Write-Log "$progress ETA: ~$eta remaining" "INFO"
        }
    }

    # Print failed/partial package summary
    if ($failedPackages.Count -gt 0) {
        Write-Host ""
        Write-Host "------------------------------------------------------------" -ForegroundColor Yellow
        Write-Host " Failed Packages ($($failedPackages.Count)):" -ForegroundColor Yellow
        foreach ($fp in $failedPackages) {
            Write-Host "   - $fp" -ForegroundColor Yellow
        }
        Write-Host "------------------------------------------------------------" -ForegroundColor Yellow
    }

    # 6. Storage backup (optional)
    if (-not $SkipStorage -and -not $WhatIf) {
        Write-Log "Starting storage backup of common folders..." "INFO"
        $commonFolders = @(
            @{ Remote = "/sdcard/DCIM";           Local = "DCIM" },
            @{ Remote = "/sdcard/Pictures";       Local = "Pictures" },
            @{ Remote = "/sdcard/Movies";         Local = "Movies" },
            @{ Remote = "/sdcard/Download";       Local = "Download" },
            @{ Remote = "/sdcard/Documents";      Local = "Documents" },
            @{ Remote = "/sdcard/Music";          Local = "Music" },
            @{ Remote = "/sdcard/Android/media";  Local = "Android_media" }
        )
        $internalRoot = Join-Path $Script:BackupDir "Files\Internal_Storage"
        foreach ($f in $commonFolders) {
            # Skip already-completed storage folders on resume
            $folderKey = $f.Remote
            if ($Script:State.Storage.ContainsKey($folderKey)) {
                $prevStorage = $Script:State.Storage[$folderKey]
                if ($prevStorage -and $prevStorage.Success) {
                    Write-Log "[SKIP] Storage already backed up: $folderKey" "SKIP"
                    continue
                }
            }
            $localTarget = Join-Path $internalRoot $f.Local
            Write-Log "Storage: $($f.Remote)" "INFO"
            $res = Backup-StorageFolder -Serial $Script:SelectedSerial -RemoteFolder $f.Remote -LocalFolder $localTarget
            $Script:State.Storage[$folderKey] = $res
            if ($res.Success) {
                Write-Log "[OK] $($f.Remote)" "OK"
            }
            elseif ($res.Skipped) {
                Write-Log "[SKIP] $($f.Remote)" "SKIP"
            }
            else {
                Write-Log "[WARN] $($f.Remote) failed" "WARN"
            }
            Save-BackupState -State $Script:State -Path $Script:StateFile
        }

        if ($FullSdcard) {
            Write-Host ""
            Write-Host "[WARN] Full /sdcard backup can be very large and take a long time." -ForegroundColor Yellow
            $confirm = Read-Host "Proceed with full /sdcard pull? [y/N]"
            if ($confirm -match '^[Yy]') {
                $fullLocal = Join-Path $Script:BackupDir "Files\Full_Internal_Storage"
                Write-Log "Pulling full /sdcard (this may take a long time)..." "INFO"
                $res = Backup-StorageFolder -Serial $Script:SelectedSerial -RemoteFolder "/sdcard" -LocalFolder $fullLocal -MaxAttempts 1
                $Script:State.Storage["/sdcard"] = $res
            }
        }
    }
    elseif ($WhatIf) {
        Write-Log "[DRY-RUN] Storage backup skipped (dry-run mode)." "INFO"
    }
    else {
        Write-Log "Storage backup skipped by user." "INFO"
    }

    # 7. Generate restore scripts & reports
    if (-not $WhatIf) {
        New-RestoreScripts -BackupDir $Script:BackupDir -AdbExePath $Script:AdbPath -Serial $Script:SelectedSerial
    }

    $endTime = Get-Date
    $Script:State.Completed = $true
    $Script:State.Stats.TotalBytes = $Script:TotalBytesBackedUp
    Save-BackupState -State $Script:State -Path $Script:StateFile

    $reportPath = Join-Path $Script:BackupDir "Reports\Backup_Report.txt"
    Write-BackupReport -State $Script:State -ReportPath $reportPath -EndTime $endTime

    $csvPath = Join-Path $Script:BackupDir "Reports\Application_Inventory.csv"
    Write-InventoryCsv -State $Script:State -CsvPath $csvPath

    $totalMB = [math]::Round($Script:TotalBytesBackedUp / 1MB, 2)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " Backup finished" -ForegroundColor Green
    Write-Host " Location: $($Script:BackupDir)" -ForegroundColor Green
    Write-Host " Report  : $reportPath" -ForegroundColor Green
    Write-Host " Size    : $totalMB MB" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Log "Backup completed successfully. Total: $totalMB MB" "OK"
    Close-Logging
    return 0
}

# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
try {
    $exitCode = Start-AndroidBackup
    exit $exitCode
}
catch {
    Write-Host "[FATAL] $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ScriptStackTrace) {
        Write-Host $_.ScriptStackTrace -ForegroundColor DarkRed
    }
    Close-Logging
    exit 99
}
finally {
    Close-Logging
}

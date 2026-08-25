# Installs kota for this Windows user: a Start Menu entry and a `kota` command.
# No administrator, no PATH edit, nothing outside your own user profile.
#
#   irm https://raw.githubusercontent.com/ard0x10/kota/main/install.ps1 | iex
#
# Run from a checkout instead and the entries point at the checkout, so
# `git pull` is the whole update:
#
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall -Purge
param(
    [switch]$Uninstall,
    # Also delete the saved accounts and settings. Without it they survive.
    [switch]$Purge
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$ZIP_URL   = 'https://github.com/ard0x10/kota/archive/refs/heads/main.zip'
$HOME_DIR  = Join-Path $env:LOCALAPPDATA 'Programs\kota'
$DATA_DIR  = Join-Path $env:LOCALAPPDATA 'kota'
$START_MENU = [Environment]::GetFolderPath('Programs')
$SHORTCUT  = Join-Path $START_MENU 'kota.lnk'
# WindowsApps is already on the user PATH, so a kota.cmd left there runs from
# any terminal without a PATH edit and without an administrator.
$SHIM_DIR  = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'
$SHIM      = Join-Path $SHIM_DIR 'kota.cmd'

function Say {
    param([string]$Text, [string]$Color = 'Gray')
    Write-Host "  $Text" -ForegroundColor $Color
}

#--------------------------------------------------------------------------
if ($Uninstall) {
    Write-Host ''
    # A running kota holds its own files open, and would put its tray icon
    # back over an install that is meant to be gone.
    # Get-Process carries no command line in Windows PowerShell 5.1; CIM does.
    # Matched on the entry file, not the word, so nothing else is caught.
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*kota*__main__.py*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

    foreach ($path in @($SHIM, $SHORTCUT, $HOME_DIR)) {
        if (Test-Path $path) { Remove-Item $path -Recurse -Force; Say "removed: $path" }
    }
    $run = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    if (Get-ItemProperty -Path $run -Name kota -ErrorAction SilentlyContinue) {
        Remove-ItemProperty -Path $run -Name kota
        Say 'removed: the start-at-sign-in entry'
    }
    if ($Purge) {
        if (Test-Path $DATA_DIR) { Remove-Item $DATA_DIR -Recurse -Force; Say "removed: $DATA_DIR" }
    } elseif (Test-Path $DATA_DIR) {
        Say "kept: $DATA_DIR  (your accounts; -Purge deletes them too)" 'DarkGray'
    }
    Say 'kota is gone.' 'Green'
    Write-Host ''
    return
}

#--------------------------------------------------------------------------
# What it needs
#--------------------------------------------------------------------------
Write-Host ''

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Say 'No python found. Install it with:  winget install Python.Python.3.13' 'Red'
    Write-Host ''
    exit 1
}
$version = & $python.Source -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$version -lt [version]'3.11') {
    Say "Python 3.11 or newer is needed, and this one is $version." 'Red'
    Write-Host ''
    exit 1
}
Say "python $version  ($($python.Source))" 'DarkGray'

& $python.Source -c "import PyQt6.QtWidgets" 2>$null
if ($LASTEXITCODE -ne 0) {
    Say 'Installing PyQt6...'
    & $python.Source -m pip install --user --quiet PyQt6
    if ($LASTEXITCODE -ne 0) {
        Say 'PyQt6 would not install. kota needs it for the window.' 'Red'
        Write-Host ''
        exit 1
    }
}
Say 'PyQt6 is there' 'DarkGray'

#--------------------------------------------------------------------------
# Where the code will live: this checkout, or a copy fetched from GitHub.
#--------------------------------------------------------------------------
$root = $null
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot 'kota\__main__.py'))) {
    $root = $PSScriptRoot
    Say "using the checkout: $root"
} else {
    $temp = Join-Path $env:TEMP ('kota-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temp -Force | Out-Null
    try {
        Say 'downloading kota...'
        $zip = Join-Path $temp 'kota.zip'
        Invoke-WebRequest -Uri $ZIP_URL -OutFile $zip -UseBasicParsing -TimeoutSec 60
        Expand-Archive -Path $zip -DestinationPath $temp -Force
        $unpacked = Get-ChildItem $temp -Directory | Select-Object -First 1
        if (-not $unpacked -or -not (Test-Path (Join-Path $unpacked.FullName 'kota\__main__.py'))) {
            throw 'the download did not contain kota'
        }
        # Replaced whole rather than merged: a file that has left the project
        # should not survive an update by sitting in the old directory.
        if (Test-Path $HOME_DIR) { Remove-Item $HOME_DIR -Recurse -Force }
        New-Item -ItemType Directory -Path (Split-Path $HOME_DIR) -Force | Out-Null
        Move-Item $unpacked.FullName $HOME_DIR
        $root = $HOME_DIR
        Say "installed: $root"
    } catch {
        Say "download failed: $($_.Exception.Message)" 'Red'
        Say 'Clone the repository and run install.ps1 from it instead.' 'DarkGray'
        Write-Host ''
        exit 1
    } finally {
        Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$entry = Join-Path $root 'kota\__main__.py'

# It has to import before anything claims it is installed.
& $python.Source -c "import sys; sys.path.insert(0, r'$root'); import kota.app" 2>$null
if ($LASTEXITCODE -ne 0) {
    Say 'kota will not import from that copy. Nothing was installed.' 'Red'
    Write-Host ''
    exit 1
}

#--------------------------------------------------------------------------
# The Start Menu entry and the kota command
#--------------------------------------------------------------------------
# pythonw runs the window with no console standing behind the tray icon.
$pythonw = Join-Path (Split-Path $python.Source) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $python.Source }

$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($SHORTCUT)
$link.TargetPath = $pythonw
$link.Arguments = "`"$entry`" --gui"
$link.WorkingDirectory = $root
$link.Description = 'kota: Claude quota, in the tray'
$link.Save()
Say "Start Menu: kota"

if (Test-Path $SHIM_DIR) {
    "@echo off`r`n`"$($python.Source)`" `"$entry`" %*" | Out-File $SHIM -Encoding ascii
    Say "command: kota  ($SHIM)"
} else {
    Say "No $SHIM_DIR here, so there is no kota command." 'Yellow'
    Say "Run it as: `"$($python.Source)`" `"$entry`"" 'DarkGray'
}

#--------------------------------------------------------------------------
# A kota function in the PowerShell profile would win over the command, and
# would keep pointing wherever it already points.
#--------------------------------------------------------------------------
if ($PROFILE -and (Test-Path $PROFILE)) {
    if ((Get-Content $PROFILE -Raw) -match '(?m)^\s*(function|Set-Alias)\s+kota\b') {
        Write-Host ''
        Say 'Your PowerShell profile defines kota, and that wins over the' 'Yellow'
        Say 'command installed just now. Remove the line to use this one:' 'Yellow'
        Say $PROFILE 'DarkGray'
    }
}

Write-Host ''
Say 'Installed.' 'Green'
Say "Open kota from the Start Menu, or type 'kota' in a terminal." 'DarkGray'
Say "Add your accounts from the window, or with 'kota capture'." 'DarkGray'
Write-Host ''

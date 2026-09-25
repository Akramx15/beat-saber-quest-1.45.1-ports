[CmdletBinding()]
param(
    [ValidateSet('plan', 'download', 'verify', 'install')]
    [string]$Command = 'plan',
    [string]$Profile = 'recommended',
    [string]$Manifest = (Join-Path $PSScriptRoot 'modpack.json'),
    [string]$Qmods = (Join-Path $PSScriptRoot 'qmods'),
    [string]$Backups = (Join-Path $PSScriptRoot 'private-backups'),
    [string]$Adb = 'adb',
    [string]$Serial,
    [string]$BuildReceipt
)
$ErrorActionPreference = 'Stop'
$pythonCommand = Get-Command py -ErrorAction SilentlyContinue
$pythonArguments = @()
if ($pythonCommand) {
    $pythonArguments += '-3'
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $pythonCommand) {
    throw 'Install Python 3.10 or newer for Windows, then run this command again.'
}
$pythonArguments += @(
    (Join-Path $PSScriptRoot 'manage_modpack.py'), $Command,
    '--profile', $Profile, '--manifest', $Manifest, '--qmods', $Qmods,
    '--backups', $Backups, '--adb', $Adb
)
if ($Serial) { $pythonArguments += @('--serial', $Serial) }
if ($BuildReceipt) { $pythonArguments += @('--build-receipt', $BuildReceipt) }
& $pythonCommand.Source @pythonArguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

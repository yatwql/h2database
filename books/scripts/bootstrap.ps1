# Create books\.venv and install the toolchain dependencies (Windows).
#
#   .\books\scripts\bootstrap.ps1           # runtime extras only
#   .\books\scripts\bootstrap.ps1 -Dev      # + lint/coverage/typecheck
#   .\books\scripts\bootstrap.ps1 -Check    # report state, install nothing
[CmdletBinding()]
param([switch]$Dev, [switch]$Check)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BookDir = Split-Path -Parent $ScriptDir
$Venv = Join-Path $BookDir '.venv'
$Python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
$Req = if ($Dev) { Join-Path $BookDir 'requirements-dev.txt' } else { Join-Path $BookDir 'requirements.txt' }

if ($Check) {
    $VenvPython = Join-Path $Venv 'Scripts\python.exe'
    if (Test-Path $VenvPython) { Write-Host "venv   : $Venv" } else { Write-Host 'venv   : missing (run bootstrap.ps1)' }
    Write-Host "reqs   : $Req"
    exit 0
}

$VenvPython = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path $VenvPython)) { & $Python -m venv $Venv }
& $VenvPython -m pip install -q --upgrade pip
& $VenvPython -m pip install -q -r $Req
Write-Host "bootstrap: $Venv ready ($Req)"

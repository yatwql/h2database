# Thin wrapper: run the books toolchain without typing python paths (Windows).
#
#   .\books\scripts\bookctl.ps1 status
#   .\books\scripts\bookctl.ps1 check
#   .\books\scripts\bookctl.ps1 test --full
#   .\books\scripts\bookctl.ps1 make <args...>
#   .\books\scripts\bookctl.ps1 doctor
#
# Interpreter resolution: books\.venv -> $env:PYTHON -> python.
[CmdletBinding()]
param(
    [Parameter(Position = 0)][string]$Action = 'help',
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BookDir = Split-Path -Parent $ScriptDir
$App = Join-Path $BookDir 'src\python\app\cli.py'
$Make = Join-Path $BookDir 'src\python\make.py'
$VenvPython = Join-Path $BookDir '.venv\Scripts\python.exe'

$Python = if ($env:PYTHON) { $env:PYTHON }
          elseif (Test-Path $VenvPython) { $VenvPython }
          else { 'python' }

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    Write-Error 'python not found; run books\scripts\bootstrap.ps1'
    exit 2
}

switch ($Action) {
    'new'    { & $Python (Join-Path $BookDir 'src\python\app\scaffold.py') @Rest }
    'make'   { & $Python $Make @Rest }
    'doctor' { & $Python $Make 'doctor' }
    'help'   { Get-Content $MyInvocation.MyCommand.Path | Select-Object -First 14 }
    default  { & $Python $App $Action @Rest }
}
exit $LASTEXITCODE

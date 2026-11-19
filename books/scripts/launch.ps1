# Launch the books toolchain (Windows PowerShell).
#
#   .\books\scripts\launch.ps1                  # TUI
#   .\books\scripts\launch.ps1 cli status       # CLI passthrough
#   .\books\scripts\launch.ps1 web --port 8080  # Web console
#
# Requires python on PATH. No business logic here: it only locates the
# interpreter and forwards to books\src\python\app\*.py.
[CmdletBinding()]
param(
    [Parameter(Position = 0)][ValidateSet('cli', 'tui', 'web')][string]$Channel = 'tui',
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $ScriptDir '..\src\python\app'
$VenvPython = Join-Path (Split-Path -Parent $ScriptDir) '.venv\Scripts\python.exe'
$Python = if ($env:PYTHON) { $env:PYTHON }
          elseif (Test-Path $VenvPython) { $VenvPython }
          else { 'python' }

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    Write-Error "python not found; run books\scripts\bootstrap.ps1 or set PYTHON"
    exit 2
}

$Entry = Join-Path $AppDir "$Channel.py"
& $Python $Entry @Rest
exit $LASTEXITCODE

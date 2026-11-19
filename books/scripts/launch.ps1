# Launch the books toolchain (Windows PowerShell).
#
#   .\books\scripts\run.ps1                  # TUI
#   .\books\scripts\run.ps1 cli status       # CLI passthrough
#   .\books\scripts\run.ps1 web --port 8080  # Web console
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
$Python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    Write-Error "python not found; set PYTHON to the interpreter path"
    exit 2
}

$Entry = Join-Path $AppDir "$Channel.py"
& $Python $Entry @Rest
exit $LASTEXITCODE

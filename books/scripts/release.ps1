# Release flow (Windows): status | gate | publish | manifest
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)
$BookDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BookDir '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }
& $Python (Join-Path $BookDir 'src\python\release.py') @Rest

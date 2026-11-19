# Test coverage with the ratchet from base.json [toolchain].coverage_fail_under.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Extra)
$BookDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BookDir '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }
& $Python (Join-Path $BookDir 'src\python\make.py') cover @Extra

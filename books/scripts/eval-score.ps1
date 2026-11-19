# Six-dimension release scorecard (human table, or -Extra json).
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Extra)
$BookDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BookDir '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }
& $Python (Join-Path $BookDir 'src\python\make.py') report @Extra

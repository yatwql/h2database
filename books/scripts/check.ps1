# Local gate runner (Windows). Orchestration lives in check_runner.py.
param(
    [ValidateSet('p0', 'p1', 'p2', 'fast', 'full', 'release')][string]$Tier = 'p0',
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Extra
)
$BookDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BookDir '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }
& $Python (Join-Path $BookDir 'src\python\check_runner.py') --mode $Tier @Extra

# Local gate runner (Windows), mirroring the CI tiers in .github/workflows/book.yml.
#   .\verify.ps1            fast tier
#   .\verify.ps1 full       every gate
#   .\verify.ps1 release    full + slow suite + artifacts
param([ValidateSet('fast', 'full', 'release')][string]$Tier = 'fast')
$ErrorActionPreference = 'Stop'

$BookDir = Split-Path -Parent $PSScriptRoot
$RepoDir = Split-Path -Parent $BookDir
$Python = Join-Path $BookDir '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }
Set-Location $RepoDir

$FastGates = 'architecture,script_contract,style_schema,llm_policy,versions,file_length'

function Say($text) { Write-Host "`n== $text" -ForegroundColor Cyan }

Say 'lint (ruff)'
try { & $Python -m ruff check books/src/python books/src/test }
catch { Write-Warning 'ruff not installed; run pip install -r requirements-dev.txt' }

Say 'structural gates'
& $Python books/src/python/make.py check --only $FastGates

Say 'unit suite (fast tier)'
& $Python books/src/python/make.py test --timings

if ($Tier -ne 'fast') {
    Say 'every gate'
    & $Python books/src/python/make.py check --keep-going --timings
    if ($Tier -eq 'release') {
        Say 'slow suite (browser + pandoc)'
        $env:BOOK_SLOW = '1'
        & $Python books/src/python/make.py test --full --timings
        Say 'deliver artifacts'
        & $Python books/src/python/make.py deliver --timings
    }
}
Say "$Tier tier passed"

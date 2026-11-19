# Point git at the tracked hooks in .githooks/ (pre-commit = P0, pre-push = P1).
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot
if (-not (Test-Path (Join-Path $RepoRoot '.git'))) {
    Write-Error 'not a git checkout'; exit 2
}
git config core.hooksPath .githooks
Write-Host 'installed: core.hooksPath=.githooks'
Write-Host '  pre-commit -> check_runner.py --mode p0 (~16s)'
Write-Host '  pre-push   -> check_runner.py --mode p1'

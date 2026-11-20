# Convenience wrapper: the diff-scoped tier (~2s) of check.ps1
& (Join-Path $PSScriptRoot "check.ps1") -Tier quick @args

# Convenience wrapper: tests-only edit tier of check.ps1
& (Join-Path $PSScriptRoot "check.ps1") -Tier tests @args

# Convenience wrapper: docs-only edit tier of check.ps1
& (Join-Path $PSScriptRoot "check.ps1") -Tier docs @args

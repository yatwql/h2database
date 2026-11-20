# Convenience wrapper: code-only edit tier of check.ps1
& (Join-Path $PSScriptRoot "check.ps1") -Tier code @args

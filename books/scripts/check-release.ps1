# Convenience wrapper: the release tier of check.ps1
& (Join-Path $PSScriptRoot "check.ps1") -Tier release @args

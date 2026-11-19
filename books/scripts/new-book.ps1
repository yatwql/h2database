# Scaffold a new book (or a translation) from the current structure.
#   .\new-book.ps1 ..\my-book --title "My Book"
#   .\new-book.ps1 ..\translation --lang en --title "My Book (EN)"
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)
$BookDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BookDir '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }
& $Python (Join-Path $BookDir 'src\python\core\scaffold.py') @Rest

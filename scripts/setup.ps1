$ErrorActionPreference = 'Stop'

$project = Split-Path -Parent $PSScriptRoot
$bundledPython = 'C:\Users\labar\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$python = if (Test-Path -LiteralPath $bundledPython -PathType Leaf) { $bundledPython } else { 'python' }

Push-Location $project
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe' -PathType Leaf)) {
        & $python -m venv .venv
    }
    & '.\.venv\Scripts\python.exe' -m pip install --disable-pip-version-check -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
finally {
    Pop-Location
}


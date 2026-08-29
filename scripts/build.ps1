param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$OutputName = 'LumaGuard'
)

$ErrorActionPreference = 'Stop'

$project = Split-Path -Parent $PSScriptRoot
$python = Join-Path $project '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'The project virtual environment is missing. Run scripts\setup.ps1 first.'
}

& $python (Join-Path $PSScriptRoot 'create_icon.py')
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }

Push-Location $project
try {
    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --uac-admin `
        --name $OutputName `
        --icon 'assets\lumaguard.ico' `
        --version-file 'assets\version_info.txt' `
        --add-data 'browser-extension;browser-extension' `
        'app.py'
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
}
finally {
    Pop-Location
}

Write-Output (Join-Path $project ("dist\{0}.exe" -f $OutputName))

param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$OutputName = 'Website Blocker'
)

$ErrorActionPreference = 'Stop'

$project = Split-Path -Parent $PSScriptRoot
$python = Join-Path $project '.venv\Scripts\python.exe'
$archiveViewer = Join-Path $project '.venv\Scripts\pyi-archive_viewer.exe'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'The project virtual environment is missing. Run scripts\setup.ps1 first.'
}

if (-not (Test-Path -LiteralPath $archiveViewer -PathType Leaf)) {
    throw 'PyInstaller tools are missing. Run scripts\setup.ps1 first.'
}

# Qt uses the Windows ICU compatibility DLLs. If another application puts its
# own ICU build on PATH, PyInstaller can accidentally bundle that incompatible
# copy and QtCore will fail to load at startup.
$originalPath = $env:Path
$systemDirectory = [Environment]::GetFolderPath([Environment+SpecialFolder]::System)
$safePathEntries = [Collections.Generic.List[string]]::new()
$safePathEntries.Add($systemDirectory)

foreach ($entry in ($originalPath -split [IO.Path]::PathSeparator)) {
    $trimmed = $entry.Trim()
    if (-not $trimmed) { continue }

    try {
        $resolved = [IO.Path]::GetFullPath($trimmed)
    }
    catch {
        $safePathEntries.Add($trimmed)
        continue
    }

    if ($resolved.TrimEnd('\') -eq $systemDirectory.TrimEnd('\')) { continue }
    if (Test-Path -LiteralPath (Join-Path $resolved 'icuuc.dll') -PathType Leaf) {
        Write-Verbose "Excluding incompatible ICU search path: $resolved"
        continue
    }

    $safePathEntries.Add($trimmed)
}

$env:Path = $safePathEntries -join [IO.Path]::PathSeparator

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
        --icon 'assets\website_blocker.ico' `
        --version-file 'assets\version_info.txt' `
        --add-data 'browser-extension;browser-extension' `
        'app.py'
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
}
finally {
    Pop-Location
    $env:Path = $originalPath
}

$outputPath = Join-Path $project ("dist\{0}.exe" -f $OutputName)
$archiveEntries = @(& $archiveViewer -l $outputPath)
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the packaged executable.' }

$bundledIcu = @($archiveEntries | Select-String -Pattern "'(?:icuuc|icuin|icudt\d*)\.dll'" -CaseSensitive:$false)
if ($bundledIcu.Count -gt 0) {
    throw 'The packaged executable contains incompatible non-system ICU DLLs.'
}

Write-Output $outputPath

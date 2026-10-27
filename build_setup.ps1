$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$distDir = Join-Path $projectRoot 'dist'
$buildDir = Join-Path $projectRoot 'build'
$exePath = Join-Path $distDir 'PcRemoteServer.exe'
$setupPath = Join-Path $distDir 'PcRemoteServerSetup.exe'

if (-not (Test-Path -LiteralPath $python)) { throw "Project virtual environment not found: $python" }

New-Item -ItemType Directory -Path $distDir -Force | Out-Null

$hiddenImports = @(
    'winrt.windows.foundation',
    'winrt.windows.devices.bluetooth',
    'winrt.windows.devices.bluetooth.rfcomm',
    'winrt.windows.networking',
    'winrt.windows.networking.sockets',
    'winrt.windows.storage.streams'
)

$pyinstallerArgs = @(
    '-m', 'PyInstaller',
    '--noconfirm', '--clean', '--onefile', '--console',
    '--name', 'PcRemoteServer',
    '--distpath', $distDir,
    '--workpath', (Join-Path $buildDir 'pyinstaller'),
    '--specpath', $buildDir
)
foreach ($module in $hiddenImports) {
    $pyinstallerArgs += @('--hidden-import', $module)
}
$pyinstallerArgs += (Join-Path $projectRoot 'server.py')

Push-Location $projectRoot
try {
    & $python @pyinstallerArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

$setupArgs = @(
    '-m', 'PyInstaller',
    '--noconfirm', '--clean', '--onefile', '--windowed',
    '--name', 'PcRemoteServerSetup',
    '--distpath', $distDir,
    '--workpath', (Join-Path $buildDir 'setup-pyinstaller'),
    '--specpath', $buildDir,
    '--add-data', "$exePath;."
)
$setupArgs += (Join-Path $projectRoot 'setup.py')
Push-Location $projectRoot
try {
    & $python @setupArgs
    if ($LASTEXITCODE -ne 0) { throw "Setup package build failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}
if (-not (Test-Path -LiteralPath $setupPath)) { throw "PyInstaller did not create $setupPath" }

Get-Item -LiteralPath $exePath, $setupPath | Select-Object FullName, Length

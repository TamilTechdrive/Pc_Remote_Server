$ErrorActionPreference = 'Stop'

$installRoot = Join-Path $env:LOCALAPPDATA 'Programs\PCRemoteServer'
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$shortcutPath = Join-Path $startMenu 'PCRemote Server.lnk'
$sourceExe = Join-Path $PSScriptRoot 'PcRemoteServer.exe'

if (-not (Test-Path -LiteralPath $sourceExe)) {
    throw "Installer payload is missing PcRemoteServer.exe."
}

New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
Copy-Item -LiteralPath $sourceExe -Destination (Join-Path $installRoot 'PcRemoteServer.exe') -Force
New-Item -ItemType Directory -Path $startMenu -Force | Out-Null

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $installRoot 'PcRemoteServer.exe'
$shortcut.WorkingDirectory = $installRoot
$shortcut.Description = 'Start the PC Remote server'
$shortcut.Save()

Write-Host 'PC Remote Server installed successfully.'
Write-Host "Installed to: $installRoot"
Write-Host 'Use the PCRemote Server shortcut in the Start menu to start it.'
Read-Host 'Press Enter to close this installer'

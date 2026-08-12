# Unblock Zone.Identifier on a downloaded / copied package so pythonnet DLLs can load.
# Run in PowerShell from the package folder, or:
#   powershell -ExecutionPolicy Bypass -File scripts\unblock-windows.ps1
param(
    [string]$Path = (Get-Location).Path
)

Write-Host "Unblocking files under: $Path"
Get-ChildItem -Path $Path -Recurse -Force -ErrorAction SilentlyContinue |
    Unblock-File -ErrorAction SilentlyContinue
Write-Host "Done. Please run terminal-insight-v2.exe again."

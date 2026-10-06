$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot 'logs\processes.json'
if (Test-Path -LiteralPath $pidFile) {
    foreach ($entry in (Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json)) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($entry.Id)" -ErrorAction SilentlyContinue
        if ($process -and $process.ExecutablePath -and $process.ExecutablePath.StartsWith($projectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            Stop-Process -Id $entry.Id
        }
    }
}
Write-Output 'Stopped recorded project processes.'

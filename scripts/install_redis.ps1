$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$toolsDirectory = Join-Path $projectRoot '.tools'
New-Item -ItemType Directory -Force $toolsDirectory | Out-Null
$archive = Join-Path $toolsDirectory 'redis.zip'
$expectedHash = '281F180EABA420F43EB18D655197D55BF804EB692BC55209264BFB284DA3850F'
if (-not (Test-Path -LiteralPath $archive)) {
    Invoke-WebRequest 'https://github.com/redis-windows/redis-windows/releases/download/8.2.10/Redis-8.2.10-Windows-x64-msys2.zip' -OutFile $archive
}
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expectedHash) {
    throw 'Redis archive checksum does not match the publisher release.'
}
Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $toolsDirectory 'redis') -Force
Write-Output 'Portable Redis verified and extracted. No system service was installed.'

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectRoot 'my_venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    $pythonExecutable = Join-Path $projectRoot '.venv\Scripts\python.exe'
}
$redisExecutable = Join-Path $projectRoot '.tools\redis\Redis-8.2.10-Windows-x64-msys2\redis-server.exe'
$logsDirectory = Join-Path $projectRoot 'logs'
New-Item -ItemType Directory -Force $logsDirectory | Out-Null
$jobs = @()
if (-not (Test-Path -LiteralPath $redisExecutable)) { throw 'Run scripts/install_redis.ps1 first.' }
$jobs += Start-Process -FilePath $redisExecutable -ArgumentList '--bind','127.0.0.1','--port','6379','--save','""','--appendonly','no' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logsDirectory 'redis.log') -RedirectStandardError (Join-Path $logsDirectory 'redis-error.log')
$jobs += Start-Process -FilePath $pythonExecutable -ArgumentList '-m','celery','-A','config','worker','--pool=solo','--loglevel=info','--hostname=talentdesk@%h' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logsDirectory 'celery.log') -RedirectStandardError (Join-Path $logsDirectory 'celery-error.log')
$jobs += Start-Process -FilePath $pythonExecutable -ArgumentList 'manage.py','runserver','127.0.0.1:8000','--noreload' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logsDirectory 'django.log') -RedirectStandardError (Join-Path $logsDirectory 'django-error.log')
$jobs | Select-Object Id,ProcessName | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logsDirectory 'processes.json')
$ready = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/accounts/login/' -TimeoutSec 2
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) { throw 'Django did not become ready. Inspect logs/django-error.log.' }
Write-Output 'Started local Redis, Celery, and Django. Open http://127.0.0.1:8000/. Logs are in logs/.'

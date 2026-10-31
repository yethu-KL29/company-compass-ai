# Start the assignment outside temporary tool/terminal sessions.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimePath = Join-Path $projectRoot 'data/runtime'
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
$vitePath = Join-Path $projectRoot 'frontend/node_modules/vite/bin/vite.js'

function Test-Endpoint([string] $Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Wait-Endpoint([string] $Url, [string] $Name) {
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if (Test-Endpoint $Url) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "$Name did not start. Check the logs in data/runtime."
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Python environment missing. Run uv sync --extra dev --extra neo4j-mcp first.'
}
if (-not (Test-Path -LiteralPath $vitePath)) {
    throw 'Frontend dependencies missing. Run npm ci from frontend first.'
}
$nodePath = (Get-Command node -ErrorAction Stop).Source
New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null

if (-not (Test-Endpoint 'http://127.0.0.1:8010/api/health')) {
    $backend = Start-Process -FilePath $pythonPath `
        -ArgumentList @('-m', 'company_compass.cli', 'serve', '--port', '8010') `
        -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimePath 'backend.stdout.log') `
        -RedirectStandardError (Join-Path $runtimePath 'backend.stderr.log')
    Wait-Endpoint 'http://127.0.0.1:8010/api/health' 'Backend'
    Write-Output "Started backend process $($backend.Id)."
}

if (-not (Test-Endpoint 'http://127.0.0.1:5173/')) {
    $frontend = Start-Process -FilePath $nodePath `
        -ArgumentList @(('"' + $vitePath + '"'), '--host', '127.0.0.1', '--port', '5173', '--strictPort') `
        -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimePath 'frontend.stdout.log') `
        -RedirectStandardError (Join-Path $runtimePath 'frontend.stderr.log')
    Wait-Endpoint 'http://127.0.0.1:5173/' 'Frontend'
    Write-Output "Started frontend process $($frontend.Id)."
}

Wait-Endpoint 'http://127.0.0.1:5173/api/health' 'Frontend API connection'
Write-Output 'Company Compass is available at http://127.0.0.1:5173'
Write-Output 'Process logs are in data/runtime. Running services were left untouched.'

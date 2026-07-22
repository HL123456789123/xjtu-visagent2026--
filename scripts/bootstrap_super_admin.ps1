[CmdletBinding()]
param(
    [string]$ProjectName = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Start Docker Desktop and try again."
}

docker version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Engine is unavailable. Start Docker Desktop and try again."
}

$composeArgs = @("compose")
if ($ProjectName) {
    $composeArgs += @("-p", $ProjectName)
}

$backendId = (& docker @composeArgs ps -q backend).Trim()
if (-not $backendId) {
    throw "The backend service is not running. Run 'docker compose up -d' first."
}

$isRunning = (& docker inspect --format "{{.State.Running}}" $backendId).Trim()
if ($isRunning -ne "true") {
    throw "The backend container is not running. Start it and try again."
}

Write-Host "Starting the one-time VisAgent super administrator bootstrap."
Write-Host "The password will be entered inside the backend container and will not be saved by this script."
Write-Host ""

& docker @composeArgs exec backend uv run --no-sync python scripts/bootstrap_super_admin.py
if ($LASTEXITCODE -ne 0) {
    throw "Super administrator bootstrap did not complete. Review the message above."
}

Write-Host ""
Write-Host "Bootstrap completed. Open http://127.0.0.1:3000 to sign in."

param(
    [string]$DeploymentDirectory,
    [int]$Port = 18080
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $DeploymentDirectory) {
    $currentFile = Join-Path $repoRoot 'backend/runtime/current.json'
    if (-not (Test-Path -LiteralPath $currentFile -PathType Leaf)) { throw 'No prepared local deployment is selected.' }
    $DeploymentDirectory = (Get-Content -LiteralPath $currentFile -Raw | ConvertFrom-Json).directory
}
$deploymentPath = (Resolve-Path -LiteralPath $DeploymentDirectory).Path
$environmentFile = Join-Path $deploymentPath '.env'
$launcherFile = Join-Path $repoRoot 'backend/scripts/run-local-backend.py'
$pythonFile = Join-Path $repoRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $environmentFile -PathType Leaf)) { throw 'Deployment environment file is missing.' }
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Invalid local port.' }
if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) { throw 'Port is already occupied; no existing process was stopped.' }
$stdoutFile = Join-Path $deploymentPath 'server.stdout.log'
$stderrFile = Join-Path $deploymentPath 'server.stderr.log'
$processArguments = @("`"$launcherFile`"", '--env-file', "`"$environmentFile`"", '--port', $Port)
$backendProcess = Start-Process -FilePath $pythonFile -ArgumentList $processArguments -WorkingDirectory (Join-Path $repoRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile -PassThru
$ready = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    $backendProcess.Refresh()
    if ($backendProcess.HasExited) { throw 'Backend exited; inspect its private runtime log.' }
    try {
        $probe = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health/ready" -TimeoutSec 2
        if ($probe.service -eq 'health-new' -and $probe.schema_ready -eq $true) { $ready = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 500
}
$state = @{ processId = $backendProcess.Id; port = $Port; service = 'health-new'; schemaReady = $ready; startedAt = [DateTime]::UtcNow.ToString('o') }
$state | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $deploymentPath 'process.json') -Encoding UTF8
if (-not $ready) { throw 'Backend did not become ready; it was retained for inspection and no other process was stopped.' }
$state | ConvertTo-Json -Compress

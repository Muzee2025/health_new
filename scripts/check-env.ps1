[CmdletBinding()]
param(
    [switch]$Strict,
    [string]$PythonPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$backendVenvPython = Join-Path $backendPath '.venv\Scripts\python.exe'
$rootVenvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$failedChecks = [System.Collections.Generic.List[string]]::new()

function Add-Failure {
    param([string]$Name)
    $script:failedChecks.Add($Name)
}

function Get-CommandPath {
    param([string]$Name)
    $command = Get-Command -Name $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $command) { return $null }
    if (-not [string]::IsNullOrWhiteSpace($command.Source)) { return $command.Source }
    if (-not [string]::IsNullOrWhiteSpace($command.Path)) { return $command.Path }
    return $command.Name
}

function Invoke-VersionCommand {
    param(
        [string]$Executable,
        [string[]]$Arguments = @()
    )
    try {
        $output = @(& $Executable @Arguments 2>$null)
        $code = $LASTEXITCODE
        if ($code -ne 0 -or $output.Count -eq 0) { return $null }
        return ([string]$output[0]).Trim()
    }
    catch {
        return $null
    }
}

Write-Output 'Environment check'
Write-Output ("Project: {0}" -f $projectRoot)
Write-Output ("Mode: {0}" -f $(if ($Strict) { 'Strict' } else { 'Diagnostic' }))

$nodePath = Get-CommandPath 'node'
$nodeVersionText = $null
$nodeOk = $false
if ($null -ne $nodePath) {
    $nodeVersionText = Invoke-VersionCommand -Executable $nodePath -Arguments @('--version')
    if ($null -ne $nodeVersionText -and $nodeVersionText -match '^v?(\d+)\.') {
        $nodeOk = [int]$Matches[1] -ge 18
    }
}
if ($null -eq $nodePath) {
    Write-Output 'Node.js: MISSING'
    Add-Failure 'Node.js >= 18'
}
elseif ($null -eq $nodeVersionText) {
    Write-Output ("Node.js: VERSION UNKNOWN ({0})" -f $nodePath)
    Add-Failure 'Node.js >= 18'
}
else {
    Write-Output ("Node.js: {0} at {1} ({2})" -f $nodeVersionText, $nodePath, $(if ($nodeOk) { 'PASS' } else { 'FAIL: requires >= 18' }))
    if (-not $nodeOk) { Add-Failure 'Node.js >= 18' }
}

$npmPath = Get-CommandPath 'npm'
if ($null -eq $npmPath) {
    Write-Output 'npm: MISSING'
    Add-Failure 'npm available'
}
else {
    $npmVersion = Invoke-VersionCommand -Executable $npmPath -Arguments @('--version')
    if ($null -eq $npmVersion) {
        Write-Output ("npm: VERSION UNKNOWN at {0}" -f $npmPath)
        Add-Failure 'npm available'
    }
    else {
        Write-Output ("npm: {0} at {1} (PASS)" -f $npmVersion, $npmPath)
    }
}

$frontendModules = Join-Path $projectRoot 'node_modules'
if (Test-Path -LiteralPath $frontendModules -PathType Container) {
    Write-Output 'Frontend dependencies (node_modules): PRESENT'
}
else {
    Write-Output 'Frontend dependencies (node_modules): MISSING'
    Add-Failure 'frontend node_modules'
}

$pythonExecutable = $null
$pythonPrefixArguments = @()
$pythonSource = $null
if (-not [string]::IsNullOrWhiteSpace($PythonPath)) {
    if (Test-Path -LiteralPath $PythonPath -PathType Leaf) {
        $pythonExecutable = (Resolve-Path -LiteralPath $PythonPath).Path
        $pythonSource = 'explicit -PythonPath'
    }
    else {
        Write-Output 'Python selection: -PythonPath does not resolve to a file'
        Add-Failure 'Python >= 3.10'
    }
}
elseif (Test-Path -LiteralPath $backendVenvPython -PathType Leaf) {
    $pythonExecutable = $backendVenvPython
    $pythonSource = 'backend .venv'
}
elseif (Test-Path -LiteralPath $rootVenvPython -PathType Leaf) {
    $pythonExecutable = $rootVenvPython
    $pythonSource = 'project .venv'
}
else {
    $pythonExecutable = Get-CommandPath 'python'
    if ($null -ne $pythonExecutable) {
        $pythonSource = 'python command'
    }
    else {
        $pythonExecutable = Get-CommandPath 'py'
        if ($null -ne $pythonExecutable) {
            $pythonPrefixArguments = @('-3')
            $pythonSource = 'py -3 launcher'
        }
    }
}

$pyLauncher = Get-CommandPath 'py'
if ($null -ne $pyLauncher) {
    try {
        $pyCandidates = @(& $pyLauncher -0p 2>$null)
        if ($LASTEXITCODE -eq 0 -and $pyCandidates.Count -gt 0) {
            Write-Output 'Installed Python candidates (py -0p):'
            foreach ($candidateLine in $pyCandidates) {
                if ([string]$candidateLine -match '^\s*-V:\S+\s+\*?\s*(.+?python(?:w)?\.exe)\s*$') {
                    $candidatePath = $Matches[1].Trim()
                    $candidateVersion = Invoke-VersionCommand -Executable $candidatePath -Arguments @('--version')
                    if ($null -eq $candidateVersion) { $candidateVersion = 'VERSION UNKNOWN' }
                    Write-Output ("  {0} ({1})" -f $candidatePath, $candidateVersion)
                }
            }
        }
        else {
            Write-Output 'Installed Python candidates (py -0p): NONE REPORTED'
        }
    }
    catch {
        Write-Output 'Installed Python candidates (py -0p): UNKNOWN'
    }
}
else {
    Write-Output 'Installed Python candidates (py -0p): py launcher MISSING'
}

$pythonVersionCode = 'import sys; print(sys.executable); print(sys.version_info[0], sys.version_info[1], sys.version_info[2], sep=chr(46))'
$pythonActualPath = $null
$pythonVersion = $null
$pythonOk = $false
if ($null -eq $pythonExecutable) {
    Write-Output 'Python: MISSING (no .venv, python, or py launcher found)'
    Add-Failure 'Python >= 3.10'
}
else {
    try {
        $pythonOutput = @(& $pythonExecutable @pythonPrefixArguments -c $pythonVersionCode 2>$null)
        $pythonExitCode = $LASTEXITCODE
        if ($pythonExitCode -eq 0 -and $pythonOutput.Count -ge 2) {
            $pythonActualPath = ([string]$pythonOutput[0]).Trim()
            $pythonVersion = ([string]$pythonOutput[1]).Trim()
            if ($pythonVersion -match '^(\d+)\.(\d+)\.(\d+)$') {
                $pythonOk = ([int]$Matches[1] -gt 3) -or (([int]$Matches[1] -eq 3) -and ([int]$Matches[2] -ge 10))
            }
        }
    }
    catch {
        $pythonVersion = $null
    }
    if ($null -eq $pythonVersion) {
        Write-Output ("Python: VERSION UNKNOWN via {0} ({1})" -f $pythonSource, $pythonExecutable)
        Add-Failure 'Python >= 3.10'
    }
    else {
        Write-Output ("Python: {0} at {1} via {2} ({3})" -f $pythonVersion, $pythonActualPath, $pythonSource, $(if ($pythonOk) { 'PASS' } else { 'FAIL: requires >= 3.10' }))
        if (-not $pythonOk) { Add-Failure 'Python >= 3.10' }
    }
}

if (Test-Path -LiteralPath $backendVenvPython -PathType Leaf) {
    Write-Output 'Backend virtual environment (backend/.venv): PRESENT'
}
else {
    Write-Output 'Backend virtual environment (backend/.venv): MISSING'
}

if (Test-Path -LiteralPath $rootVenvPython -PathType Leaf) {
    Write-Output 'Project virtual environment (.venv): PRESENT'
}
else {
    Write-Output 'Project virtual environment (.venv): MISSING'
}

if ($null -ne $pythonExecutable -and $null -ne $pythonVersion) {
    $dependencyModules = @('fastapi', 'sqlalchemy', 'dotenv', 'jwt', 'jose', 'bcrypt', 'requests', 'uvicorn', 'docx', 'multipart', 'chromadb')
    $moduleProbeCode = 'import importlib.util, sys; [print(m, importlib.util.find_spec(m) is not None) for m in sys.argv[1:]]'
    try {
        $moduleOutput = @(& $pythonExecutable @pythonPrefixArguments -c $moduleProbeCode @dependencyModules 2>$null)
        $moduleExitCode = $LASTEXITCODE
        $moduleStates = @{}
        if ($moduleExitCode -eq 0) {
            foreach ($moduleLine in $moduleOutput) {
                if ([string]$moduleLine -match '^([A-Za-z0-9_]+)\s+(True|False)$') {
                    $moduleStates[$Matches[1]] = ($Matches[2] -eq 'True')
                }
            }
        }
        Write-Output ("Backend module availability (selected Python {0}):" -f $pythonActualPath)
        foreach ($module in $dependencyModules) {
            if ($moduleStates.ContainsKey($module) -and $moduleStates[$module]) {
                Write-Output ("  {0}: PRESENT" -f $module)
            }
            else {
                Write-Output ("  {0}: MISSING" -f $module)
                Add-Failure ("Python module {0}" -f $module)
            }
        }
        $pipOutput = @(& $pythonExecutable @pythonPrefixArguments -m pip check 2>$null)
        $pipExitCode = $LASTEXITCODE
        if ($pipExitCode -eq 0) {
            Write-Output 'Dependency consistency (selected Python pip check): PASS'
        }
        else {
            Write-Output ("Dependency consistency (selected Python pip check): FAIL (exit {0})" -f $pipExitCode)
            Add-Failure 'Python dependency consistency'
        }
    }
    catch {
        Write-Output 'Dependency inspection (selected Python): UNAVAILABLE'
        Add-Failure 'Python dependency inspection'
    }
}
else {
    Write-Output 'Dependency inspection: NOT CHECKED (no usable selected Python)'
    Add-Failure 'Python dependency inspection'
}

Write-Output 'Ports (listening state only):'
foreach ($port in @(8000, 5173, 18080)) {
    $listening = $false
    try {
        $connections = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction Stop)
        $listening = $connections.Count -gt 0
        Write-Output ("  {0}: {1}" -f $port, $(if ($listening) { 'LISTENING' } else { 'NOT LISTENING' }))
    }
    catch {
        $netstatPath = Get-CommandPath 'netstat.exe'
        if ($null -eq $netstatPath) { $netstatPath = Get-CommandPath 'netstat' }
        if ($null -ne $netstatPath) {
            try {
                $netstatLines = @(& $netstatPath -ano 2>$null)
                $listening = @($netstatLines | Where-Object { $_ -match ("^\s*TCP\s+\S+:{0}\s+\S+\s+LISTENING\s+\d+\s*$" -f $port) }).Count -gt 0
                Write-Output ("  {0}: {1}" -f $port, $(if ($listening) { 'LISTENING' } else { 'NOT LISTENING' }))
            }
            catch {
                Write-Output ("  {0}: UNKNOWN" -f $port)
            }
        }
        else {
            Write-Output ("  {0}: UNKNOWN" -f $port)
        }
    }
}

$envFile = Join-Path $backendPath '.env'
$envEntries = @{}
if (Test-Path -LiteralPath $envFile -PathType Leaf) {
    Write-Output 'backend/.env: PRESENT'
    try {
        foreach ($line in [System.IO.File]::ReadAllLines($envFile)) {
            if ($line -match '^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
                $key = $Matches[1]
                $value = $Matches[2].Trim()
                if ($value.Length -gt 0 -and ($value[0] -eq '"' -or $value[0] -eq "'")) {
                    $quote = $value[0]
                    $closingQuote = $value.IndexOf($quote, 1)
                    if ($closingQuote -ge 0) {
                        $content = $value.Substring(1, $closingQuote - 1)
                        $trailing = $value.Substring($closingQuote + 1).Trim()
                        if ($trailing.Length -gt 0 -and -not $trailing.StartsWith('#')) {
                            $content = $value
                        }
                        $value = $content.Trim()
                    }
                }
                else {
                    if ($value.StartsWith('#')) {
                        $value = ''
                    }
                    else {
                        $value = [regex]::Replace($value, '\s+#.*$', '').Trim()
                    }
                }
                $envEntries[$key] = -not [string]::IsNullOrWhiteSpace($value)
            }
        }
    }
    catch {
        Write-Output 'backend/.env: PRESENT (read error; variable states UNKNOWN)'
    }
}
else {
    Write-Output 'backend/.env: MISSING'
}

$requiredEnvNames = @('DATABASE_URL', 'JWT_SECRET_KEY')
foreach ($name in $requiredEnvNames) {
    $state = 'MISSING'
    if (Test-Path -LiteralPath $envFile -PathType Leaf) {
        if ($envEntries.ContainsKey($name)) {
            $state = if ($envEntries[$name]) { 'PRESENT' } else { 'EMPTY' }
        }
    }
    Write-Output ("Required env {0}: {1}" -f $name, $state)
    if ($state -ne 'PRESENT') { Add-Failure ("env {0}" -f $name) }
}

$optionalEnvNames = @('DEEPSEEK_API_KEY', 'QWEN_API_KEY', 'ZHIPU_API_KEY')
foreach ($name in $optionalEnvNames) {
    $state = 'MISSING'
    if (Test-Path -LiteralPath $envFile -PathType Leaf) {
        if ($envEntries.ContainsKey($name)) {
            $state = if ($envEntries[$name]) { 'PRESENT' } else { 'EMPTY' }
        }
    }
    Write-Output ("Optional env {0}: {1}" -f $name, $state)
}

if ($failedChecks.Count -eq 0) {
    Write-Output 'Summary: PASS (all required checks passed)'
    exit 0
}

Write-Output ("Summary: {0} required check(s) failed: {1}" -f $failedChecks.Count, ($failedChecks -join ', '))
if ($Strict) { exit 1 }
exit 0

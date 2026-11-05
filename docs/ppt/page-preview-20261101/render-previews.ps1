param([Parameter(Mandatory=$true)][string]$InputPptx,[Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$renderInput = (Resolve-Path -LiteralPath $InputPptx).Path
if (-not [IO.Path]::IsPathRooted($OutputDirectory)) { $OutputDirectory = Join-Path (Get-Location).Path $OutputDirectory }
$renderAbsoluteOutput = [IO.Path]::GetFullPath($OutputDirectory)
$workspaceTarget = Split-Path -Parent $renderInput
if (-not $renderAbsoluteOutput.StartsWith($workspaceTarget + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Output must stay in this task delivery directory' }
New-Item -ItemType Directory -Force -Path $renderAbsoluteOutput | Out-Null
$renderHash = (Get-FileHash -LiteralPath $renderInput -Algorithm SHA256).Hash
$renderApp = $null
$renderDeck = $null
try {
    $renderApp = New-Object -ComObject PowerPoint.Application
    $renderSecurity = $renderApp.AutomationSecurity
    $renderApp.AutomationSecurity = 3
    $renderDeck = $renderApp.Presentations.Open($renderInput, -1, 0, 0)
    $renderCount = $renderDeck.Slides.Count
    $renderDeck.SaveAs((Join-Path $renderAbsoluteOutput 'optimized.pdf'), 32)
    for ($renderIndex=1; $renderIndex -le $renderCount; $renderIndex++) {
        $renderDeck.Slides.Item($renderIndex).Export((Join-Path $renderAbsoluteOutput ('slide-{0:D2}.png' -f $renderIndex)), 'PNG', 1600, 900)
    }
    $renderDeck.Close()
    $renderDeck = $null
    $renderApp.AutomationSecurity = $renderSecurity
    if ($renderApp.Presentations.Count -eq 0) { $renderApp.Quit() }
    $renderApp = $null
    if ((Get-FileHash -LiteralPath $renderInput -Algorithm SHA256).Hash -ne $renderHash) { throw 'Input changed' }
    [ordered]@{ renderer='PowerPoint COM'; readOnly=$true; sourceSaved=$false; sourceSha256=$renderHash.ToLower(); slideCount=$renderCount; width=1600; height=900; pdf='optimized.pdf' } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $renderAbsoluteOutput 'native-render.json') -Encoding UTF8
    Write-Output ('Native PowerPoint render and PDF: '+$renderCount+' slides')
}
finally {
    if ($null -ne $renderDeck) { $renderDeck.Close() }
    if ($null -ne $renderApp) {
        $renderApp.AutomationSecurity = $renderSecurity
        if ($renderApp.Presentations.Count -eq 0) { $renderApp.Quit() }
    }
}

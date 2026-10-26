param(
    [Parameter(Mandatory=$true)][string]$InputDocx,
    [Parameter(Mandatory=$true)][string]$OutputPdf,
    [Parameter(Mandatory=$true)][string]$Report
)
$ErrorActionPreference = 'Stop'
$inputPath = (Resolve-Path -LiteralPath $InputDocx).Path
$outputPath = [System.IO.Path]::GetFullPath($OutputPdf)
if (Test-Path -LiteralPath $outputPath) { throw 'Use a new PDF path for each render.' }
$wordApp = $null
$wordDocument = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordDocument = $wordApp.Documents.Open($inputPath, $false, $true, $false)
    $wordDocument.ExportAsFixedFormat($outputPath, 17)
    $result = [ordered]@{
        renderer = 'Microsoft Word'
        version = $wordApp.Version
        pages = $wordDocument.ComputeStatistics(2)
        sections = $wordDocument.Sections.Count
        readOnly = $wordDocument.ReadOnly
        input = $inputPath
        pdf = $outputPath
    }
    $result | ConvertTo-Json | Set-Content -LiteralPath $Report -Encoding utf8
    $result | ConvertTo-Json
}
finally {
    if ($null -ne $wordDocument) { $wordDocument.Close(0); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordDocument) }
    if ($null -ne $wordApp) { $wordApp.Quit(); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordApp) }
}

param([Parameter(Mandatory=$true)][string]$InputDocx,[Parameter(Mandatory=$true)][string]$OutputPdf,[switch]$UpdateCopy)
$ErrorActionPreference = 'Stop'
$wordApp = $null
$wordDoc = $null
try {
  $wordApp = New-Object -ComObject Word.Application
  $wordApp.Visible = $false
  $wordApp.DisplayAlerts = 0
  $wordDoc = $wordApp.Documents.Open($InputDocx, $false, (-not $UpdateCopy))
  if ($UpdateCopy) {
    foreach ($tocItem in $wordDoc.TablesOfContents) { $tocItem.Update() }
    $wordDoc.Fields.Update() | Out-Null
    $wordDoc.Repaginate()
    foreach ($tocItem in $wordDoc.TablesOfContents) { $tocItem.UpdatePageNumbers() }
    $wordDoc.Save()
  }
  $wordDoc.Repaginate()
  $wordDoc.ExportAsFixedFormat($OutputPdf, 17)
  Write-Output ('pages=' + $wordDoc.ComputeStatistics(2))
} finally {
  if ($wordDoc) { $wordDoc.Close($false) }
  if ($wordApp) { $wordApp.Quit() }
}

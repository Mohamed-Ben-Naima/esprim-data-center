# Builds the network report: content/*.md -> .docx (node build.js) -> TOC/fields updated + .pdf (Word COM)
# Usage: powershell -ExecutionPolicy Bypass -File 03_Network\report\build.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$docx = Join-Path $here "Rapport_Reseau_GNS3_DC_Casablanca.docx"
$pdf  = Join-Path $here "Rapport_Reseau_GNS3_DC_Casablanca.pdf"

Push-Location (Join-Path $here "_source")
try {
    if (-not (Test-Path node_modules)) { npm install --silent | Out-Null }
    node build.js
    if ($LASTEXITCODE -ne 0) { throw "build.js failed" }
} finally { Pop-Location }

$cscript = Join-Path $env:WINDIR "SysWOW64\cscript.exe"
if (-not (Test-Path $cscript)) { $cscript = "cscript.exe" }
& $cscript //nologo (Join-Path $here "_source\word_export.js") $docx $pdf
if ($LASTEXITCODE -ne 0) { throw "Word export failed" }

# MiRG Chart Editor installer for Windows. Paste into PowerShell:
#   irm https://raw.githubusercontent.com/andrewjfiore/mirg-chart-editor/main/install.ps1 | iex
# Files fetched this way carry no download mark, so Windows opens the launcher without a SmartScreen warning.
# Running it again updates the app and keeps its Python setup, models and your work.
$ErrorActionPreference = 'Stop'
$dir = if ($env:MIRG_DIR) { $env:MIRG_DIR } else { Join-Path $HOME 'MiRG Chart Editor' }
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('mirg-' + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $tmp, $dir | Out-Null
Write-Host "Downloading MiRG Chart Editor into: $dir"
Invoke-WebRequest 'https://github.com/andrewjfiore/mirg-chart-editor/archive/refs/heads/main.zip' -OutFile "$tmp\mirg.zip" -UseBasicParsing
Expand-Archive "$tmp\mirg.zip" -DestinationPath $tmp -Force
Copy-Item -Recurse -Force "$tmp\mirg-chart-editor-main\*" $dir
Write-Host 'Installed. Next time, double-click "Start MiRG (Windows).bat" in that folder.'
Start-Process -FilePath (Join-Path $dir 'Start MiRG (Windows).bat') -WorkingDirectory $dir

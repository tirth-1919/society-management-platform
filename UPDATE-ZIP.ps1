$ErrorActionPreference = "Stop"

# ============================================================
# SOCIETY MAINTENANCE - AUTO UPDATE FULL PROJECT ZIP
# ============================================================

$Project = (Get-Location).Path
$Zip = "C:\Users\HP\Desktop\Society-Maintenance-FULL.zip"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " SOCIETY MAINTENANCE - UPDATE ZIP" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Project: $Project"
Write-Host "ZIP    : $Zip"
Write-Host ""

# ------------------------------------------------------------
# CHECK PROJECT
# ------------------------------------------------------------

if (-not (Test-Path -LiteralPath $Project)) {
    Write-Host "ERROR: Project folder does not exist!" -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------
# REMOVE OLD ZIP
# ------------------------------------------------------------

if (Test-Path -LiteralPath $Zip) {
    Write-Host "Removing old ZIP..." -ForegroundColor Yellow
    Remove-Item -LiteralPath $Zip -Force
}

# ------------------------------------------------------------
# EXCLUDE ONLY GENERATED / ENVIRONMENT FILES
# ------------------------------------------------------------

$ExcludedDirectories = @(
    ".venv",
    "node_modules",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".qodo",
    ".mypy_cache",
    ".cache"
)

Write-Host "Scanning project..." -ForegroundColor Cyan

$Items = Get-ChildItem -LiteralPath $Project -Recurse -File -Force |
    Where-Object {

        $relativePath = $_.FullName.Substring($Project.Length + 1)

        $parts = $relativePath -split '[\\/]'

        $excluded = $false

        foreach ($part in $parts) {
            if ($ExcludedDirectories -contains $part) {
                $excluded = $true
                break
            }
        }

        -not $excluded
    }

Write-Host ""
Write-Host "Files selected: $($Items.Count)" -ForegroundColor Green

if ($Items.Count -eq 0) {
    Write-Host "ERROR: No project files selected!" -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------
# TEMPORARY ZIP BUILD DIRECTORY
# ------------------------------------------------------------

$Temp = Join-Path $env:TEMP "society-maintenance-full-zip"

if (Test-Path $Temp) {
    Remove-Item $Temp -Recurse -Force
}

New-Item -ItemType Directory -Path $Temp -Force | Out-Null

Write-Host "Preparing files..." -ForegroundColor Cyan

# ------------------------------------------------------------
# COPY FILES WHILE PRESERVING PROJECT STRUCTURE
# ------------------------------------------------------------

foreach ($file in $Items) {

    $relative = $file.FullName.Substring($Project.Length + 1)

    $destination = Join-Path $Temp $relative

    $destinationDir = Split-Path $destination -Parent

    if (-not (Test-Path $destinationDir)) {
        New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
    }

    Copy-Item `
        -LiteralPath $file.FullName `
        -Destination $destination `
        -Force
}

# ------------------------------------------------------------
# CREATE ZIP
# ------------------------------------------------------------

Write-Host ""
Write-Host "Creating ZIP..." -ForegroundColor Cyan

Compress-Archive `
    -Path "$Temp\*" `
    -DestinationPath $Zip `
    -CompressionLevel Optimal `
    -Force `
    -ErrorAction Stop

# ------------------------------------------------------------
# CLEAN TEMP
# ------------------------------------------------------------

Remove-Item $Temp -Recurse -Force

# ------------------------------------------------------------
# VERIFY ZIP
# ------------------------------------------------------------

if (-not (Test-Path -LiteralPath $Zip)) {
    Write-Host ""
    Write-Host "ERROR: ZIP was not created!" -ForegroundColor Red
    exit 1
}

$File = Get-Item -LiteralPath $Zip

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " ZIP UPDATED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "ZIP FILE:" -ForegroundColor Cyan
Write-Host $File.FullName
Write-Host ""
Write-Host "SIZE:" -ForegroundColor Cyan
Write-Host "$($File.Length) bytes"
Write-Host ""
Write-Host "SIZE MB:" -ForegroundColor Cyan
Write-Host "$([math]::Round($File.Length / 1MB, 2)) MB"
Write-Host ""
Write-Host "FILES:" -ForegroundColor Cyan
Write-Host $Items.Count
Write-Host ""
Write-Host "UPDATED:" -ForegroundColor Cyan
Write-Host $File.LastWriteTime
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " READY FOR CLAUDE CODE" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green


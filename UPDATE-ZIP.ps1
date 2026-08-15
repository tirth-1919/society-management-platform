$Project = (Get-Location).Path
$Zip = "$env:USERPROFILE\Desktop\society-maintenance-LATEST.zip"

Write-Host "Creating latest project ZIP..." -ForegroundColor Cyan
Write-Host "Project: $Project"

Remove-Item $Zip -Force -ErrorAction SilentlyContinue

$Items = Get-ChildItem $Project -Force | Where-Object {
    $_.Name -notin @(
        "instance",
        ".pytest_cache",
        ".qodo",
        ".ruff_cache",
        "__pycache__",
        ".git",
        "UPDATE-ZIP.ps1"
    )
}

if (-not $Items) {
    Write-Host "ERROR: No project files found!" -ForegroundColor Red
    exit 1
}

Compress-Archive `
    -Path $Items.FullName `
    -DestinationPath $Zip `
    -Force

if (Test-Path $Zip) {
    $File = Get-Item $Zip

    Write-Host ""
    Write-Host "ZIP UPDATED SUCCESSFULLY!" -ForegroundColor Green
    Write-Host "File: $($File.FullName)"
    Write-Host "Size: $($File.Length) bytes"
    Write-Host "Updated: $($File.LastWriteTime)"
}
else {
    Write-Host "ERROR: ZIP was not created!" -ForegroundColor Red
    exit 1
}
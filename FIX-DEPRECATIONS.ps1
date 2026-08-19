$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Society Maintenance - Deprecation Fixer" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$ProjectRoot = (Get-Location).Path

# ------------------------------------------------------------
# BACKUP
# ------------------------------------------------------------

$ParentFolder = Split-Path $ProjectRoot -Parent
$BackupRoot = Join-Path $ParentFolder ("Society-maintenance-backup-" + (Get-Date -Format "yyyyMMdd_HHmmss"))

Write-Host "[1/8] Project:" -ForegroundColor Yellow
Write-Host "      $ProjectRoot"
Write-Host ""

Write-Host "[2/8] Creating backup..." -ForegroundColor Yellow

Copy-Item `
    -Path $ProjectRoot `
    -Destination $BackupRoot `
    -Recurse `
    -Force

Write-Host "      Backup created:" -ForegroundColor Green
Write-Host "      $BackupRoot"
Write-Host ""

# ------------------------------------------------------------
# FIND PYTHON FILES
# ------------------------------------------------------------

$PythonFiles = Get-ChildItem $ProjectRoot -Recurse -File -Filter "*.py" |
    Where-Object {
        $_.FullName -notmatch "\\__pycache__\\" -and
        $_.FullName -notmatch "\\\.git\\" -and
        $_.FullName -notmatch "\\venv\\" -and
        $_.FullName -notmatch "\\.venv\\"
    }

Write-Host "[3/8] Python files found: $($PythonFiles.Count)" -ForegroundColor Yellow
Write-Host ""

# ------------------------------------------------------------
# CREATE / VERIFY app/utils.py
# ------------------------------------------------------------

$UtilsFile = Join-Path $ProjectRoot "app\utils.py"

if (-not (Test-Path $UtilsFile)) {

    @'
"""Application utility helpers."""

from datetime import datetime, timezone


def utcnow():
    """Return current UTC time as a naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
'@ | Set-Content -Path $UtilsFile -Encoding UTF8

    Write-Host "Created app\utils.py" -ForegroundColor Green
}
else {

    $UtilsText = Get-Content $UtilsFile -Raw

    if ($UtilsText -notmatch '(?m)^\s*def\s+utcnow\s*\(') {

        Add-Content -Path $UtilsFile -Value @'


from datetime import datetime, timezone


def utcnow():
    """Return current UTC time as a naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
'@

        Write-Host "Added utcnow() to app\utils.py" -ForegroundColor Green
    }
    else {
        Write-Host "app\utils.py already has utcnow()" -ForegroundColor DarkGray
    }
}

Write-Host ""

# ------------------------------------------------------------
# DATETIME.UTCNOW REPLACEMENT
# ------------------------------------------------------------

Write-Host "[4/8] Replacing datetime.utcnow()..." -ForegroundColor Yellow

$UtcFilesChanged = 0
$UtcOccurrences = 0

foreach ($File in $PythonFiles) {

    if ($File.FullName -eq $UtilsFile) {
        continue
    }

    $Text = Get-Content $File.FullName -Raw

    if ($Text -notmatch 'datetime\.utcnow') {
        continue
    }

    $CountBefore = ([regex]::Matches($Text, 'datetime\.utcnow\(\)')).Count

    # Replace executable occurrences.
    $Text = $Text -replace '\bdatetime\.utcnow\(\)', 'utcnow()'

    # Add helper import if required.
    if ($Text -match '\butcnow\(\)') {

        if ($Text -notmatch '(?m)^\s*from\s+app\.utils\s+import\s+.*\butcnow\b') {

            # Existing app.utils import
            $UtilsImport = [regex]::Match(
                $Text,
                '(?m)^\s*from\s+app\.utils\s+import\s+([^\r\n]+)'
            )

            if ($UtilsImport.Success) {

                $OldImport = $UtilsImport.Value

                if ($OldImport -notmatch '\butcnow\b') {

                    $NewImport = $OldImport.TrimEnd() + ", utcnow"

                    $Text = $Text.Replace(
                        $OldImport,
                        $NewImport
                    )
                }
            }
            else {

                # Safest option: put import at top of file.
                $Text = "from app.utils import utcnow`r`n" + $Text
            }
        }
    }

    Set-Content -Path $File.FullName -Value $Text -Encoding UTF8

    $UtcFilesChanged++
    $UtcOccurrences += $CountBefore

    Write-Host "      Fixed: $($File.FullName)" -ForegroundColor DarkGreen
}

Write-Host ""
Write-Host "      datetime.utcnow() occurrences replaced: $UtcOccurrences" -ForegroundColor Green
Write-Host "      Files changed: $UtcFilesChanged" -ForegroundColor Green
Write-Host ""

# ------------------------------------------------------------
# QUERY.GET REPLACEMENT
# ------------------------------------------------------------

Write-Host "[5/8] Replacing .query.get()..." -ForegroundColor Yellow

$QueryFilesChanged = 0
$QueryOccurrences = 0

foreach ($File in $PythonFiles) {

    $Text = Get-Content $File.FullName -Raw

    if ($Text -notmatch '\.query\.get\(') {
        continue
    }

    $CountBefore = ([regex]::Matches($Text, '\.query\.get\(')).Count

    # Example:
    #
    # User.query.get(user_id)
    #
    # becomes:
    #
    # db.session.get(User, user_id)
    #
    $Text = [regex]::Replace(
        $Text,
        '\b([A-Za-z_][A-Za-z0-9_]*)\.query\.get\(([^()\r\n]+)\)',
        'db.session.get($1, $2)'
    )

    # Make sure db is available from app.models.
    if ($Text -match 'db\.session\.get\(') {

        if ($Text -notmatch '(?m)^\s*from\s+app\.models\s+import\s+.*\bdb\b') {

            $ModelsImport = [regex]::Match(
                $Text,
                '(?m)^\s*from\s+app\.models\s+import\s+([^\r\n]+)'
            )

            if ($ModelsImport.Success) {

                $OldImport = $ModelsImport.Value
                $ImportItems = $ModelsImport.Groups[1].Value.Trim()

                if ($ImportItems -notmatch '\bdb\b') {

                    $NewImport = "from app.models import db, " + $ImportItems

                    $Text = $Text.Replace(
                        $OldImport,
                        $NewImport
                    )
                }
            }
            else {

                $Text = "from app.models import db`r`n" + $Text
            }
        }
    }

    Set-Content -Path $File.FullName -Value $Text -Encoding UTF8

    $QueryFilesChanged++
    $QueryOccurrences += $CountBefore

    Write-Host "      Fixed: $($File.FullName)" -ForegroundColor DarkGreen
}

Write-Host ""
Write-Host ".query.get() occurrences replaced: $QueryOccurrences" -ForegroundColor Green
Write-Host "Files changed: $QueryFilesChanged" -ForegroundColor Green
Write-Host ""

# ------------------------------------------------------------
# ACCOUNTING SPECIAL CASE
# ------------------------------------------------------------

Write-Host "[6/8] Checking accounting.py..." -ForegroundColor Yellow

$AccountingFile = Join-Path $ProjectRoot "app\models\accounting.py"

if (Test-Path $AccountingFile) {

    $AccountingText = Get-Content $AccountingFile -Raw

    $EntryLines = $AccountingText -split "`r?`n" |
        Where-Object {
            $_ -match "entry_date"
        }

    foreach ($Line in $EntryLines) {
        Write-Host "      $($Line.Trim())" -ForegroundColor DarkGray
    }

    if ($AccountingText -match 'entry_date\s*=.*default=utcnow') {
        Write-Host "PASS: accounting.py entry_date uses default=utcnow" -ForegroundColor Green
    }
    elseif ($AccountingText -match 'entry_date\s*=.*default=datetime\.utcnow') {
        Write-Host "WARNING: accounting.py still uses datetime.utcnow for entry_date." -ForegroundColor Yellow
    }
    else {
        Write-Host "INFO: Review accounting.py entry_date manually if necessary." -ForegroundColor Yellow
    }
}
else {
    Write-Host "accounting.py not found." -ForegroundColor DarkGray
}

Write-Host ""

# ------------------------------------------------------------
# FINAL AUDIT
# ------------------------------------------------------------

Write-Host "[7/8] Running final source audit..." -ForegroundColor Yellow
Write-Host ""

$AuditFiles = Get-ChildItem $ProjectRoot -Recurse -File -Filter "*.py" |
    Where-Object {
        $_.FullName -notmatch "\\__pycache__\\" -and
        $_.FullName -notmatch "\\\.git\\" -and
        $_.FullName -notmatch "\\venv\\" -and
        $_.FullName -notmatch "\\.venv\\"
    }

$RemainingUtc = @(
    $AuditFiles |
        Select-String -Pattern "datetime\.utcnow"
)

$RemainingQuery = @(
    $AuditFiles |
        Select-String -Pattern "\.query\.get\("
)

if ($RemainingUtc.Count -eq 0) {

    Write-Host "PASS: datetime.utcnow = 0 occurrences" -ForegroundColor Green
}
else {

    Write-Host "FAIL: datetime.utcnow still found:" -ForegroundColor Red

    foreach ($Match in $RemainingUtc) {
        Write-Host "$($Match.Path):$($Match.LineNumber): $($Match.Line.Trim())" -ForegroundColor Red
    }
}

Write-Host ""

if ($RemainingQuery.Count -eq 0) {

    Write-Host "PASS: .query.get( = 0 occurrences" -ForegroundColor Green
}
else {

    Write-Host "FAIL: .query.get( still found:" -ForegroundColor Red

    foreach ($Match in $RemainingQuery) {
        Write-Host "$($Match.Path):$($Match.LineNumber): $($Match.Line.Trim())" -ForegroundColor Red
    }
}

Write-Host ""

# ------------------------------------------------------------
# RUFF
# ------------------------------------------------------------

Write-Host "[8/8] Running Ruff..." -ForegroundColor Yellow
Write-Host ""

python -m ruff check .

$RuffExit = $LASTEXITCODE

Write-Host ""

if ($RuffExit -eq 0) {
    Write-Host "Ruff: PASS" -ForegroundColor Green
}
else {
    Write-Host "Ruff: FAILED" -ForegroundColor Red
}

# ------------------------------------------------------------
# PYTEST
# ------------------------------------------------------------

Write-Host ""
Write-Host "Running pytest..." -ForegroundColor Yellow
Write-Host ""

python -m pytest

$PytestExit = $LASTEXITCODE

Write-Host ""

if ($PytestExit -eq 0) {
    Write-Host "Pytest: PASS" -ForegroundColor Green
}
else {
    Write-Host "Pytest: FAILED" -ForegroundColor Red
}

# ------------------------------------------------------------
# FINAL RESULT
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " FINAL RESULT" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($RemainingUtc.Count -eq 0 -and $RemainingQuery.Count -eq 0) {
    Write-Host "Deprecation audit: PASS" -ForegroundColor Green
}
else {
    Write-Host "Deprecation audit: REVIEW REQUIRED" -ForegroundColor Red
}

if ($RuffExit -eq 0) {
    Write-Host "Ruff: PASS" -ForegroundColor Green
}
else {
    Write-Host "Ruff: FAILED" -ForegroundColor Red
}

if ($PytestExit -eq 0) {
    Write-Host "Pytest: PASS" -ForegroundColor Green
}
else {
    Write-Host "Pytest: FAILED" -ForegroundColor Red
}

Write-Host ""
Write-Host "Backup location:" -ForegroundColor Yellow
Write-Host $BackupRoot
Write-Host ""
Write-Host "Finished." -ForegroundColor Green
# Patch Fix Script for Ungoogled Chromium Fingerprint Browser
# This script fixes common patch file format issues

Write-Host "=== Patch Fix Script ===" -ForegroundColor Green
Write-Host ""

$patchDir = "patches/extra/fingerprint"
$patchFiles = Get-ChildItem -Path $patchDir -Filter "*.patch"

Write-Host "Fixing patch files in $patchDir..." -ForegroundColor Yellow
Write-Host ""

foreach ($patch in $patchFiles) {
    Write-Host "Fixing $($patch.Name)..." -ForegroundColor Cyan
    
    # Read content as bytes to preserve encoding
    $content = Get-Content $patch.FullName -Raw -Encoding UTF8
    
    # Fix line endings - convert CRLF to LF
    $content = $content -replace "`r`n", "`n"
    
    # Remove trailing whitespace from each line
    $lines = $content -split "`n"
    $fixedLines = @()
    
    foreach ($line in $lines) {
        # Remove trailing whitespace but preserve the line structure
        $fixedLine = $line -replace "\s+$", ""
        $fixedLines += $fixedLine
    }
    
    # Join lines back with LF
    $fixedContent = $fixedLines -join "`n"
    
    # Ensure file ends with a single newline
    if (-not $fixedContent.EndsWith("`n")) {
        $fixedContent += "`n"
    }
    
    # Write back with UTF8 encoding and LF line endings
    [System.IO.File]::WriteAllText($patch.FullName, $fixedContent, [System.Text.UTF8Encoding]::new($false))
    
    Write-Host "  ✅ Fixed" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== All patches have been fixed! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Changes made:" -ForegroundColor Yellow
Write-Host "1. Converted line endings to Unix format (LF)"
Write-Host "2. Removed trailing whitespace"
Write-Host "3. Ensured UTF-8 encoding"
Write-Host ""
Write-Host "Please test the patches to ensure they still apply correctly." -ForegroundColor Cyan 
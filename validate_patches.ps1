# Patch Validation Script for Ungoogled Chromium Fingerprint Browser
# This script validates patch file formats to ensure they can be applied correctly

Write-Host "=== Patch Validation Script ===" -ForegroundColor Green
Write-Host ""

$patchDir = "patches/extra/fingerprint"
$patchFiles = Get-ChildItem -Path $patchDir -Filter "*.patch"

Write-Host "Validating patch files in $patchDir..." -ForegroundColor Yellow
Write-Host ""

$allValid = $true

foreach ($patch in $patchFiles) {
    Write-Host "Checking $($patch.Name)..." -ForegroundColor Cyan
    
    $content = Get-Content $patch.FullName -Raw
    
    # Check for common patch format issues
    $issues = @()
    
    # Check for proper diff headers
    if (-not ($content -match "^diff --git")) {
        $issues += "Missing proper diff header"
    }
    
    # Check for malformed lines (lines that don't start with space, +, -, @, or diff)
    $lines = $content -split "`n"
    for ($i = 0; $i -lt $lines.Length; $i++) {
        $line = $lines[$i]
        if ($line -and -not ($line -match "^[ +\-@\\]|^diff |^index |^--- |^\+\+\+ |^Binary |^new file mode |^deleted file mode |^similarity index |^rename ")) {
            if (-not ($line -match "^[a-zA-Z].*:$|^#|^$")) {
                $issues += "Line $($i+1): Potentially malformed line: '$line'"
            }
        }
    }
    
    # Check for Windows line endings (CRLF)
    if ($content -match "`r`n") {
        $issues += "Contains Windows line endings (CRLF) - should use Unix line endings (LF)"
    }
    
    # Check for trailing whitespace issues
    $trailingSpaceLines = $lines | Where-Object { $_ -match " +$" }
    if ($trailingSpaceLines.Count -gt 0) {
        $issues += "Contains lines with trailing whitespace"
    }
    
    if ($issues.Count -eq 0) {
        Write-Host "  ✅ Valid" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Issues found:" -ForegroundColor Red
        foreach ($issue in $issues) {
            Write-Host "    - $issue" -ForegroundColor Red
        }
        $allValid = $false
    }
    Write-Host ""
}

if ($allValid) {
    Write-Host "=== All patches are valid! ===" -ForegroundColor Green
    exit 0
} else {
    Write-Host "=== Some patches have issues that need to be fixed ===" -ForegroundColor Red
    Write-Host ""
    Write-Host "Common fixes:" -ForegroundColor Yellow
    Write-Host "1. Ensure all files use Unix line endings (LF)"
    Write-Host "2. Remove trailing whitespace"
    Write-Host "3. Check patch format follows standard unified diff format"
    Write-Host "4. Ensure proper diff headers are present"
    exit 1
} 
# Fix all patch files encoding and line endings
$patchFiles = Get-ChildItem "patches/extra/fingerprint/*.patch"

foreach ($file in $patchFiles) {
    Write-Host "Fixing: $($file.Name)"
    
    # Read content with UTF8 encoding
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    
    # Convert CRLF to LF
    $content = $content -replace "`r`n", "`n"
    
    # Remove any trailing whitespace
    $content = $content -replace " +`n", "`n"
    
    # Ensure file ends with single newline
    $content = $content.TrimEnd() + "`n"
    
    # Write back with UTF8 encoding and LF line endings
    [System.IO.File]::WriteAllText($file.FullName, $content, [System.Text.UTF8Encoding]::new($false))
    
    Write-Host "Fixed: $($file.Name)"
}

Write-Host "All patch files have been fixed!" 
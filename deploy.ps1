#!/usr/bin/env pwsh

Write-Host "Deploying to https://github.com/fjlmcm/chromium tag 134.0.6998.165" -ForegroundColor Green
Write-Host ""

# Check if git is available
try {
    git --version | Out-Null
} catch {
    Write-Host "Error: Git is not installed or not in PATH" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if we're in a git repository
if (-not (Test-Path ".git")) {
    Write-Host "Error: Not in a git repository" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Add all changes
Write-Host "Adding all changes..." -ForegroundColor Yellow
git add .

# Commit changes
Write-Host "Committing changes..." -ForegroundColor Yellow
git commit -m "Refactor fingerprint patches: improve font protection, fix coding standards, add English comments"

# Add remote if it doesn't exist
try {
    git remote get-url fjlmcm | Out-Null
} catch {
    Write-Host "Adding remote repository..." -ForegroundColor Yellow
    git remote add fjlmcm https://github.com/fjlmcm/chromium.git
}

# Fetch the remote
Write-Host "Fetching remote repository..." -ForegroundColor Yellow
git fetch fjlmcm

# Check if tag exists
$tagExists = git tag | Select-String "134.0.6998.165"
if (-not $tagExists) {
    Write-Host "Creating tag 134.0.6998.165..." -ForegroundColor Yellow
    git tag 134.0.6998.165
}

# Force push to the specific tag
Write-Host "Force pushing to tag 134.0.6998.165..." -ForegroundColor Yellow
git push fjlmcm HEAD:refs/tags/134.0.6998.165 --force

Write-Host ""
Write-Host "Deployment completed successfully!" -ForegroundColor Green
Write-Host "Repository: https://github.com/fjlmcm/chromium" -ForegroundColor Cyan
Write-Host "Tag: 134.0.6998.165" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit" 
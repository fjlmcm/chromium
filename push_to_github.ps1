# Ungoogled Chromium Fingerprint Browser - GitHub Push Script
# PowerShell version for Windows compatibility

Write-Host "=== Ungoogled Chromium Fingerprint Browser - GitHub Push Script ===" -ForegroundColor Green
Write-Host ""

# Configuration
$REPO_URL = "https://github.com/fjlmcm/chromium.git"
$TAG_NAME = "134.0.6998.165"

# Check if we're in a git repository
if (-not (Test-Path ".git")) {
    Write-Host "Error: Not in a git repository. Please run this script from the project root." -ForegroundColor Red
    exit 1
}

Write-Host "1. Checking current git status..." -ForegroundColor Yellow
git status

Write-Host ""
Write-Host "2. Checking remote repository..." -ForegroundColor Yellow
$remotes = git remote -v
if ($remotes -match "origin") {
    Write-Host "Remote 'origin' already exists."
} else {
    Write-Host "Adding remote 'origin'..."
    git remote add origin $REPO_URL
}

Write-Host ""
Write-Host "3. Pushing to GitHub..." -ForegroundColor Yellow
Write-Host "Pushing main branch..."
git push -u origin master

Write-Host "Pushing tag..."
git push origin $TAG_NAME

Write-Host ""
Write-Host "=== Push completed successfully! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Repository URL: $REPO_URL" -ForegroundColor Cyan
Write-Host "Tag: $TAG_NAME" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Visit the GitHub repository to verify the upload"
Write-Host "2. Create a release from the tag if needed"
Write-Host "3. Update documentation and README as necessary"
Write-Host ""
Write-Host "Build instructions:" -ForegroundColor Yellow
Write-Host "git clone $REPO_URL"
Write-Host "cd chromium"
Write-Host "git checkout $TAG_NAME"
Write-Host "# Follow standard ungoogled-chromium build process" 
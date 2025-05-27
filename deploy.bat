@echo off
echo Deploying to https://github.com/fjlmcm/chromium tag 134.0.6998.165
echo.

REM Check if git is available
git --version >nul 2>&1
if errorlevel 1 (
    echo Error: Git is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if we're in a git repository
if not exist ".git" (
    echo Error: Not in a git repository
    pause
    exit /b 1
)

REM Add all changes
echo Adding all changes...
git add .

REM Commit changes
echo Committing changes...
git commit -m "Refactor fingerprint patches: improve font protection, fix coding standards, add English comments"

REM Add remote if it doesn't exist
git remote get-url fjlmcm >nul 2>&1
if errorlevel 1 (
    echo Adding remote repository...
    git remote add fjlmcm https://github.com/fjlmcm/chromium.git
)

REM Fetch the remote
echo Fetching remote repository...
git fetch fjlmcm

REM Check if tag exists
git tag | findstr "134.0.6998.165" >nul
if errorlevel 1 (
    echo Creating tag 134.0.6998.165...
    git tag 134.0.6998.165
)

REM Force push to the specific tag
echo Force pushing to tag 134.0.6998.165...
git push fjlmcm HEAD:refs/tags/134.0.6998.165 --force

echo.
echo Deployment completed successfully!
echo Repository: https://github.com/fjlmcm/chromium
echo Tag: 134.0.6998.165
echo.
pause 
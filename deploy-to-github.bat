@echo off
REM One-shot deploy script for AI Job Market Impact Tracker.
REM Double-click this file from File Explorer, or run from Command Prompt.

cd /d "%~dp0"

echo ==> Initialising git repo...
git init >nul 2>&1

echo ==> Staging all files...
git add .

echo ==> Creating initial commit...
git -c user.email="ngupta@advanced-workplace.com" -c user.name="Nathan Gupta" commit -m "Initial commit: AI Job Market Impact Tracker"
if errorlevel 1 (
  echo Commit failed - if "nothing to commit", proceeding anyway.
)

echo ==> Renaming branch to main...
git branch -M main

echo ==> Adding remote...
git remote remove origin >nul 2>&1
git remote add origin https://github.com/pallabk9/ai-jobmarket-tracker.git

echo ==> Pushing to GitHub (browser will open for OAuth on first push)...
git push -u origin main
if errorlevel 1 (
  echo Push failed. Try running this from Git Bash instead of cmd.
  pause
  exit /b 1
)

echo.
echo ====================================================
echo  DONE. Tell Claude "push complete" to continue.
echo  Repo: https://github.com/pallabk9/ai-jobmarket-tracker
echo ====================================================
pause

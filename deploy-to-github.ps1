# One-shot deploy script: push this folder to the GitHub repo.
# Run in Windows PowerShell from this folder (netlify-site).
# Git for Windows is required. Browser will open for first-time OAuth.

$ErrorActionPreference = "Stop"
$repo = "https://github.com/pallabk9/ai-jobmarket-tracker.git"

Write-Host "==> Initialising git repo..."
git init | Out-Null

Write-Host "==> Staging all files..."
git add .

Write-Host "==> Creating initial commit..."
git -c user.email="ngupta@advanced-workplace.com" -c user.name="Nathan Gupta" commit -m "Initial commit: AI Job Market Impact Tracker"

Write-Host "==> Renaming branch to main..."
git branch -M main

Write-Host "==> Adding remote..."
try { git remote add origin $repo } catch { git remote set-url origin $repo }

Write-Host "==> Pushing to GitHub (browser will open for OAuth on first push)..."
git push -u origin main

Write-Host ""
Write-Host "===================================================="
Write-Host "  DONE. Tell Claude 'push complete' to continue."
Write-Host "  Repo: $repo"
Write-Host "===================================================="

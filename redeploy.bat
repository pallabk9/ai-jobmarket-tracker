@echo off
REM Push local changes to GitHub. Netlify auto-redeploys on push.
REM Run from this folder. Pass a commit message as the first argument,
REM or accept the default.

cd /d "%~dp0"

set MSG=%~1
if "%MSG%"=="" set MSG=Update site

echo Staging changes...
git add .

echo Committing...
git -c user.email="pallabk9@users.noreply.github.com" -c user.name="Dr. Pallab Kakoti" commit -m "%MSG%"
if errorlevel 1 echo No new changes to commit - will still push any unpushed commits.

echo Pulling latest from GitHub first...
git pull --rebase origin main
if errorlevel 1 (
  echo Pull failed - resolve the conflict shown above, then rerun.
  pause
  exit /b 1
)

echo Pushing to GitHub...
git push origin main
if errorlevel 1 (
  echo Push failed. Try Git Bash instead of cmd, or check your GitHub auth.
  pause
  exit /b 1
)

echo.
echo ====================================================
echo  PUSHED. Netlify will auto-redeploy within ~30 seconds.
echo  Live site: https://ai-jobmarket-tracker.netlify.app
echo ====================================================
pause

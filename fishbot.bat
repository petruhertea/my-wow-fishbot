@echo off
rem Launches python-fishbot from the folder this file lives in, so it works from a shortcut too.
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo uv was not found. Install it from https://docs.astral.sh/uv/ and try again.
    pause
    exit /b 1
)

uv run python-fishbot

rem Keep the window open so any error message can be read.
pause
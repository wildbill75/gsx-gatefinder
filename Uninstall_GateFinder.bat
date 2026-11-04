@echo off
title Uninstall GateFinder
echo ========================================================
echo          GateFinder - MSFS In-Game Panel Uninstaller
echo ========================================================
echo.
echo Launching uninstallation process...
echo.

if exist "%~dp0GateFinder.exe" (
    "%~dp0GateFinder.exe" --uninstall
) else (
    echo [ERROR] GateFinder.exe was not found in the current folder.
    echo Please make sure this script is located next to GateFinder.exe.
    pause
)

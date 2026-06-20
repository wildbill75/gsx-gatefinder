@echo off
echo ========================================================
echo GateFinder MSFS 2020 / 2024 Network Fix
echo ========================================================
echo.
echo Autorisation de la connexion locale pour Flight Simulator...
echo.

CheckNetIsolation.exe LoopbackExempt -a -n="Microsoft.Limitless_8wekyb3d8bbwe"
CheckNetIsolation.exe LoopbackExempt -a -n="Microsoft.FlightSimulator_8wekyb3d8bbwe"

echo.
echo Termine! Vous pouvez fermer cette fenetre.
pause

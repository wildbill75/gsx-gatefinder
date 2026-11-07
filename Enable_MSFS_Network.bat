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
echo Autorisation du port 8420 (GateFinder Web EFB - 2nd PC / Tablet)...
netsh advfirewall firewall delete rule name="GateFinder Web EFB (TCP 8420)" >nul 2>&1
netsh advfirewall firewall add rule name="GateFinder Web EFB (TCP 8420)" dir=in action=allow protocol=TCP localport=8420 profile=private,domain,public >nul 2>&1

echo.
echo Termine! Vous pouvez fermer cette fenetre.
pause

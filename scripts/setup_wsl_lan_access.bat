@echo off
REM Execute como Administrador (clique direito ^> Executar como administrador)
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_wsl_lan_access.ps1"
echo.
pause

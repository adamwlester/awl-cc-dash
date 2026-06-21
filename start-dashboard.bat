@echo off
title AWL Dashboard Launcher
echo.
echo  AWL Multi-Agent Dashboard
echo  ==========================
echo.

:: Start the sidecar API in a new window
echo  Starting sidecar API on port 7690...
start "AWL Sidecar" /d "%~dp0sidecar" python main.py

:: Give the sidecar a moment to bind the port
ping -n 3 127.0.0.1 >nul

:: Clear ELECTRON_RUN_AS_NODE — VS Code / Claude Code terminals set it, which makes the
:: Electron binary run as plain Node and crash on startup. Harmless when launched elsewhere.
set "ELECTRON_RUN_AS_NODE="

:: Start the Electron + Vite frontend
echo  Starting Electron dashboard...
start "AWL Dashboard" /d "%~dp0frontend" cmd /c "npm run dev"

echo.
echo  Both services launching. Close this window anytime.
echo  Sidecar: http://127.0.0.1:7690
echo.

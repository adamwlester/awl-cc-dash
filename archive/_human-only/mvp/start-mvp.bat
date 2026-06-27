@echo off
title AWL Dashboard — FROZEN MVP Launcher
echo.
echo  AWL Multi-Agent Dashboard — FROZEN MVP (reference)
echo  =================================================
echo.

:: Start the sidecar API in a new window (uses this folder's venv)
echo  Starting MVP sidecar API on port 7691...
start "AWL MVP Sidecar" /d "%~dp0sidecar" "%~dp0.venv\Scripts\python.exe" main.py

:: Give the sidecar a moment to bind the port
ping -n 3 127.0.0.1 >nul

:: Clear ELECTRON_RUN_AS_NODE — VS Code / Claude Code terminals set it, which makes the
:: Electron binary run as plain Node and crash on startup. Harmless when launched elsewhere.
set "ELECTRON_RUN_AS_NODE="

:: Start the Electron + Vite frontend
echo  Starting Electron dashboard...
start "AWL MVP Dashboard" /d "%~dp0frontend" cmd /c "npm run dev"

echo.
echo  Both services launching. Close this window anytime.
echo  Sidecar: http://127.0.0.1:7691  (frozen MVP reference, not the build target)
echo.

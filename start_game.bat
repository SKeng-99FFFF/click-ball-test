@echo off
chcp 65001 >nul
echo Starting Aim Trainer v3.4...
echo.

python aim_trainer.py

if errorlevel 1 (
    echo Python is not installed or not in PATH
    echo Please make sure Python and pygame are installed
    echo Install command: pip install pygame
    pause
)
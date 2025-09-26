@echo off
REM SETERA Tools - Automated Installation Batch Wrapper
REM This batch file launches the PowerShell installation script

echo.
echo ==========================================
echo  SETERA Tools - Instalacao Automatizada
echo ==========================================
echo.
echo Este script ira:
echo - Verificar/Instalar Python
echo - Instalar todos os pacotes necessarios
echo - Desabilitar avisos do Windows SmartScreen
echo.

REM Check if PowerShell is available
powershell -Command "Write-Host 'PowerShell disponivel'" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRO: PowerShell nao encontrado!
    echo Este script requer Windows PowerShell ou PowerShell Core.
    pause
    exit /b 1
)

echo Iniciando script PowerShell...
echo.

REM Run the PowerShell script with unrestricted execution policy
powershell -ExecutionPolicy Unrestricted -File "%~dp0instalar.ps1"

if %errorlevel% equ 0 (
    echo.
    echo ===============================================
    echo  INSTALACAO CONCLUIDA COM SUCESSO!
    echo ===============================================
) else (
    echo.
    echo ===============================================
    echo  ERRO DURANTE A INSTALACAO
    echo ===============================================
)

echo.
pause
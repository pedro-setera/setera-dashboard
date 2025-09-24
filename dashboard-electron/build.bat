@echo off
echo =====================================
echo   SETERA Dashboard - Electron Build
echo =====================================
echo.

:: Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Node.js nao encontrado! Por favor, instale Node.js 18+
    echo.
    pause
    exit /b 1
)

echo [INFO] Node.js encontrado:
node --version

:: Install dependencies if node_modules doesn't exist
if not exist "node_modules" (
    echo.
    echo [INFO] Instalando dependencias...
    npm install
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar dependencias!
        echo.
        pause
        exit /b 1
    )
)

:: Build the application
echo.
echo [INFO] Construindo aplicacao Electron...
echo [INFO] Isto pode levar alguns minutos na primeira vez...
echo.
npm run dist

if errorlevel 1 (
    echo [ERRO] Falha na construcao!
    echo.
    pause
    exit /b 1
)

echo.
echo =====================================
echo        BUILD CONCLUIDO COM SUCESSO!
echo =====================================
echo.
echo Arquivo gerado em: .\dist\SETERA-Ferramentas.exe
echo.
echo Para distribuir:
echo 1. Distribua a pasta 'setera-tools' completa
echo 2. O executavel esta em .\dist\SETERA-Ferramentas.exe
echo 3. Usuarios criam atalhos para .\dist\SETERA-Ferramentas.exe
echo.
pause
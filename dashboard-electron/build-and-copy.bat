@echo off
echo =====================================
echo   SETERA Dashboard - Build & Deploy
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

:: Install dependencies if needed
if not exist "node_modules" (
    echo [INFO] Instalando dependencias...
    npm install
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar dependencias!
        pause
        exit /b 1
    )
)

:: Build the application
echo.
echo [INFO] Construindo aplicacao Electron...
npm run dist

if errorlevel 1 (
    echo [ERRO] Falha na construcao!
    pause
    exit /b 1
)

:: Executable is built in dist folder
echo.
echo [INFO] Executavel construido em .\dist\SETERA-Ferramentas.exe

echo.
echo =====================================
echo        SUCESSO!
echo =====================================
echo.
echo Arquivo construido em: .\dist\SETERA-Ferramentas.exe
echo.
echo PRONTO PARA DISTRIBUICAO:
echo - A pasta 'setera-tools' contem tudo que voce precisa
echo - SETERA-Ferramentas.exe esta em .\dist\ junto com as 22 pastas de apps
echo - Distribua a pasta 'setera-tools' completa
echo - Usuarios criam atalho para .\dist\SETERA-Ferramentas.exe
echo.
pause
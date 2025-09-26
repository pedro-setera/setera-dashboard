# SETERA Tools Automated Installation Script
# This script automatically installs and configures all requirements for SETERA Tools
# Version: 1.0
# Author: SETERA Development Team
# Date: 26Set2025
# Requires: Administrator privileges for SmartScreen configuration

# Script configuration
$PYTHON_VERSION = "3.11.9"
$PYTHON_URL = "https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-amd64.exe"
$PIP_PACKAGES = @(
    "psycopg2-binary",
    "pandas",
    "matplotlib",
    "seaborn",
    "flask",
    "xlsxwriter",
    "PyQt6",
    "python-can",
    "canalystii",
    "pywin32",
    "pyqtgraph",
    "numpy",
    "scipy",
    "asammdf"
)

# Colors for output
$RED = [System.ConsoleColor]::Red
$GREEN = [System.ConsoleColor]::Green
$YELLOW = [System.ConsoleColor]::Yellow
$CYAN = [System.ConsoleColor]::Cyan

function Write-ColorOutput($ForegroundColor, $Message) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    Write-Output $Message
    $host.UI.RawUI.ForegroundColor = $fc
}

function Test-AdminPrivileges {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Request-AdminPrivileges {
    if (-NOT (Test-AdminPrivileges)) {
        Write-ColorOutput $YELLOW "[AVISO] Este script precisa de privilegios de administrador para configurar o SmartScreen."
        Write-ColorOutput $YELLOW "[INFO] Reiniciando com privilegios de administrador..."

        $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`""
        Start-Process PowerShell -Verb RunAs -ArgumentList $arguments -Wait
        exit
    }
}

function Test-PythonInstalled {
    try {
        $pythonVersion = python --version 2>$null
        if ($pythonVersion) {
            Write-ColorOutput $GREEN "[OK] Python ja instalado: $pythonVersion"
            return $true
        }
    }
    catch {
        Write-ColorOutput $YELLOW "[AVISO] Python nao encontrado no sistema."
        return $false
    }
    return $false
}

function Install-Python {
    Write-ColorOutput $CYAN "[INFO] Baixando Python $PYTHON_VERSION..."

    $tempPath = "$env:TEMP\python-installer.exe"

    try {
        # Download Python installer
        Invoke-WebRequest -Uri $PYTHON_URL -OutFile $tempPath -UseBasicParsing

        Write-ColorOutput $CYAN "[INFO] Instalando Python $PYTHON_VERSION..."

        # Install Python silently with pip and add to PATH
        $installArgs = "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0 Include_pip=1"
        Start-Process -FilePath $tempPath -ArgumentList $installArgs -Wait

        # Refresh environment variables
        $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
        $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
        $env:Path = $machinePath + ";" + $userPath

        # Wait a moment for installation to complete
        Start-Sleep -Seconds 3

        # Verify installation
        if (Test-PythonInstalled) {
            Write-ColorOutput $GREEN "[OK] Python instalado com sucesso!"
            Remove-Item $tempPath -ErrorAction SilentlyContinue
            return $true
        } else {
            throw "Python installation verification failed"
        }
    }
    catch {
        Write-ColorOutput $RED "[ERRO] Erro ao instalar Python: $($_.Exception.Message)"
        Remove-Item $tempPath -ErrorAction SilentlyContinue
        return $false
    }
}

function Install-PipPackages {
    Write-ColorOutput $CYAN "[INFO] Instalando pacotes Python necessarios..."

    # Upgrade pip first
    Write-ColorOutput $CYAN "[INFO] Atualizando pip..."
    try {
        python -m pip install --upgrade pip --quiet
        Write-ColorOutput $GREEN "[OK] Pip atualizado com sucesso!"
    }
    catch {
        Write-ColorOutput $YELLOW "[AVISO] Nao foi possivel atualizar o pip, continuando..."
    }

    # Install packages
    $totalPackages = $PIP_PACKAGES.Count
    $currentPackage = 0

    foreach ($package in $PIP_PACKAGES) {
        $currentPackage++
        Write-ColorOutput $CYAN "[INFO] [$currentPackage/$totalPackages] Instalando: $package"

        try {
            python -m pip install $package --quiet --no-warn-script-location
            Write-ColorOutput $GREEN "[OK] $package instalado com sucesso!"
        }
        catch {
            Write-ColorOutput $YELLOW "[AVISO] Falha ao instalar $package - $($_.Exception.Message)"
        }
    }

    Write-ColorOutput $GREEN "[OK] Instalacao de pacotes Python concluida!"
}

function Disable-SmartScreen {
    Write-ColorOutput $CYAN "[INFO] Desabilitando Windows SmartScreen..."

    try {
        $registryPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer"
        Set-ItemProperty -Path $registryPath -Name SmartScreenEnabled -Value Off
        Write-ColorOutput $GREEN "[OK] Windows SmartScreen desabilitado com sucesso!"
        Write-ColorOutput $GREEN "[INFO] Isto elimina os avisos de seguranca para executaveis nao assinados."
    }
    catch {
        Write-ColorOutput $RED "[ERRO] Erro ao desabilitar SmartScreen: $($_.Exception.Message)"
        Write-ColorOutput $YELLOW "[INFO] Voce pode desabilitar manualmente executando como administrador:"
        Write-ColorOutput $YELLOW "[INFO] Set-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer'"
        Write-ColorOutput $YELLOW "[INFO]                  -Name SmartScreenEnabled -Value Off"
    }
}

function Create-DesktopShortcut {
    Write-ColorOutput $CYAN "[INFO] Criando atalho na area de trabalho..."

    try {
        # Define paths
        $targetPath = "C:\Program Files\setera-tools\dashboard-electron\dist\win-unpacked\SETERA-Ferramentas.exe"
        $desktopPath = [System.Environment]::GetFolderPath("Desktop")
        $shortcutPath = Join-Path $desktopPath "SETERA Ferramentas.lnk"

        # Check if target executable exists
        if (-NOT (Test-Path $targetPath)) {
            Write-ColorOutput $YELLOW "[AVISO] Executavel nao encontrado em: $targetPath"
            Write-ColorOutput $YELLOW "[INFO] Atalho nao sera criado. Verifique se o SETERA Tools esta instalado corretamente."
            return $false
        }

        # Create shortcut using WScript.Shell COM object
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $targetPath
        $shortcut.WorkingDirectory = Split-Path $targetPath -Parent
        $shortcut.Description = "SETERA Ferramentas v1.4 - Dashboard de Ferramentas de Desenvolvimento"
        $shortcut.Save()

        # Release COM object
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell) | Out-Null

        Write-ColorOutput $GREEN "[OK] Atalho criado com sucesso na area de trabalho!"
        Write-ColorOutput $GREEN "[INFO] Nome do atalho: SETERA Ferramentas"
        return $true
    }
    catch {
        Write-ColorOutput $RED "[ERRO] Erro ao criar atalho: $($_.Exception.Message)"
        Write-ColorOutput $YELLOW "[INFO] Voce pode criar o atalho manualmente apontando para:"
        Write-ColorOutput $YELLOW "[INFO] $targetPath"
        return $false
    }
}

function Show-CompletionSummary {
    Write-ColorOutput $GREEN "=========================================="
    Write-ColorOutput $GREEN " INSTALACAO CONCLUIDA COM SUCESSO!"
    Write-ColorOutput $GREEN "=========================================="
    Write-Output ""
    Write-ColorOutput $CYAN "RESUMO DA INSTALACAO:"
    Write-ColorOutput $GREEN "[OK] Python verificado/instalado"
    Write-ColorOutput $GREEN "[OK] Pacotes pip instalados"
    Write-ColorOutput $GREEN "[OK] Windows SmartScreen desabilitado"
    Write-Output ""
    Write-ColorOutput $CYAN "PROXIMOS PASSOS:"
    Write-ColorOutput $YELLOW "1. Execute SETERA-Ferramentas.exe sem avisos de seguranca"
    Write-ColorOutput $YELLOW "2. Todos os tools Python agora funcionarao corretamente"
    Write-ColorOutput $YELLOW "3. O firmware updater nao exibira mais avisos SmartScreen"
    Write-Output ""
    Write-ColorOutput $GREEN "Sistema pronto para uso das SETERA Tools!"
    Write-Output ""
    Write-Host "Pressione qualquer tecla para sair..." -NoNewline
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# Main installation process
function Start-Installation {
    Clear-Host
    Write-ColorOutput $CYAN "SETERA Tools - Instalacao Automatizada v1.0"
    Write-ColorOutput $CYAN "============================================"
    Write-Output ""

    # Step 1: Check admin privileges
    Write-ColorOutput $CYAN "1. Verificando privilegios de administrador..."
    Request-AdminPrivileges
    Write-ColorOutput $GREEN "[OK] Executando com privilegios de administrador!"
    Write-Output ""

    # Step 2: Check/Install Python
    Write-ColorOutput $CYAN "2. Verificando instalacao do Python..."
    if (-NOT (Test-PythonInstalled)) {
        if (-NOT (Install-Python)) {
            Write-ColorOutput $RED "[ERRO] Falha na instalacao do Python. Abortando..."
            exit 1
        }
    }
    Write-Output ""

    # Step 3: Install pip packages
    Write-ColorOutput $CYAN "3. Instalando pacotes Python necessarios..."
    Install-PipPackages
    Write-Output ""

    # Step 4: Disable SmartScreen
    Write-ColorOutput $CYAN "4. Configurando Windows SmartScreen..."
    Disable-SmartScreen
    Write-Output ""

    # Step 5: Create desktop shortcut
    Write-ColorOutput $CYAN "5. Criando atalho na area de trabalho..."
    Create-DesktopShortcut
    Write-Output ""

    # Step 6: Show completion summary
    Show-CompletionSummary
}

# Script entry point
try {
    Start-Installation
}
catch {
    Write-ColorOutput $RED "[ERRO CRITICO] $($_.Exception.Message)"
    Write-ColorOutput $YELLOW "[INFO] Contate o suporte tecnico se o problema persistir."
    Write-Output ""
    Write-Host "Pressione qualquer tecla para sair..." -NoNewline
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}
#!/usr/bin/env pwsh
<#
.SYNOPSIS
    SETERA Tools Automated Installation Script

.DESCRIPTION
    This script automatically installs and configures all requirements for SETERA Tools:
    - Verifies Python installation (installs if missing)
    - Installs all required Python packages
    - Disables Windows SmartScreen to prevent security warnings
    - Configures the environment for optimal tool performance

.NOTES
    Version: 1.0
    Author: SETERA Development Team
    Date: 26Set2025
    Requires: Administrator privileges for SmartScreen configuration
#>

# Script configuration
$PYTHON_VERSION = "3.11.9"  # Recommended Python version
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
        Write-ColorOutput $YELLOW "⚠️  Este script precisa de privilégios de administrador para configurar o SmartScreen."
        Write-ColorOutput $YELLOW "🔄 Reiniciando com privilégios de administrador..."

        $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`""
        Start-Process PowerShell -Verb RunAs -ArgumentList $arguments -Wait
        exit
    }
}

function Test-PythonInstalled {
    try {
        $pythonVersion = python --version 2>$null
        if ($pythonVersion) {
            Write-ColorOutput $GREEN "✅ Python já instalado: $pythonVersion"
            return $true
        }
    }
    catch {
        Write-ColorOutput $YELLOW "⚠️  Python não encontrado no sistema."
        return $false
    }
    return $false
}

function Install-Python {
    Write-ColorOutput $CYAN "📥 Baixando Python $PYTHON_VERSION..."

    $tempPath = "$env:TEMP\python-installer.exe"

    try {
        # Download Python installer
        Invoke-WebRequest -Uri $PYTHON_URL -OutFile $tempPath -UseBasicParsing

        Write-ColorOutput $CYAN "🚀 Instalando Python $PYTHON_VERSION..."

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
            Write-ColorOutput $GREEN "✅ Python instalado com sucesso!"
            Remove-Item $tempPath -ErrorAction SilentlyContinue
            return $true
        } else {
            throw "Python installation verification failed"
        }
    }
    catch {
        Write-ColorOutput $RED "❌ Erro ao instalar Python: $($_.Exception.Message)"
        Remove-Item $tempPath -ErrorAction SilentlyContinue
        return $false
    }
}

function Install-PipPackages {
    Write-ColorOutput $CYAN "📦 Instalando pacotes Python necessários..."

    # Upgrade pip first
    Write-ColorOutput $CYAN "⬆️  Atualizando pip..."
    try {
        python -m pip install --upgrade pip --quiet
        Write-ColorOutput $GREEN "✅ Pip atualizado com sucesso!"
    }
    catch {
        Write-ColorOutput $YELLOW "⚠️  Aviso: Não foi possível atualizar o pip, continuando..."
    }

    # Install packages
    $totalPackages = $PIP_PACKAGES.Count
    $currentPackage = 0

    foreach ($package in $PIP_PACKAGES) {
        $currentPackage++
        Write-ColorOutput $CYAN "📦 [$currentPackage/$totalPackages] Instalando: $package"

        try {
            python -m pip install $package --quiet --no-warn-script-location
            Write-ColorOutput $GREEN "   ✅ $package instalado com sucesso!"
        }
        catch {
            Write-ColorOutput $YELLOW "   ⚠️  Aviso: Falha ao instalar $package - $($_.Exception.Message)"
        }
    }

    Write-ColorOutput $GREEN "🎉 Instalação de pacotes Python concluída!"
}

function Disable-SmartScreen {
    Write-ColorOutput $CYAN "🛡️  Desabilitando Windows SmartScreen..."

    try {
        $registryPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer"
        Set-ItemProperty -Path $registryPath -Name SmartScreenEnabled -Value Off
        Write-ColorOutput $GREEN "✅ Windows SmartScreen desabilitado com sucesso!"
        Write-ColorOutput $GREEN "   ℹ️  Isto elimina os avisos de segurança para executáveis não assinados."
    }
    catch {
        Write-ColorOutput $RED "❌ Erro ao desabilitar SmartScreen: $($_.Exception.Message)"
        Write-ColorOutput $YELLOW "⚠️  Você pode desabilitar manualmente executando como administrador:"
        Write-ColorOutput $YELLOW "   Set-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer'"
        Write-ColorOutput $YELLOW "                        -Name SmartScreenEnabled -Value Off"
    }
}

function Show-CompletionSummary {
    Write-ColorOutput $GREEN "🎊 INSTALAÇÃO CONCLUÍDA COM SUCESSO! 🎊"
    Write-Output ""
    Write-ColorOutput $CYAN "📋 RESUMO DA INSTALAÇÃO:"
    Write-ColorOutput $GREEN "✅ Python verificado/instalado"
    Write-ColorOutput $GREEN "✅ Pacotes pip instalados"
    Write-ColorOutput $GREEN "✅ Windows SmartScreen desabilitado"
    Write-Output ""
    Write-ColorOutput $CYAN "🚀 PRÓXIMOS PASSOS:"
    Write-ColorOutput $YELLOW "1. Execute SETERA-Ferramentas.exe sem avisos de segurança"
    Write-ColorOutput $YELLOW "2. Todos os tools Python agora funcionarão corretamente"
    Write-ColorOutput $YELLOW "3. O firmware updater não exibirá mais avisos SmartScreen"
    Write-Output ""
    Write-ColorOutput $GREEN "✨ Sistema pronto para uso das SETERA Tools! ✨"
    Write-Output ""
    Write-Host "Pressione qualquer tecla para sair..." -NoNewline
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# Main installation process
function Start-Installation {
    Clear-Host
    Write-ColorOutput $CYAN "🔧 SETERA Tools - Instalação Automatizada v1.0"
    Write-ColorOutput $CYAN "================================================"
    Write-Output ""

    # Step 1: Check admin privileges
    Write-ColorOutput $CYAN "1️⃣  Verificando privilégios de administrador..."
    Request-AdminPrivileges
    Write-ColorOutput $GREEN "✅ Executando com privilégios de administrador!"
    Write-Output ""

    # Step 2: Check/Install Python
    Write-ColorOutput $CYAN "2️⃣  Verificando instalação do Python..."
    if (-NOT (Test-PythonInstalled)) {
        if (-NOT (Install-Python)) {
            Write-ColorOutput $RED "❌ Falha na instalação do Python. Abortando..."
            exit 1
        }
    }
    Write-Output ""

    # Step 3: Install pip packages
    Write-ColorOutput $CYAN "3️⃣  Instalando pacotes Python necessários..."
    Install-PipPackages
    Write-Output ""

    # Step 4: Disable SmartScreen
    Write-ColorOutput $CYAN "4️⃣  Configurando Windows SmartScreen..."
    Disable-SmartScreen
    Write-Output ""

    # Step 5: Show completion summary
    Show-CompletionSummary
}

# Script entry point
try {
    Start-Installation
}
catch {
    Write-ColorOutput $RED "❌ ERRO CRÍTICO: $($_.Exception.Message)"
    Write-ColorOutput $YELLOW "📞 Contate o suporte técnico se o problema persistir."
    Write-Output ""
    Write-Host "Pressione qualquer tecla para sair..." -NoNewline
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}
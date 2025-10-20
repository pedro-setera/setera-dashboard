# SETERA Dashboard - Electron Desktop Application

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ installed
- Python 3.x installed (for launching tools)

### Installation
1. Navigate to this directory in terminal/command prompt
2. Install dependencies:
   ```bash
   npm install
   ```

### Development
Run in development mode:
```bash
npm run dev
```

### Building Portable Executable

To create a portable executable for distribution:

```bash
npm run dist
```

This will create:
- `dist/SETERA-Ferramentas.exe` - Portable executable in `dist/win-unpacked/` folder

### Distribution

1. The portable executable is self-contained
2. Users should place the entire `dist` folder on their computers
3. Users can create their own desktop shortcuts to the `.exe` file
4. **Important**: The tools directory must be available relative to the executable

## 📁 Project Structure

```
dashboard-electron/
├── src/
│   ├── main.js          # Electron main process
│   ├── preload.js       # Preload script for security
│   └── renderer/        # Web UI files
│       ├── dashboard.html
│       └── static/
├── assets/
│   └── icon.ico        # Application icon
├── package.json
└── README.md
```

## ⚡ Features

- **Instant startup** - No server startup delay
- **Maximized window** - Starts maximized automatically
- **Portable** - Single executable, no installation required
- **Same UI** - Identical interface to web version
- **Python integration** - Launches all existing tools
- **Search functionality** - Fast application search
- **Keyboard shortcuts** - Ctrl+F, F11, etc.

## 🛠️ Technical Details

- **Frontend**: HTML5, CSS3, JavaScript (same as original)
- **Backend**: Express.js server embedded in Electron
- **Process**: Node.js child_process for launching applications
- **Security**: Context isolation enabled
- **Build**: Electron Builder for packaging

## 📋 Build Notes

- The app expects the tools to be in a relative `tools` directory
- In development mode (`--dev`), it looks for tools in `../../..` (relative to project)
- In production, it looks for tools relative to the executable location
- All Python scripts are launched with proper working directories

## 📝 Changelog

### v1.60 - 20Out2025
- **Novo**: Adicionado "Config STR-CAM via SMS" na seção Configuração e Atualização
  - Sistema automatizado de envio de comandos SMS para múltiplos dispositivos GPS STR-CAM
  - Interface gráfica moderna com ttkbootstrap (tema escuro)
  - Integração com API SETERA para busca automática de terminais STR-CAM
  - Multi-seleção de terminais e command queue builder (3 terminais × 2 comandos = 6 entradas)
  - Sistema inteligente de validação de respostas com pattern matching
  - Monitoramento em tempo real com código de cores e logs detalhados
  - Suporte a Arduino Uno R4 + Shield SIM800C para envio de SMS via AT commands
  - Controles de pausa/retomada, importação em lote e exportação de logs

### v1.59 - 17Out2025
- **Novo**: Adicionado "Atualiza Módulo Áudio" na seção Configuração e Atualização
  - Ferramenta para atualização de firmware do módulo de áudio WTV380/Waytronic via UART
  - Interface gráfica com progress bar e logging detalhado
  - Suporta flooding handshake e protocolo proprietário de atualização
  - Auto-detecção de arquivos .bin no diretório da ferramenta

### v1.58 - 16Out2025
- **Atualização**: Config/Update STR1010/600P (remoto) agora utiliza Config_STR1010_v127_16Out2025.exe
  - Versão atualizada da ferramenta de configuração remota

### v1.57 - 14Out2025
- **Novo**: Adicionado "Config/Update Leitor CAN" na seção Configuração e Atualização
  - Ferramenta para atualização de firmware e configuração de leitores CANBUS
  - Suporta comandos VERSIONS, LIMITS e atualização via arquivos .frm
  - Detecção automática de dispositivos dormentes com retry inteligente
  - Monitoramento FR1 para habilitação/desabilitação automática de botões
  - Interface com feedback visual por cores (verde=ativo, vermelho=inativo)

### v1.6 - 02Out2025
- Lançamento inicial do dashboard Electron
- Migração da interface web para aplicação desktop
- Suporte completo para todas as ferramentas SETERA existentes
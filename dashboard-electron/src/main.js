const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const express = require('express');
const { spawn, exec, execFile } = require('child_process');
const fs = require('fs');

// Centralized executable launcher with automatic elevation detection
const launchExecutable = (exePath, res) => {
  // Check if file exists
  if (!fs.existsSync(exePath)) {
    return res.json({
      success: false,
      error: `Arquivo não encontrado: ${exePath}`
    });
  }

  // List of keywords that typically indicate admin/elevation is required
  const elevationKeywords = [
    'update', 'install', 'setup', 'config', 'admin',
    'fw', 'firmware', 'driver', 'uninstall'
  ];

  // Check if executable name suggests it needs elevation
  const fileName = path.basename(exePath).toLowerCase();
  const needsElevation = elevationKeywords.some(keyword => fileName.includes(keyword));

  if (needsElevation) {
    console.log(`Launching with potential elevation: ${fileName}`);
  }

  try {
    // For paths with spaces, we need to use shell: true with proper quoting
    // Use spawn with detached to not wait for process to complete
    const child = spawn(`"${exePath}"`, [], {
      cwd: path.dirname(exePath),
      detached: true,
      stdio: 'ignore',
      shell: true  // Important for handling paths with spaces on Windows
    });

    // Track if we've sent a response
    let responseSent = false;

    child.on('error', (error) => {
      if (!responseSent) {
        responseSent = true;
        console.error(`Failed to launch ${fileName}:`, error);
        res.json({
          success: false,
          error: `Erro ao iniciar aplicação: ${error.message}`
        });
      }
    });

    // Unref the child process so our app doesn't wait for it
    child.unref();

    // Send success response after a very short delay to catch immediate errors
    // But don't wait for the application to actually open or close
    setTimeout(() => {
      if (!responseSent) {
        responseSent = true;
        res.json({
          success: true,
          message: needsElevation
            ? 'Aplicação com privilégios administrativos iniciada com sucesso'
            : 'Aplicação iniciada com sucesso'
        });
      }
    }, 200); // 200ms is enough to catch immediate launch errors

  } catch (error) {
    console.error(`Exception launching ${fileName}:`, error);
    res.json({
      success: false,
      error: `Erro ao iniciar aplicação: ${error.message}`
    });
  }
};

let mainWindow;
let server;
const PORT = 3000;

// Server setup
const expressApp = express();

// Middleware
expressApp.use(express.json());
expressApp.use(express.static(path.join(__dirname, 'renderer')));

// Tool markers to identify the correct setera-tools directory
const TOOL_MARKERS = ['busca_placa', 'config_str1010', 'update-fw-str1010'];

// Climb upward from a directory until we find one containing all tool markers
const locateToolsRoot = (startDir) => {
  if (!startDir) return null;

  let dir = path.resolve(startDir);
  const visited = new Set();

  while (!visited.has(dir)) {
    visited.add(dir);

    // Check if this directory contains all the tool markers
    const looksRight = TOOL_MARKERS.every(marker =>
      fs.existsSync(path.join(dir, marker))
    );

    if (looksRight) {
      console.log(`✓ Found tools root: ${dir}`);
      return dir;
    }

    // Move to parent directory
    const parent = path.dirname(dir);
    if (parent === dir) break; // Reached filesystem root
    dir = parent;
  }

  return null;
};

// Get the parent directory (where the tools are located)
const getToolsPath = () => {
  console.log('=== SETERA PATH RESOLUTION ===');
  console.log(`process.execPath: ${process.execPath}`);
  console.log(`process.cwd(): ${process.cwd()}`);
  console.log(`__dirname: ${__dirname}`);
  console.log(`process.env.PORTABLE_EXECUTABLE_DIR: ${process.env.PORTABLE_EXECUTABLE_DIR}`);

  // 1) Development mode - use known relative path
  const isDev = process.argv.includes('--dev');
  if (isDev) {
    const devPath = path.resolve(__dirname, '../..');
    console.log(`✓ Development mode: ${devPath}`);
    return devPath;
  }

  // 2) Portable build - climb from PORTABLE_EXECUTABLE_DIR
  if (process.env.PORTABLE_EXECUTABLE_DIR) {
    const fromPortable = locateToolsRoot(process.env.PORTABLE_EXECUTABLE_DIR);
    if (fromPortable) {
      console.log(`✓ Using tools from portable dir: ${fromPortable}`);
      return fromPortable;
    }
  }

  // 3) Try around the running binary location
  const fromExec = locateToolsRoot(path.dirname(process.execPath));
  if (fromExec) {
    console.log(`✓ Using tools from exec path: ${fromExec}`);
    return fromExec;
  }

  // 4) Try the current working directory (CLI launches)
  const fromCwd = locateToolsRoot(process.cwd());
  if (fromCwd) {
    console.log(`✓ Using tools from cwd: ${fromCwd}`);
    return fromCwd;
  }

  // 5) Asar-relative fallback (inside packaged app)
  const asarFallback = locateToolsRoot(path.resolve(__dirname, '..', '..', '..'));
  if (asarFallback) {
    console.log(`✓ Using tools from asar fallback: ${asarFallback}`);
    return asarFallback;
  }

  // Ultimate fallback
  console.log('⚠️ Could not locate tools directory, using current working directory');
  console.log('=== END PATH RESOLUTION ===');
  return process.cwd();
};

const TOOLS_PATH = getToolsPath();

// Routes - converted from Flask
expressApp.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'renderer', 'dashboard.html'));
});

expressApp.get('/status', (req, res) => {
  res.json({ status: 'running', version: '1.4' });
});

expressApp.post('/launch-stm32', async (req, res) => {
  try {
    // Fixed path for STM32 Cube Programmer
    const stm32Path = 'C:\\Program Files\\STMicroelectronics\\STM32Cube\\STM32CubeProgrammer\\bin\\STM32CubeProgrammer.exe';

    // Special check for STM32 with custom error message
    if (!fs.existsSync(stm32Path)) {
      return res.json({
        success: false,
        error: 'STM32 Cube Programmer não encontrado. Por favor, verifique se está instalado em C:\\Program Files\\STMicroelectronics\\STM32Cube\\STM32CubeProgrammer\\'
      });
    }

    // Use centralized launcher
    launchExecutable(stm32Path, res);

  } catch (error) {
    res.json({ success: false, error: error.message });
  }
});

expressApp.post('/launch-url', async (req, res) => {
  try {
    const { url_path } = req.body;

    if (!url_path) {
      return res.json({ success: false, error: 'Caminho da URL não fornecido' });
    }

    // Build full path to the HTML file
    const fullPath = path.join(TOOLS_PATH, url_path);

    // Check if file exists
    if (!fs.existsSync(fullPath)) {
      return res.json({ success: false, error: `Arquivo não encontrado: ${url_path}` });
    }

    // Convert to file:// URL format
    const fileUrl = 'file://' + fullPath.replace(/\\/g, '/');

    // Open in default browser
    shell.openExternal(fileUrl);

    res.json({ success: true, message: 'URL aberta no navegador padrão' });

  } catch (error) {
    res.json({ success: false, error: error.message });
  }
});

expressApp.post('/launch', async (req, res) => {
  try {
    const { app_path } = req.body;

    if (!app_path) {
      return res.json({ success: false, error: 'Caminho da aplicação não fornecido' });
    }

    // Build full path
    const fullPath = path.join(TOOLS_PATH, app_path);

    // Check if file exists
    if (!fs.existsSync(fullPath)) {
      return res.json({ success: false, error: `Arquivo não encontrado: ${app_path}` });
    }

    // Launch based on file type
    if (fullPath.endsWith('.pyw')) {
      // Python GUI applications
      const result = spawn('pythonw.exe', [fullPath], {
        cwd: path.dirname(fullPath),
        detached: true,
        stdio: 'ignore'
      });

      result.unref();
      res.json({ success: true, message: 'Aplicação Python GUI iniciada com sucesso' });

    } else if (fullPath.endsWith('.py')) {
      // Special handling for Flask apps
      if (fullPath.includes('app.py')) {
        // For rpm_analysis Flask app
        const workingDir = path.dirname(fullPath);
        const flaskProcess = spawn('python.exe', [path.basename(fullPath)], {
          cwd: workingDir,
          detached: true,
          stdio: 'ignore'
        });

        flaskProcess.unref();

        // Wait longer for Flask server initialization and database connection
        // The RPM analysis app needs time to connect to PostgreSQL database
        setTimeout(() => {
          shell.openExternal('http://localhost:5004/loading');
        }, 5000);

        res.json({ success: true, message: 'Aplicação Flask iniciada com sucesso' });
      } else {
        // Regular Python scripts
        const result = spawn('python.exe', [fullPath], {
          cwd: path.dirname(fullPath),
          detached: true,
          stdio: 'ignore'
        });

        result.unref();
        res.json({ success: true, message: 'Script Python iniciado com sucesso' });
      }

    } else if (fullPath.endsWith('.exe')) {
      // Use centralized launcher for ALL executables
      launchExecutable(fullPath, res);

    } else {
      res.json({ success: false, error: 'Tipo de arquivo não suportado' });
    }

  } catch (error) {
    res.json({ success: false, error: error.message });
  }
});

// Start Express server
const startServer = () => {
  return new Promise((resolve, reject) => {
    server = expressApp.listen(PORT, 'localhost', (err) => {
      if (err) {
        reject(err);
      } else {
        console.log(`SETERA Dashboard server running on http://localhost:${PORT}`);
        resolve();
      }
    });
  });
};

// Create main window
const createWindow = () => {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    show: false, // Don't show until ready
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, '../assets/logo.ico'),
    title: 'SETERA Ferramentas v1.4 - 26Set2025',
    autoHideMenuBar: true
  });

  // Maximize window on startup
  mainWindow.maximize();

  // Load the dashboard
  mainWindow.loadURL(`http://localhost:${PORT}`);

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
    if (server) {
      server.close();
    }
  });
};

// App event handlers
app.whenReady().then(async () => {
  try {
    await startServer();
    createWindow();
  } catch (error) {
    console.error('Failed to start server:', error);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    if (server) {
      server.close();
    }
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// IPC handlers for renderer communication
ipcMain.handle('launch-app', async (event, appPath) => {
  // This will be used if we want to use IPC instead of HTTP
  // For now, keeping HTTP for minimal changes
  return { success: true, message: 'Use HTTP endpoint for now' };
});
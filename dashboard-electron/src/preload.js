const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // For future IPC communication if needed
  launchApp: (appPath) => ipcRenderer.invoke('launch-app', appPath),

  // Platform detection
  platform: process.platform,

  // Version info
  versions: {
    node: process.versions.node,
    chrome: process.versions.chrome,
    electron: process.versions.electron,
  }
});

// For debugging
console.log('Preload script loaded');
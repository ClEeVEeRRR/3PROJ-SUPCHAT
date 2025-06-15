const { app, BrowserWindow, Menu, ipcMain } = require('electron');
const fs = require('fs');
const path = require('path');

function getApiAddress() {
  const userDataPath = app.getPath('userData');
  const userApiAddressPath = path.join(userDataPath, 'api_address');
  const defaultApiAddressPath = path.join(__dirname, 'api_address');

  if (!fs.existsSync(userApiAddressPath)) {
    try {
      if (fs.existsSync(defaultApiAddressPath)) {
        fs.copyFileSync(defaultApiAddressPath, userApiAddressPath);
      } else {
        fs.writeFileSync(userApiAddressPath, 'http://127.0.0.1:8000');
      }
    } catch (err) {
      console.error('Error initializing api_address:', err);
    }
  }

  try {
    return fs.readFileSync(userApiAddressPath, 'utf-8').trim();
  } catch (err) {
    console.error('Error reading user api_address:', err);
    return '';
  }
}

ipcMain.handle('get-api-address', () => {
  return getApiAddress();
});

function createWindow () {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  // Hide the default menu bar
  win.setMenuBarVisibility(false);
  win.removeMenu();

  if (process.env.NODE_ENV === 'development') {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, 'dist/index.html'));
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
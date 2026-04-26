/**
 * CompanionOS 窗口管理器
 * 管理主窗口、VRM伴侣窗口的创建与生命周期
 */

const { BrowserWindow } = require('electron');
const path = require('path');

const isDev = !require('electron').app.isPackaged;

class WindowManager {
  constructor() {
    this.mainWindow = null;
    this.vrmWindow = null;
  }

  createMainWindow() {
    this.mainWindow = new BrowserWindow({
      width: 1400,
      height: 900,
      minWidth: 1024,
      minHeight: 700,
      frame: false,
      titleBarStyle: 'hiddenInset',
      backgroundColor: '#1a1a2e',
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
      },
    });

    const url = isDev
      ? 'http://localhost:5173'
      : `file://${path.join(__dirname, '../frontend/dist/index.html')}`;

    this.mainWindow.loadURL(url);

    // 关闭时隐藏而非退出（托盘模式）
    this.mainWindow.on('close', (e) => {
      e.preventDefault();
      this.mainWindow.hide();
    });

    return this.mainWindow;
  }

  createVRMWindow() {
    this.vrmWindow = new BrowserWindow({
      width: 320,
      height: 480,
      frame: false,
      transparent: true,
      alwaysOnTop: true,
      resizable: false,
      skipTaskbar: true,
      hasShadow: false,
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
      },
    });

    const url = isDev
      ? 'http://localhost:5173/vrm.html'
      : `file://${path.join(__dirname, '../frontend/dist/vrm.html')}`;

    this.vrmWindow.loadURL(url);
    this.vrmWindow.setVisibleOnAllWorkspaces(true);

    return this.vrmWindow;
  }

  getMainWindow() {
    return this.mainWindow;
  }

  getVRMWindow() {
    return this.vrmWindow;
  }

  showMainWindow() {
    if (this.mainWindow) {
      this.mainWindow.show();
      this.mainWindow.focus();
    }
  }

  hideMainWindow() {
    this.mainWindow?.hide();
  }

  showVRMWindow() {
    this.vrmWindow?.show();
  }

  hideVRMWindow() {
    this.vrmWindow?.hide();
  }

  toggleVRM(show) {
    if (show) this.showVRMWindow();
    else this.hideVRMWindow();
  }

  sendToVRM(channel, data) {
    this.vrmWindow?.webContents.send(channel, data);
  }

  sendToMain(channel, data) {
    this.mainWindow?.webContents.send(channel, data);
  }

  destroyAll() {
    if (this.vrmWindow && !this.vrmWindow.isDestroyed()) {
      this.vrmWindow.removeAllListeners();
      this.vrmWindow.destroy();
    }
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.removeAllListeners();
      this.mainWindow.destroy();
    }
    this.mainWindow = null;
    this.vrmWindow = null;
  }
}

module.exports = WindowManager;

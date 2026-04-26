/**
 * CompanionOS - Electron 主进程入口
 * 虚拟伴侣AI办公一体桌面端应用
 */

const { app, ipcMain, dialog } = require('electron');
const WindowManager = require('./window-manager');
const ProcessManager = require('./process-manager');
const TrayManager = require('./tray');

// ==================== 自动更新模块 ====================

let updater = null;
try {
  updater = require('./updater');
} catch (error) {
  console.warn('[CompanionOS] 自动更新模块加载失败:', error.message);
}

// ==================== 全局异常处理 ====================

process.on('uncaughtException', (error) => {
  console.error('[CompanionOS] 未捕获的异常:', error.message, error.stack);
  try {
    dialog.showErrorBox('CompanionOS 错误', `发生未预期的错误:\n${error.message}\n\n${error.stack}`);
  } catch {
    // 对话框可能不可用
  }
});

process.on('unhandledRejection', (reason) => {
  console.error('[CompanionOS] 未处理的 Promise 拒绝:', reason);
  if (reason instanceof Error) {
    console.error('[CompanionOS] 拒绝堆栈:', reason.stack);
  }
});

process.on('warning', (warning) => {
  console.warn('[CompanionOS] 进程警告:', warning.name, warning.message, warning.stack);
});

// ==================== 初始化管理器 ====================

const windowManager = new WindowManager();
const processManager = new ProcessManager();
const trayManager = new TrayManager(windowManager, processManager);

// ==================== IPC 通信注册 ====================

function registerIPC() {
  // 窗口控制
  ipcMain.handle('window:minimize', () => windowManager.getMainWindow()?.minimize());
  ipcMain.handle('window:maximize', () => {
    const win = windowManager.getMainWindow();
    if (win?.isMaximized()) win.unmaximize();
    else win?.maximize();
  });
  ipcMain.handle('window:close', () => windowManager.hideMainWindow());

  // VRM伴侣控制
  ipcMain.handle('vrm:toggle', (_, show) => windowManager.toggleVRM(show));
  ipcMain.handle('companion:action', (_, action) => {
    windowManager.sendToVRM('companion-action', action);
  });

  // 系统信息
  ipcMain.handle('system:info', () => ({
    platform: process.platform,
    version: app.getVersion(),
    electronVersion: process.versions.electron,
    nodeVersion: process.versions.node,
  }));

  // 进程管理
  ipcMain.handle('process:status', () => ({
    running: processManager.getRunningProcesses(),
    backend: processManager.isRunning('backend'),
  }));

  ipcMain.handle('process:restart-backend', () => {
    processManager.stopProcess('backend');
    processManager.startBackend();
    return { status: 'restarting' };
  });

  // 自动更新
  if (updater) {
    ipcMain.handle('update:check', () => updater.checkForUpdates());
    ipcMain.handle('update:download', () => updater.downloadUpdate());
    ipcMain.handle('update:install', () => updater.quitAndInstall());
  }
}

// ==================== 应用生命周期 ====================

app.whenReady().then(async () => {
  try {
    console.log('[CompanionOS] 应用启动中...');

    // 1. 注册IPC通信
    registerIPC();

    // 2. 启动后端服务
    processManager.startBackend();

    // 3. 等待后端就绪
    await processManager.waitForBackend();

    // 4. 创建窗口
    windowManager.createMainWindow();
    windowManager.createVRMWindow();

    // 5. 创建系统托盘
    trayManager.create();

    // 6. 自动启动设置
    try {
      app.setLoginItemSettings({
        openAtLogin: true,
        path: app.getPath('exe'),
      });
      console.log('[CompanionOS] 自动启动已启用');
    } catch (error) {
      console.warn('[CompanionOS] 自动启动设置失败:', error.message);
    }

    // 7. 窗口关闭时隐藏到托盘
    const mainWindow = windowManager.getMainWindow();
    if (mainWindow) {
      mainWindow.on('close', (event) => {
        if (!app.isQuitting) {
          event.preventDefault();
          mainWindow.hide();
        }
      });
    }

    // 8. 初始化自动更新
    if (updater) {
      try {
        updater.initUpdater();
      } catch (error) {
        console.warn('[CompanionOS] 自动更新初始化失败:', error.message);
      }
    }

    console.log('[CompanionOS] 应用启动完成');
  } catch (error) {
    console.error('[CompanionOS] 启动失败:', error.message, error.stack);
    dialog.showErrorBox('CompanionOS 启动失败', `应用启动过程中发生错误:\n${error.message}\n\n请检查后端服务是否正常。`);
  }
});

app.on('window-all-closed', () => {
  // 保持托盘运行
});

app.on('before-quit', () => {
  app.isQuitting = true;
  try {
    processManager.stopAll();
    windowManager.destroyAll();
    trayManager.destroy();
  } catch (error) {
    console.error('[CompanionOS] 退出清理失败:', error.message);
  }
});

app.on('activate', () => {
  windowManager.showMainWindow();
});

// ==================== 单实例锁 ====================

const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    windowManager.showMainWindow();
  });
}

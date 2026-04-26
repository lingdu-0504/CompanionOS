/**
 * CompanionOS - 自动更新模块
 * 基于 electron-updater 实现自动检查、下载和安装更新
 */

const { autoUpdater } = require('electron-updater');
const { BrowserWindow } = require('electron');

// ==================== 日志配置 ====================

autoUpdater.logger = console;
autoUpdater.logger.info = (...args) => console.log('[CompanionOS Updater]', ...args);
autoUpdater.logger.warn = (...args) => console.warn('[CompanionOS Updater]', ...args);
autoUpdater.logger.error = (...args) => console.error('[CompanionOS Updater]', ...args);

// ==================== 更新状态管理 ====================

let updateCheckInProgress = false;

// ==================== IPC 事件发送 ====================

function sendStatusToWindows(channel, data) {
  const windows = BrowserWindow.getAllWindows();
  windows.forEach(win => {
    try {
      win.webContents.send(channel, data);
    } catch (err) {
      console.error('[CompanionOS Updater] 发送状态失败:', err.message);
    }
  });
}

// ==================== 自动更新事件处理 ====================

autoUpdater.on('checking-for-update', () => {
  console.log('[CompanionOS Updater] 正在检查更新...');
  sendStatusToWindows('update:checking', { status: 'checking' });
});

autoUpdater.on('update-available', (info) => {
  console.log('[CompanionOS Updater] 发现新版本:', info.version);
  sendStatusToWindows('update:available', {
    status: 'available',
    version: info.version,
    releaseDate: info.releaseDate,
    releaseNotes: info.releaseNotes,
  });
});

autoUpdater.on('update-not-available', (info) => {
  console.log('[CompanionOS Updater] 当前已是最新版本');
  sendStatusToWindows('update:not-available', {
    status: 'not-available',
    version: info?.version,
  });
  updateCheckInProgress = false;
});

autoUpdater.on('download-progress', (progressObj) => {
  const { percent, bytesPerSecond, transferred, total } = progressObj;
  console.log(`[CompanionOS Updater] 下载进度: ${percent.toFixed(1)}%`);
  sendStatusToWindows('update:download-progress', {
    status: 'downloading',
    percent: Math.round(percent * 10) / 10,
    bytesPerSecond,
    transferred,
    total,
  });
});

autoUpdater.on('update-downloaded', (info) => {
  console.log('[CompanionOS Updater] 更新下载完成:', info.version);
  sendStatusToWindows('update:downloaded', {
    status: 'downloaded',
    version: info.version,
    releaseDate: info.releaseDate,
  });
  updateCheckInProgress = false;
});

autoUpdater.on('error', (error) => {
  console.error('[CompanionOS Updater] 更新出错:', error.message, error.stack);
  sendStatusToWindows('update:error', {
    status: 'error',
    message: error.message,
  });
  updateCheckInProgress = false;
});

// ==================== 公开 API ====================

function initUpdater() {
  try {
    autoUpdater.autoDownload = false;
    autoUpdater.autoInstallOnAppQuit = true;
    console.log('[CompanionOS Updater] 模块初始化完成');
  } catch (error) {
    console.error('[CompanionOS Updater] 初始化失败:', error.message);
  }
}

async function checkForUpdates() {
  if (updateCheckInProgress) {
    console.log('[CompanionOS Updater] 更新检查正在进行中，跳过');
    return { status: 'in-progress' };
  }

  try {
    updateCheckInProgress = true;
    const result = await autoUpdater.checkForUpdates();
    return result;
  } catch (error) {
    console.error('[CompanionOS Updater] 检查更新失败:', error.message);
    updateCheckInProgress = false;
    return { status: 'error', message: error.message };
  }
}

function downloadUpdate() {
  try {
    autoUpdater.downloadUpdate();
    return { status: 'downloading' };
  } catch (error) {
    console.error('[CompanionOS Updater] 下载更新失败:', error.message);
    return { status: 'error', message: error.message };
  }
}

function quitAndInstall() {
  try {
    autoUpdater.quitAndInstall();
  } catch (error) {
    console.error('[CompanionOS Updater] 安装更新失败:', error.message);
  }
}

module.exports = {
  initUpdater,
  checkForUpdates,
  downloadUpdate,
  quitAndInstall,
};

/**
 * CompanionOS 系统托盘
 * 提供快捷操作入口和状态显示
 */

const { Tray, Menu, nativeImage, app } = require('electron');
const path = require('path');

class TrayManager {
  constructor(windowManager, processManager) {
    this.tray = null;
    this.windowManager = windowManager;
    this.processManager = processManager;
  }

  create() {
    const iconPath = path.join(__dirname, 'assets', 'icon.png');
    let icon;
    try {
      icon = nativeImage.createFromPath(iconPath);
      if (icon.isEmpty()) {
        icon = nativeImage.createEmpty();
      }
    } catch {
      icon = nativeImage.createEmpty();
    }

    this.tray = new Tray(icon);

    const contextMenu = Menu.buildFromTemplate([
      {
        label: '显示主窗口',
        click: () => this.windowManager.showMainWindow(),
      },
      {
        label: '显示伴侣',
        click: () => this.windowManager.showVRMWindow(),
      },
      {
        label: '隐藏窗口',
        click: () => this.windowManager.hideMainWindow(),
      },
      { type: 'separator' },
      {
        label: '快速指令',
        submenu: [
          {
            label: '总结今日邮件',
            click: () => this.windowManager.sendToMain('quick-command', 'summarize_emails'),
          },
          {
            label: '生成周报',
            click: () => this.windowManager.sendToMain('quick-command', 'generate_report'),
          },
          {
            label: '开始对话',
            click: () => {
              this.windowManager.showMainWindow();
              this.windowManager.sendToMain('quick-command', 'start_chat');
            },
          },
        ],
      },
      { type: 'separator' },
      {
        label: '设置',
        click: () => {
          this.windowManager.showMainWindow();
          this.windowManager.sendToMain('navigate', 'settings');
        },
      },
      { type: 'separator' },
      { label: 'CompanionOS 运行中', enabled: false },
      {
        label: '运行状态',
        type: 'submenu',
        submenu: [
          { label: '后端服务: 运行中', type: 'normal', enabled: false },
          { label: 'MCP网关: 待实现', type: 'normal', enabled: false },
          { label: 'A2A网关: 待实现', type: 'normal', enabled: false },
        ],
      },
      { type: 'separator' },
      {
        label: '重启后端',
        click: () => {
          this.processManager.stopProcess('backend');
          this.processManager.startBackend();
        },
      },
      { type: 'separator' },
      {
        label: '退出 CompanionOS',
        click: () => {
          app.isQuitting = true;
          this.processManager.stopAll();
          app.quit();
        },
      },
    ]);

    this.tray.setToolTip('CompanionOS - AI伴侣办公助手');
    this.tray.setContextMenu(contextMenu);

    this.tray.on('double-click', () => {
      this.windowManager.showMainWindow();
    });

    return this.tray;
  }

  /**
   * 更新托盘菜单中的状态显示
   */
  updateStatus(status) {
    if (!this.tray) return;

    const statusLabel = status?.status === 'running' ? '运行中' : '未连接';
    this.tray.setToolTip(`CompanionOS - ${statusLabel}`);
  }

  destroy() {
    if (this.tray) {
      this.tray.destroy();
      this.tray = null;
    }
  }
}

module.exports = TrayManager;

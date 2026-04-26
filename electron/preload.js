/**
 * CompanionOS Preload脚本
 * 安全桥接主进程和渲染进程
 */

const { contextBridge, ipcRenderer } = require('electron');

const API_BASE = 'http://localhost:18080';

// ==================== HTTP API封装 ====================

async function apiFetch(path, options = {}) {
  try {
    const resp = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    return await resp.json();
  } catch (err) {
    return { error: err.message, status: 'network_error' };
  }
}

contextBridge.exposeInMainWorld('companionOS', {
  // ==================== 窗口控制 ====================
  minimize: () => ipcRenderer.invoke('window:minimize'),
  maximize: () => ipcRenderer.invoke('window:maximize'),
  close: () => ipcRenderer.invoke('window:close'),

  // ==================== VRM伴侣控制 ====================
  toggleVRM: (show) => ipcRenderer.invoke('vrm:toggle', show),
  sendAction: (action) => ipcRenderer.invoke('companion:action', action),

  // ==================== 快捷指令监听 ====================
  onQuickCommand: (callback) => ipcRenderer.on('quick-command', (_, cmd) => callback(cmd)),

  // ==================== 系统信息 ====================
  getSystemInfo: () => ipcRenderer.invoke('system:info'),
  getProcessStatus: () => ipcRenderer.invoke('process:status'),
  restartBackend: () => ipcRenderer.invoke('process:restart-backend'),

  // ==================== 核心API ====================
  api: {
    // 系统状态
    getStatus: () => apiFetch('/api/status'),

    // 对话
    chat: (message, sessionId, context) => apiFetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId, context }),
    }),

    // 工作流
    getWorkflows: () => apiFetch('/api/workflow'),
    createWorkflow: (data) => apiFetch('/api/workflow', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
    executeWorkflow: (id, inputs) => apiFetch(`/api/workflow/${id}/execute`, {
      method: 'POST',
      body: JSON.stringify({ inputs }),
    }),
    getNodeTypes: () => apiFetch('/api/workflow/node-types'),

    // 记忆
    listMemoryBlocks: () => apiFetch('/api/memory'),
    getMemory: (type) => apiFetch(`/api/memory/${type}`),
    updateMemory: (type, label, value) => apiFetch(`/api/memory/${type}`, {
      method: 'PUT',
      body: JSON.stringify({ label, value }),
    }),

    // 伴侣
    getCompanionState: () => apiFetch('/api/companion/state'),
    companionInteract: (type, delta) => apiFetch(`/api/companion/interact?interaction_type=${type}&delta=${delta}`, {
      method: 'POST',
    }),
    getRelationLevels: () => apiFetch('/api/companion/relation-levels'),

    // 语音
    textToSpeech: (text, engine) => apiFetch(`/api/voice/tts?text=${encodeURIComponent(text)}&engine=${engine || ''}`, {
      method: 'POST',
    }),
    listVoiceEngines: () => apiFetch('/api/voice/engines'),

    // MCP工具
    listMCPTools: () => apiFetch('/api/mcp/tools'),
    callMCPTool: (name, args) => apiFetch(`/api/mcp/call?tool_name=${name}`, {
      method: 'POST',
      body: JSON.stringify(args || {}),
    }),

    // A2A Agent
    listAgents: () => apiFetch('/api/a2a/agents'),
    delegateTask: (from, to, task) => apiFetch(`/api/a2a/delegate?from_agent=${from}&to_agent=${to}`, {
      method: 'POST',
      body: JSON.stringify(task),
    }),

    // 安全
    listKeys: () => apiFetch('/api/security/keys'),
    approveOperation: (id) => apiFetch(`/api/security/approve/${id}`, { method: 'POST' }),
    rejectOperation: (id) => apiFetch(`/api/security/reject/${id}`, { method: 'POST' }),
  },

  // ==================== 自动更新 ====================
  onUpdateStatus: (callback) => {
    ipcRenderer.on('update:checking', (_, data) => callback(data));
    ipcRenderer.on('update:available', (_, data) => callback(data));
    ipcRenderer.on('update:not-available', (_, data) => callback(data));
    ipcRenderer.on('update:download-progress', (_, data) => callback(data));
    ipcRenderer.on('update:downloaded', (_, data) => callback(data));
    ipcRenderer.on('update:error', (_, data) => callback(data));
  },
  checkUpdate: () => ipcRenderer.invoke('update:check'),
  downloadUpdate: () => ipcRenderer.invoke('update:download'),
  installUpdate: () => ipcRenderer.invoke('update:install'),

  // ==================== WebSocket ====================
  connectWS: () => {
    const ws = new WebSocket('ws://localhost:18080/ws');
    return ws;
  },
});

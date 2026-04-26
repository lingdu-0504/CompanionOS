import { create } from 'zustand';
import type { ChatMessage, CompanionState, SystemStatus } from '../types';

// ==================== 应用状态Store ====================

import { API_BASE } from '../config';

interface AppStore {
  // 当前视图模式
  currentView: 'home' | 'chat' | 'flow' | 'task' | 'settings';
  setCurrentView: (view: AppStore['currentView']) => void;

  // 伴侣状态
  companion: CompanionState;
  setCompanion: (state: CompanionState) => void;

  // 聊天消息
  messages: ChatMessage[];
  addMessage: (msg: ChatMessage) => void;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  clearMessages: () => void;

  // 系统状态
  systemStatus: SystemStatus | null;
  setSystemStatus: (status: SystemStatus) => void;

  // VRM伴侣显示
  vrmVisible: boolean;
  toggleVRM: () => void;

  // 加载状态
  loading: boolean;
  setLoading: (loading: boolean) => void;

  // 伴侣形象模式
  avatarMode: 'vrm' | 'live2d';
  setAvatarMode: (mode: 'vrm' | 'live2d') => void;

  // WebSocket 连接状态
  wsConnected: boolean;
  setWsConnected: (connected: boolean) => void;
  wsConnect: () => void;
  wsSend: (data: any) => void;
}

let wsInstance: WebSocket | null = null;
let wsRetryCount = 0;

export const useAppStore = create<AppStore>((set, get) => ({
  currentView: 'home',
  setCurrentView: (view) => set({ currentView: view }),

  companion: {
    name: '小暖',
    relation_level: 1,
    relation_name: '陌生人',
    affection: 0,
    trust: 0,
    intimacy: 0,
    comfort: 0,
    respect: 0,
    current_emotion: 'neutral',
  },
  setCompanion: (state) => set({ companion: state }),

  messages: [],
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  updateMessage: (id, updates) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, ...updates } : m)),
    })),
  clearMessages: () => set({ messages: [] }),

  systemStatus: null,
  setSystemStatus: (status) => set({ systemStatus: status }),

  vrmVisible: true,
  toggleVRM: () => set((s) => ({ vrmVisible: !s.vrmVisible })),

  loading: false,
  setLoading: (loading) => set({ loading }),

  avatarMode: 'vrm',
  setAvatarMode: (mode) => set({ avatarMode: mode }),

  wsConnected: false,
  setWsConnected: (connected) => set({ wsConnected: connected }),

  wsConnect: () => {
    if (wsInstance?.readyState === WebSocket.OPEN) return;

    const wsUrl = 'ws://localhost:18080/ws';
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      set({ wsConnected: true });
      wsRetryCount = 0;
    };

    ws.onclose = () => {
      set({ wsConnected: false });
      const delay = Math.min(1000 * Math.pow(2, wsRetryCount), 30000);
      wsRetryCount++;
      setTimeout(() => {
        if (!get().wsConnected) get().wsConnect();
      }, delay);
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case 'chat_response': {
            // Real-time chat response from another client/session
            const chatData = data.data;
            if (chatData?.emotion) {
              const companion = get().companion;
              set({ companion: { ...companion, current_emotion: chatData.emotion } });
            }
            break;
          }
          case 'stream_token': {
            // WebSocket streaming token
            const store = get();
            const lastMsg = store.messages[store.messages.length - 1];
            if (lastMsg?.role === 'assistant' && data.session_id) {
              store.updateMessage(lastMsg.id, {
                content: (lastMsg.content || '') + (data.content || ''),
              });
            }
            break;
          }
          case 'stream_done': {
            // Stream completed
            break;
          }
          case 'companion_state': {
            if (data.state) {
              set({ companion: data.state });
            }
            break;
          }
          case 'task_update': {
            // Task status update - could trigger TaskView refresh
            break;
          }
          case 'workflow_update': {
            // Workflow execution update
            break;
          }
          case 'pong':
            break;
          default:
            break;
        }
      } catch {
        // Not JSON, ignore
      }
    };

    wsInstance = ws;
  },

  wsSend: (data) => {
    if (wsInstance?.readyState === WebSocket.OPEN) {
      wsInstance.send(JSON.stringify(data));
    }
  },
}));

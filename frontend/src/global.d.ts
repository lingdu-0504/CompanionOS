interface Window {
  companionOS?: {
    // 窗口控制
    minimize: () => Promise<void>;
    maximize: () => Promise<void>;
    close: () => Promise<void>;

    // VRM伴侣控制
    toggleVRM: (show: boolean) => Promise<void>;
    sendAction: (action: string) => Promise<void>;

    // 快捷指令监听
    onQuickCommand: (callback: (cmd: string) => void) => void;

    // 系统信息
    getSystemInfo: () => Promise<{
      platform: string;
      version: string;
      electronVersion: string;
      nodeVersion: string;
    }>;
    getProcessStatus: () => Promise<{
      running: string[];
      backend: boolean;
    }>;
    restartBackend: () => Promise<{ status: string }>;

    // 核心API
    api: {
      // 系统状态
      getStatus: () => Promise<{
        status: string;
        services: Record<string, string>;
        companion: Record<string, unknown>;
        tools: Record<string, unknown>;
        timestamp: string;
      }>;

      // 对话
      chat: (message: string, sessionId?: string, context?: Record<string, unknown>) => Promise<{
        content: string;
        companion_remark?: string;
        intent: string;
        emotion?: string;
        vrm_action?: string;
        session_id: string;
      }>;

      // 工作流
      getWorkflows: () => Promise<{ workflows: Array<Record<string, unknown>> }>;
      createWorkflow: (data: Record<string, unknown>) => Promise<{ id: string; workflow?: { id: string } }>;
      executeWorkflow: (id: string, inputs: Record<string, unknown>) => Promise<Record<string, unknown>>;
      getNodeTypes: () => Promise<{ node_types: Array<Record<string, unknown>> }>;

      // 记忆
      listMemoryBlocks: () => Promise<{ blocks: Array<Record<string, unknown>> }>;
      getMemory: (type: string) => Promise<Record<string, unknown>>;
      updateMemory: (type: string, label: string, value: string) => Promise<Record<string, unknown>>;

      // 伴侣
      getCompanionState: () => Promise<Record<string, unknown>>;
      companionInteract: (type: string, delta?: number) => Promise<Record<string, unknown>>;
      getRelationLevels: () => Promise<{ levels: Array<Record<string, unknown>> }>;

      // 语音
      textToSpeech: (text: string, engine?: string) => Promise<Record<string, unknown>>;
      listVoiceEngines: () => Promise<{ engines: Array<Record<string, unknown>> }>;

      // MCP工具
      listMCPTools: () => Promise<{ tools: Array<Record<string, unknown>> }>;
      callMCPTool: (name: string, args?: Record<string, unknown>) => Promise<Record<string, unknown>>;

      // A2A Agent
      listAgents: () => Promise<{ agents: Array<Record<string, unknown>> }>;
      delegateTask: (from: string, to: string, task: Record<string, unknown>) => Promise<Record<string, unknown>>;

      // 安全
      listKeys: () => Promise<{ keys: Array<string> }>;
      approveOperation: (id: string) => Promise<{ success: boolean }>;
      rejectOperation: (id: string) => Promise<{ success: boolean }>;
    };

    // WebSocket
    connectWS: () => WebSocket;
  };
}

// 伴侣状态
export interface CompanionState {
  name: string;
  relation_level: number;
  relation_name: string;
  affection: number;
  trust: number;
  intimacy: number;
  comfort: number;
  respect: number;
  current_emotion: string;
  companion_remark?: string;
}

// 聊天消息
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  companion_remark?: string;
  intent?: string;
  emotion?: string;
  vrm_action?: string;
  timestamp: number;
}

// 工作流节点
export interface WorkflowNode {
  id: string;
  type: string;
  label: string;
  config: Record<string, unknown>;
  position: { x: number; y: number };
}

// 工作流边
export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
}

// 工作流
export interface Workflow {
  id: string;
  name: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  created_at: string;
}

// 记忆块
export interface MemoryBlock {
  label: string;
  value: string;
  updated_at?: string;
}

// 关系等级
export interface RelationLevel {
  level: number;
  name: string;
  threshold: number;
  icon: string;
}

// MCP工具
export interface MCPTool {
  name: string;
  group: string;
  description: string;
}

// A2A Agent
export interface A2AAgent {
  id: string;
  name: string;
  capabilities: string[];
  status: string;
}

// 系统状态
export interface SystemStatus {
  status: string;
  services: {
    hermes: string;
    'neuro-sama': string;
    letta: string;
    daemon: string;
  };
  companion: CompanionState;
  tools: {
    mcp: number;
    a2a_agents: number;
    workflow_nodes: number;
  };
  timestamp: string;
}

// API响应类型
export interface ChatResponse {
  content: string;
  companion_remark?: string;
  intent: string;
  emotion?: string;
  vrm_action?: string;
  session_id: string;
}

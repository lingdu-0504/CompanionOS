import React, { useCallback, useEffect, useState } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { SaveOutlined, PlayCircleOutlined, PlusOutlined, SettingOutlined } from '@ant-design/icons';
import './FlowView.css';

import { API_BASE } from '../config';

// Node type definitions with colors and config options
const nodeTypeDefinitions = [
  { type: 'hermesLLM', label: '🧠 Hermes LLM', color: '#64ffda', configFields: ['model', 'temperature'] },
  { type: 'emotion', label: '❤️ 情感交互', color: '#c792ea', configFields: ['emotion_type'] },
  { type: 'browser', label: '🌐 浏览器操作', color: '#82aaff', configFields: ['url', 'action'] },
  { type: 'document', label: '📄 文档处理', color: '#ffd700', configFields: ['doc_type', 'action'] },
  { type: 'desktop', label: '🖱️ 桌面自动化', color: '#ff6b9d', configFields: ['action'] },
  { type: 'email', label: '📧 邮件处理', color: '#64ffda', configFields: ['folder', 'action'] },
  { type: 'tts', label: '🔊 语音合成', color: '#c792ea', configFields: ['voice', 'text'] },
  { type: 'condition', label: '🔀 条件分支', color: '#ffd700', configFields: ['condition'] },
  { type: 'cron', label: '⏰ 定时触发', color: '#82aaff', configFields: ['schedule'] },
  { type: 'memory', label: '📝 记忆读写', color: '#ff6b9d', configFields: ['block_type', 'action'] },
  { type: 'a2a', label: '🔗 A2A委派', color: '#c792ea', configFields: ['agent_type', 'task'] },
  { type: 'code', label: '⚡ 代码执行', color: '#82aaff', configFields: ['language', 'code'] },
];

// Custom node component
const CustomNode: React.FC<NodeProps> = ({ data, selected }) => {
  return (
    <div className={`custom-node ${selected ? 'selected' : ''}`} style={{ borderColor: data.color || '#64ffda' }}>
      <Handle type="target" position={Position.Top} />
      <div className="custom-node-label">{data.label}</div>
      {data.configured && <div className="custom-node-badge">✓</div>}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

const nodeTypes = { custom: CustomNode };

const initialNodes: Node[] = [
  { id: '1', type: 'custom', position: { x: 250, y: 50 }, data: { label: '⏰ 开始', color: '#82aaff' } },
  { id: '2', type: 'custom', position: { x: 250, y: 150 }, data: { label: '🧠 AI处理', color: '#64ffda' } },
  { id: '3', type: 'custom', position: { x: 250, y: 250 }, data: { label: '✅ 输出结果', color: '#ff6b9d' } },
];

const initialEdges: Edge[] = [
  { id: 'e1-2', source: '1', target: '2', animated: true },
  { id: 'e2-3', source: '2', target: '3' },
];

const FlowView: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [workflowName, setWorkflowName] = useState('未命名工作流');
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [nodeConfig, setNodeConfig] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [loadingWorkflows, setLoadingWorkflows] = useState(true);
  const [loadingWorkflowId, setLoadingWorkflowId] = useState<string | null>(null);
  const [executionResult, setExecutionResult] = useState<any>(null);
  const [savedWorkflows, setSavedWorkflows] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Load saved workflows
  useEffect(() => {
    const loadWorkflows = async () => {
      setLoadingWorkflows(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE}/api/workflow`);
        const data = await res.json();
        setSavedWorkflows(data.workflows || []);
      } catch {
        setError('无法加载工作流列表，后端服务可能不可用');
      } finally {
        setLoadingWorkflows(false);
      }
    };
    loadWorkflows();
  }, []);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
    setNodeConfig(node.data.config || {});
  }, []);

  const addNode = (type: string, label: string, color: string) => {
    const id = `node-${Date.now()}`;
    const newNode: Node = {
      id,
      type: 'custom',
      position: { x: Math.random() * 400 + 100, y: Math.random() * 300 + 100 },
      data: { label, color, nodeType: type, config: {} },
    };
    setNodes((nds) => [...nds, newNode]);
  };

  const updateNodeConfig = () => {
    if (!selectedNode) return;
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? { ...n, data: { ...n.data, config: nodeConfig, configured: true } }
          : n
      )
    );
    setSelectedNode(null);
  };

  const saveWorkflow = async () => {
    setSaving(true);
    setError(null);
    try {
      const workflowNodes = nodes.map((n) => ({
        id: n.id,
        type: n.data.nodeType || 'unknown',
        label: n.data.label,
        config: n.data.config || {},
        position: n.position,
      }));
      const workflowEdges = edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        source_handle: e.sourceHandle,
        target_handle: e.targetHandle,
      }));

      await fetch(`${API_BASE}/api/workflow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: workflowName,
          description: `工作流: ${workflowName}`,
          nodes: workflowNodes,
          edges: workflowEdges,
        }),
      });

      const res = await fetch(`${API_BASE}/api/workflow`);
      const data = await res.json();
      setSavedWorkflows(data.workflows || []);
    } catch {
      setError('保存工作流失败，请检查后端服务');
    } finally {
      setSaving(false);
    }
  };

  const loadWorkflow = async (wfId: string) => {
    setLoadingWorkflowId(wfId);
    setError(null);
    try {
      const wf = savedWorkflows.find((w) => w.id === wfId);
      if (wf) {
        const loadedNodes: Node[] = (wf.nodes || []).map((n: any) => ({
          id: n.id,
          type: 'custom',
          position: n.position || { x: 100, y: 100 },
          data: {
            label: n.label || n.type,
            color: n.color || '#64ffda',
            nodeType: n.type,
            config: n.config || {},
            configured: !!n.config && Object.keys(n.config).length > 0,
          },
        }));
        const loadedEdges: Edge[] = (wf.edges || []).map((e: any) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.source_handle,
          targetHandle: e.target_handle,
        }));
        setNodes(loadedNodes.length > 0 ? loadedNodes : initialNodes);
        setEdges(loadedEdges.length > 0 ? loadedEdges : initialEdges);
        setWorkflowName(wf.name);
      }
    } catch {
      setError('加载工作流失败');
    } finally {
      setLoadingWorkflowId(null);
    }
  };

  const executeWorkflow = async () => {
    setExecuting(true);
    setExecutionResult(null);
    setError(null);

    try {
      const workflowNodes = nodes.map((n) => ({
        id: n.id,
        type: n.data?.nodeType || n.type || 'custom',
        label: n.data?.label || '',
        color: n.data?.color || '#64ffda',
        config: n.data?.config || {},
        position: { x: n.position?.x || 0, y: n.position?.y || 0 },
      }));
      const workflowEdges = edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        source_handle: e.sourceHandle,
        target_handle: e.targetHandle,
      }));

      const saveRes = await fetch(`${API_BASE}/api/workflow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: workflowName,
          description: `工作流: ${workflowName}`,
          nodes: workflowNodes,
          edges: workflowEdges,
        }),
      });
      const savedWf = await saveRes.json();
      const wfId = savedWf.id || savedWf.workflow?.id;

      if (wfId) {
        const execRes = await fetch(`${API_BASE}/api/workflow/${wfId}/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ inputs: {} }),
        });
        const execData = await execRes.json();
        setExecutionResult(execData);
      }

      const listRes = await fetch(`${API_BASE}/api/workflow`);
      const listData = await listRes.json();
      setSavedWorkflows(listData.workflows || []);
    } catch (e) {
      setExecutionResult({ status: 'error', error: String(e) });
      setError('执行工作流失败');
    } finally {
      setExecuting(false);
    }
  };

  // Get config fields for selected node type
  const getConfigFields = () => {
    if (!selectedNode?.data?.nodeType) return [];
    const def = nodeTypeDefinitions.find((d) => d.type === selectedNode.data.nodeType);
    return def?.configFields || [];
  };

  return (
    <div className="flow-view">
      {/* Toolbar */}
      <div className="flow-toolbar">
        <input
          className="flow-name-input"
          value={workflowName}
          onChange={(e) => setWorkflowName(e.target.value)}
          placeholder="工作流名称"
        />
        <button className="flow-btn" onClick={saveWorkflow} disabled={saving || executing}>
          <SaveOutlined /> {saving ? '保存中...' : '保存'}
        </button>
        <button className="flow-btn primary" onClick={executeWorkflow} disabled={executing || saving}>
          <PlayCircleOutlined /> {executing ? '执行中...' : '执行'}
        </button>
        <select
          className="flow-load-select"
          value=""
          onChange={(e) => e.target.value && loadWorkflow(e.target.value)}
          disabled={!!loadingWorkflowId}
        >
          <option value="">{loadingWorkflows ? '加载中...' : '加载工作流...'}</option>
          {savedWorkflows.map((wf) => (
            <option key={wf.id} value={wf.id}>
              {loadingWorkflowId === wf.id ? '加载中...' : wf.name}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="flow-error-bar">
          <span className="flow-error-text">{error}</span>
          <button className="flow-error-close" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <div className="flow-body">
        {/* Left sidebar: node panel */}
        <div className="flow-sidebar">
          <h3>节点</h3>
          {nodeTypeDefinitions.map((nt) => (
            <div
              key={nt.type}
              className="flow-node-item"
              onClick={() => addNode(nt.type, nt.label, nt.color)}
            >
              <span className="fn-label">{nt.label}</span>
              <PlusOutlined className="fn-add" />
            </div>
          ))}
        </div>

        {/* Canvas */}
        <div className="flow-canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
            style={{ background: '#0a0a1a' }}
          >
            <Controls style={{ background: '#16213e', borderRadius: 8 }} />
            <Background color="rgba(100,255,218,0.05)" gap={20} />
          </ReactFlow>
        </div>

        {/* Right panel: node config */}
        {selectedNode && (
          <div className="flow-config-panel">
            <h3><SettingOutlined /> 节点配置</h3>
            <div className="config-node-name">{selectedNode.data.label}</div>
            {getConfigFields().map((field) => (
              <div key={field} className="config-field">
                <label>{field}</label>
                <input
                  className="config-input"
                  value={nodeConfig[field] || ''}
                  onChange={(e) => setNodeConfig((c) => ({ ...c, [field]: e.target.value }))}
                  placeholder={`输入 ${field}`}
                />
              </div>
            ))}
            <button className="config-save-btn" onClick={updateNodeConfig}>
              确认
            </button>
            <button className="config-cancel-btn" onClick={() => setSelectedNode(null)}>
              取消
            </button>
          </div>
        )}
      </div>

      {/* Execution result modal */}
      {executionResult && (
        <div className="flow-result-overlay" onClick={() => setExecutionResult(null)}>
          <div className="flow-result-modal" onClick={(e) => e.stopPropagation()}>
            <h3>执行结果</h3>
            <div className={`result-status ${executionResult.status}`}>
              {executionResult.status === 'completed' ? '✅ 完成' : '❌ 失败'}
            </div>
            {executionResult.duration_ms && (
              <div className="result-duration">耗时: {executionResult.duration_ms}ms</div>
            )}
            <pre className="result-detail">
              {JSON.stringify(executionResult.results || executionResult.error, null, 2)}
            </pre>
            <button onClick={() => setExecutionResult(null)}>关闭</button>
          </div>
        </div>
      )}
    </div>
  );
};

export default FlowView;

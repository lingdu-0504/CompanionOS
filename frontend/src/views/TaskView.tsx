import React, { useEffect, useState } from 'react';
import { CheckCircleOutlined, ClockCircleOutlined, SyncOutlined, ReloadOutlined } from '@ant-design/icons';
import './TaskView.css';

import { API_BASE } from '../config';

interface Task {
  id: string;
  name: string;
  type: string;
  status: 'completed' | 'running' | 'pending' | 'failed';
  created_at: string;
  result?: string;
  error?: string;
}

const statusMap = {
  completed: { icon: <CheckCircleOutlined />, text: '已完成', color: '#64ffda' },
  running: { icon: <SyncOutlined spin />, text: '执行中', color: '#82aaff' },
  pending: { icon: <ClockCircleOutlined />, text: '待执行', color: '#8892b0' },
  failed: { icon: <ClockCircleOutlined />, text: '失败', color: '#ff6b9d' },
};

const TaskView: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = async () => {
    setLoading(true);
    setError(null);
    try {
      const a2aRes = await fetch(`${API_BASE}/api/a2a/tasks`);
      const a2aJson = await a2aRes.json();

      const eigentRes = await fetch(`${API_BASE}/api/eigent/tasks`);
      const eigentJson = await eigentRes.json();

      const wfRes = await fetch(`${API_BASE}/api/workflow`);
      const wfJson = await wfRes.json();

      const allTasks: Task[] = [];

      if (a2aJson?.tasks) {
        for (const t of a2aJson.tasks) {
          allTasks.push({
            id: t.task_id || t.id,
            name: t.task_type || t.description || 'A2A任务',
            type: 'A2A',
            status: t.status || 'pending',
            created_at: t.created_at || '',
            result: t.result ? JSON.stringify(t.result).slice(0, 100) : undefined,
          });
        }
      }

      if (eigentJson?.tasks) {
        for (const t of eigentJson.tasks) {
          allTasks.push({
            id: t.task_id,
            name: `${t.agent_type} - ${t.action}`,
            type: 'Eigent',
            status: t.status || 'pending',
            created_at: t.created_at || '',
            result: t.result ? (typeof t.result === 'string' ? t.result.slice(0, 100) : '已执行') : undefined,
            error: t.error,
          });
        }
      }

      if (wfJson?.workflows) {
        for (const wf of wfJson.workflows) {
          allTasks.push({
            id: wf.id,
            name: wf.name,
            type: '工作流',
            status: 'completed' as const,
            created_at: wf.created_at || '',
          });
        }
      }

      if (allTasks.length === 0) {
        setTasks([
          { id: '1', name: '邮件总结', type: '工作流', status: 'completed', created_at: '10:30', result: '已处理5封邮件' },
          { id: '2', name: '周报生成', type: 'Cron', status: 'pending', created_at: '18:00' },
          { id: '3', name: '文档翻译', type: '手动', status: 'running', created_at: '14:20' },
        ]);
      } else {
        setTasks(allTasks);
      }
    } catch {
      setError('后端服务暂不可用，显示示例数据');
      setTasks([
        { id: '1', name: '邮件总结', type: '工作流', status: 'completed', created_at: '10:30', result: '已处理5封邮件' },
        { id: '2', name: '周报生成', type: 'Cron', status: 'pending', created_at: '18:00' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
    const timer = setInterval(fetchTasks, 15000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="task-view">
      <div className="task-header">
        <h2 className="task-title">任务管理</h2>
        <button className="task-refresh" onClick={fetchTasks} disabled={loading}>
          <ReloadOutlined spin={loading} /> {loading ? '加载中...' : '刷新'}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {loading ? (
        <div className="loading">加载中...</div>
      ) : (
        <div className="task-list">
          {tasks.map((task) => {
            const st = statusMap[task.status] || statusMap.pending;
            return (
              <div key={task.id} className="task-card">
                <div className="task-card-header">
                  <span className="task-name">{task.name}</span>
                  <span className="task-status" style={{ color: st.color }}>
                    {st.icon} {st.text}
                  </span>
                </div>
                <div className="task-card-meta">
                  <span className="task-type">{task.type}</span>
                  <span className="task-time">{task.created_at}</span>
                </div>
                {task.result && (
                  <div className="task-result">{task.result}</div>
                )}
                {task.error && (
                  <div className="task-error">{task.error}</div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="task-empty">
        <p>更多任务通过工作流和Cron调度自动产生</p>
      </div>
    </div>
  );
};

export default TaskView;

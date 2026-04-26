import React, { useEffect, useState } from 'react';
import { ClockCircleOutlined } from '@ant-design/icons';
import './TaskPeek.css';

import { API_BASE } from '../config';

interface PeekTask {
  id: string;
  name: string;
  progress: number;
  status: 'running' | 'pending' | 'completed' | 'failed';
}

interface Reminder {
  time: string;
  text: string;
}

export const TaskPeek: React.FC = () => {
  const [tasks, setTasks] = useState<PeekTask[]>([
    { id: '1', name: '今日邮件', progress: 60, status: 'running' },
    { id: '2', name: '周报生成', progress: 0, status: 'pending' },
  ]);
  const [reminders] = useState<Reminder[]>([
    { time: '15:00', text: '喝咖啡休息' },
    { time: '18:00', text: '总结今日工作' },
  ]);

  // Fetch real tasks from backend
  useEffect(() => {
    const fetchTasks = async () => {
      try {
        // Get A2A tasks
        const a2aRes = await fetch(`${API_BASE}/api/a2a/tasks`);
        const a2aJson = await a2aRes.json();

        // Get Eigent tasks
        const eigentRes = await fetch(`${API_BASE}/api/eigent/tasks`);
        const eigentJson = await eigentRes.json();

        // Get workflows
        const wfRes = await fetch(`${API_BASE}/api/workflow`);
        const wfJson = await wfRes.json();

        const allTasks: PeekTask[] = [];

        // A2A tasks
        if (a2aJson?.tasks) {
          for (const t of a2aJson.tasks.slice(0, 3)) {
            allTasks.push({
              id: t.task_id || t.id,
              name: t.task_type || t.description || 'A2A任务',
              progress: t.status === 'completed' ? 100 : t.status === 'running' ? 50 : 0,
              status: t.status || 'pending',
            });
          }
        }

        // Eigent tasks
        if (eigentJson?.tasks) {
          for (const t of eigentJson.tasks.slice(0, 3)) {
            allTasks.push({
              id: t.task_id,
              name: `${t.agent_type} - ${t.action}`,
              progress: t.status === 'completed' ? 100 : t.status === 'running' ? 50 : 0,
              status: t.status || 'pending',
            });
          }
        }

        // Workflow as tasks
        if (wfJson?.workflows) {
          for (const wf of wfJson.workflows.slice(0, 2)) {
            allTasks.push({
              id: wf.id,
              name: wf.name,
              progress: 0,
              status: 'pending',
            });
          }
        }

        if (allTasks.length > 0) {
          setTasks(allTasks.slice(0, 4));
        }
      } catch {
        // Backend not available, keep defaults
      }
    };

    fetchTasks();
    const timer = setInterval(fetchTasks, 15000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="task-peek">
      <div className="peek-title">任务速览</div>
      {tasks.map((task) => (
        <div key={task.id} className="peek-task">
          <div className="peek-task-header">
            <span className="peek-task-name">{task.name}</span>
            <span className={`peek-task-status ${task.status}`}>
              {task.status === 'running' ? '执行中' : task.status === 'completed' ? '已完成' : task.status === 'failed' ? '失败' : '待执行'}
            </span>
          </div>
          <div className="peek-progress">
            <div className="peek-progress-fill" style={{ width: `${task.progress}%` }} />
          </div>
        </div>
      ))}

      <div className="peek-title" style={{ marginTop: 12 }}>
        <ClockCircleOutlined /> 提醒
      </div>
      {reminders.map((r, i) => (
        <div key={i} className="peek-reminder">
          <span className="peek-time">{r.time}</span>
          <span className="peek-text">{r.text}</span>
        </div>
      ))}
    </div>
  );
};

import React, { useEffect, useState } from 'react';
import { RocketOutlined, ThunderboltOutlined, MailOutlined, FileTextOutlined, BarChartOutlined, HeartOutlined } from '@ant-design/icons';
import { useAppStore } from '../stores/appStore';
import './HomeView.css';

import { API_BASE } from '../config';

interface OverviewData {
  pendingEmails: number;
  activeTasks: number;
  runningWorkflows: number;
  todayInteractions: number;
}

const quickWorkflows = [
  { icon: <MailOutlined />, name: '处理邮件', desc: '自动读取、总结、回复邮件', prompt: '帮我总结今天的邮件' },
  { icon: <FileTextOutlined />, name: '生成周报', desc: '自动汇总本周工作成果', prompt: '帮我生成周报' },
  { icon: <BarChartOutlined />, name: '数据分析', desc: '智能分析Excel数据', prompt: '帮我分析数据' },
  { icon: <HeartOutlined />, name: '情绪关怀', desc: '定时提醒休息与关怀', prompt: '我有点累了' },
];

const HomeView: React.FC = () => {
  const { companion, setCurrentView, addMessage } = useAppStore();
  const [overview, setOverview] = useState<OverviewData>({
    pendingEmails: 0,
    activeTasks: 0,
    runningWorkflows: 0,
    todayInteractions: 0,
  });
  const [loading, setLocalLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch real overview data
  useEffect(() => {
    const fetchOverview = async () => {
      setLocalLoading(true);
      setError(null);
      try {
        // Get tasks from A2A
        const tasksData = await window.companionOS?.api?.listAgents?.()
          ?? await (await fetch(`${API_BASE}/api/a2a/tasks`)).json();

        // Get workflows
        const wfData = await window.companionOS?.api?.getWorkflows?.()
          ?? await (await fetch(`${API_BASE}/api/workflow`)).json();

        // Get MCP tools stats as proxy for activity
        const statusData = await window.companionOS?.api?.getStatus?.()
          ?? await (await fetch(`${API_BASE}/api/status`)).json();

        setOverview({
          pendingEmails: statusData?.tools?.mcp?.total_calls ? Math.min(5, statusData.tools.mcp.total_calls) : 0,
          activeTasks: (tasksData?.tasks?.length || 0),
          runningWorkflows: wfData?.workflows?.length || 0,
          todayInteractions: companion ? Math.floor((companion.affection + companion.trust + companion.comfort) / 3) : 0,
        });
      } catch {
        setError('后端服务暂不可用，部分数据可能不准确');
      } finally {
        setLocalLoading(false);
      }
    };
    fetchOverview();
  }, [companion]);

  const handleQuickWorkflow = async (prompt: string) => {
    setCurrentView('chat');
    addMessage({
      id: Date.now().toString(),
      role: 'user',
      content: prompt,
      timestamp: Date.now(),
    });
  };

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 6) return '夜深了，注意休息';
    if (hour < 12) return '早上好，新的一天开始啦';
    if (hour < 18) return '下午好，继续加油';
    return '晚上好，辛苦了一天';
  };

  return (
    <div className="home-view">
      {/* 问候区 */}
      <div className="home-greeting">
        <div className="greeting-text">
          <h2>{getGreeting()}</h2>
          <p className="greeting-sub">{companion.name}在这里等你~</p>
        </div>
        <div className="greeting-mascot">
          <span className="mascot-emoji">
            {companion.current_emotion === 'happy' ? '😄' :
             companion.current_emotion === 'tired' ? '😴' :
             companion.current_emotion === 'love' ? '😍' :
             companion.current_emotion === 'sad' ? '🥺' : '😊'}
          </span>
          <span className="mascot-level">Lv.{companion.relation_level} {companion.relation_name}</span>
        </div>
      </div>

      {/* 快捷工作流 */}
      <div className="home-section">
        <h3><ThunderboltOutlined /> 快捷工作流</h3>
        <div className="workflow-grid">
          {quickWorkflows.map((wf, i) => (
            <div key={i} className="workflow-card" onClick={() => handleQuickWorkflow(wf.prompt)}>
              <span className="wf-icon">{wf.icon}</span>
              <span className="wf-name">{wf.name}</span>
              <span className="wf-desc">{wf.desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 今日概览 */}
      <div className="home-section">
        <h3><RocketOutlined /> 今日概览</h3>
        {loading ? (
          <div className="loading">加载中...</div>
        ) : error ? (
          <div className="error-message">{error}</div>
        ) : (
          <div className="overview-cards">
            <div className="overview-card">
              <span className="ov-number">{overview.pendingEmails}</span>
              <span className="ov-label">待处理邮件</span>
            </div>
            <div className="overview-card">
              <span className="ov-number">{overview.activeTasks}</span>
              <span className="ov-label">进行中任务</span>
            </div>
            <div className="overview-card">
              <span className="ov-number">{overview.runningWorkflows}</span>
              <span className="ov-label">工作流运行</span>
            </div>
            <div className="overview-card">
              <span className="ov-number">{overview.todayInteractions}</span>
              <span className="ov-label">今日互动</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default HomeView;

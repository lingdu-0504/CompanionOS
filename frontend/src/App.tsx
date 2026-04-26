import React, { Suspense, lazy, useEffect } from 'react';
import { useAppStore } from './stores/appStore';
import Sidebar from './components/Sidebar';
import CompanionPanel from './components/CompanionPanel';
import { ErrorBoundary } from './components/ErrorBoundary';
import './App.css';

const HomeView = lazy(() => import('./views/HomeView'));
const ChatView = lazy(() => import('./views/ChatView'));
const FlowView = lazy(() => import('./views/FlowView'));
const TaskView = lazy(() => import('./views/TaskView'));
const SettingsView = lazy(() => import('./views/SettingsView'));

const viewMap = {
  home: HomeView,
  chat: ChatView,
  flow: FlowView,
  task: TaskView,
  settings: SettingsView,
};

const App: React.FC = () => {
  const { currentView, systemStatus, setSystemStatus, setCompanion, wsConnect, wsConnected } = useAppStore();

  // 初始化WebSocket连接
  useEffect(() => {
    wsConnect();
  }, [wsConnect]);

  // 轮询系统状态（WebSocket的补充）
  useEffect(() => {
    const poll = async () => {
      try {
        const data = await window.companionOS?.api?.getStatus() 
          ?? await (await fetch('http://localhost:18080/api/status')).json();
        setSystemStatus(data);
        if (data.companion) setCompanion(data.companion);
      } catch {
        // 后端未启动
      }
    };

    poll();
    const timer = setInterval(poll, 5000);
    return () => clearInterval(timer);
  }, [setSystemStatus, setCompanion]);

  const CurrentView = viewMap[currentView];

  return (
    <div className="app-container">
      {/* 标题栏 */}
      <div className="titlebar">
        <span className="titlebar-text">CompanionOS</span>
        <div className="titlebar-controls">
          <button className="tb-btn" onClick={() => window.companionOS?.minimize()}>─</button>
          <button className="tb-btn" onClick={() => window.companionOS?.maximize()}>□</button>
          <button className="tb-btn close" onClick={() => window.companionOS?.close()}>✕</button>
        </div>
      </div>

      {/* 主体三栏 */}
      <div className="app-body">
        <Sidebar />
        <div className="main-content">
          <ErrorBoundary>
            <Suspense fallback={<div className="view-loading">加载中...</div>}>
              <CurrentView />
            </Suspense>
          </ErrorBoundary>
        </div>
        <CompanionPanel />
      </div>

      {/* 状态栏 */}
      <div className="statusbar">
        {systemStatus ? (
          <>
            <span className={`sb-dot ${wsConnected ? 'green' : 'yellow'}`} /> WS
            <span className="sb-dot green" /> Hermes
            <span className="sb-dot green" /> Neuro-sama
            <span className={`sb-dot ${systemStatus.services.letta === 'ready' ? 'green' : 'yellow'}`} /> Letta
            <span className={`sb-dot ${systemStatus.services.daemon === 'ready' ? 'green' : 'yellow'}`} /> Daemon
          </>
        ) : (
          <>
            <span className="sb-dot yellow" /> 后端连接中...
          </>
        )}
      </div>
    </div>
  );
};

export default App;

import React from 'react';
import { 
  HomeOutlined, 
  MessageOutlined, 
  BranchesOutlined, 
  ScheduleOutlined, 
  BookOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useAppStore } from '../stores/appStore';
import './Sidebar.css';

const menuItems = [
  { key: 'home', icon: <HomeOutlined />, label: '首页' },
  { key: 'chat', icon: <MessageOutlined />, label: '对话' },
  { key: 'flow', icon: <BranchesOutlined />, label: '流程' },
  { key: 'task', icon: <ScheduleOutlined />, label: '任务' },
  { key: 'novel', icon: <BookOutlined />, label: '小说创作' },
  { key: 'settings', icon: <SettingOutlined />, label: '设置' },
] as const;

const Sidebar: React.FC = () => {
  const { currentView, setCurrentView } = useAppStore();

  return (
    <div className="sidebar">
      {menuItems.map((item) => (
        <div
          key={item.key}
          className={`sidebar-item ${currentView === item.key ? 'active' : ''}`}
          onClick={() => setCurrentView(item.key as typeof currentView)}
          title={item.label}
        >
          <span className="sidebar-icon">{item.icon}</span>
        </div>
      ))}
    </div>
  );
};

export default Sidebar;

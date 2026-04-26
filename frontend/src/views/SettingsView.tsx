import React, { useState, useEffect } from 'react';
import { SaveOutlined } from '@ant-design/icons';
import { useAppStore } from '../stores/appStore';
import './SettingsView.css';

import { API_BASE } from '../config';

interface Settings {
  companionName: string;
  avatarMode: 'vrm' | 'live2d';
  personality: string;
  workEngine: string;
  emotionEngine: string;
  apiKey: string;
  ttsEngine: string;
  approvalEnabled: boolean;
  encryptionEnabled: boolean;
  autoBackup: boolean;
}

const defaultSettings: Settings = {
  companionName: '小暖',
  avatarMode: 'vrm',
  personality: '温柔体贴',
  workEngine: 'ollama',
  emotionEngine: 'ollama',
  apiKey: '',
  ttsEngine: 'edge-tts',
  approvalEnabled: true,
  encryptionEnabled: true,
  autoBackup: false,
};

interface ConfigStatus {
  llmReady: boolean;
  ollamaAvailable: boolean;
  openaiConfigured: boolean;
  recommendation: string;
}

const SettingsView: React.FC = () => {
  const { companion, avatarMode, setAvatarMode, setCompanion } = useAppStore();
  const [settings, setSettings] = useState<Settings>({
    ...defaultSettings,
    companionName: companion.name,
    avatarMode,
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [configStatus, setConfigStatus] = useState<ConfigStatus>({
    llmReady: false,
    ollamaAvailable: false,
    openaiConfigured: false,
    recommendation: '检测中...',
  });

  // Load settings from backend on mount
  useEffect(() => {
    const loadSettings = async () => {
      try {
        // Load companion state
        const companionData = await window.companionOS?.api?.getCompanionState()
          ?? await (await fetch(`${API_BASE}/api/companion/state`)).json();
        if (companionData?.name) {
          setSettings((s) => ({ ...s, companionName: companionData.name }));
        }
        // Load persona memory block
        const personaData = await window.companionOS?.api?.getMemory('persona')
          ?? await (await fetch(`${API_BASE}/api/memory/persona`)).json();
        if (personaData?.value) {
          const personality = personaData.value.includes('活泼') ? '元气活泼'
            : personaData.value.includes('理性') ? '冷静理性'
            : personaData.value.includes('傲娇') ? '傲娇毒舌'
            : '温柔体贴';
          setSettings((s) => ({ ...s, personality }));
        }
      } catch {
        // Backend not available, use defaults
      }
    };
    loadSettings();
  }, []);

  // Load config status on mount
  useEffect(() => {
    const loadConfigStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/config/check`);
        const data = await res.json();
        setConfigStatus({
          llmReady: data.llm_ready,
          ollamaAvailable: data.ollama_available,
          openaiConfigured: data.openai_configured,
          recommendation: data.recommendation,
        });
      } catch {
        setConfigStatus((s) => ({ ...s, recommendation: '无法连接后端服务' }));
      }
    };
    loadConfigStatus();
    const interval = setInterval(loadConfigStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const updateSetting = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setSettings((s) => ({ ...s, [key]: value }));
    setSaved(false);
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      // Save companion name
      if (settings.companionName !== companion.name) {
        // Update via companion interact (or update store directly for now)
        setCompanion({ ...companion, name: settings.companionName });
      }

      // Save avatar mode
      setAvatarMode(settings.avatarMode);

      // Save persona to memory
      try {
        await fetch(`${API_BASE}/api/memory/persona`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            label: 'persona',
            value: `我是${settings.companionName}，性格${settings.personality}的桌面伴侣，关心用户的工作和生活`,
          }),
        });
      } catch {
        // Memory save failed, non-critical
      }

      // Save API key via config API
      if (settings.apiKey) {
        try {
          await fetch(`${API_BASE}/api/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ OPENAI_API_KEY: settings.apiKey }),
          });
        } catch {
          // Config save failed
        }
      }

      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings-view">
      <div className="settings-header">
        <h2 className="settings-title">设置</h2>
        <button
          className={`save-btn ${saved ? 'saved' : ''}`}
          onClick={saveSettings}
          disabled={saving}
        >
          <SaveOutlined /> {saving ? '保存中...' : saved ? '已保存' : '保存'}
        </button>
      </div>

      {/* 配置状态 */}
      <section className="settings-section">
        <h3>📡 连接状态</h3>
        <div className="setting-row">
          <label>LLM 状态</label>
          <span className={`status-indicator ${configStatus.llmReady ? 'online' : 'offline'}`}>
            {configStatus.llmReady ? '已就绪' : '未配置'}
          </span>
        </div>
        <div className="setting-row">
          <label>Ollama 本地</label>
          <span className={`status-indicator ${configStatus.ollamaAvailable ? 'online' : 'offline'}`}>
            {configStatus.ollamaAvailable ? '运行中' : '未检测到'}
          </span>
        </div>
        <div className="setting-row">
          <label>OpenAI</label>
          <span className={`status-indicator ${configStatus.openaiConfigured ? 'online' : 'offline'}`}>
            {configStatus.openaiConfigured ? '已配置' : '未配置'}
          </span>
        </div>
        {configStatus.recommendation && (
          <div className="setting-row">
            <label>建议</label>
            <span className="recommendation-text">{configStatus.recommendation}</span>
          </div>
        )}
      </section>

      {/* 伴侣人设 */}
      <section className="settings-section">
        <h3>🧑 伴侣人设</h3>
        <div className="setting-row">
          <label>名称</label>
          <input
            className="setting-input"
            value={settings.companionName}
            onChange={(e) => updateSetting('companionName', e.target.value)}
          />
        </div>
        <div className="setting-row">
          <label>形象模式</label>
          <div className="setting-toggle">
            <button
              className={`toggle-btn ${settings.avatarMode === 'vrm' ? 'active' : ''}`}
              onClick={() => updateSetting('avatarMode', 'vrm')}
            >3D VRM</button>
            <button
              className={`toggle-btn ${settings.avatarMode === 'live2d' ? 'active' : ''}`}
              onClick={() => updateSetting('avatarMode', 'live2d')}
            >2D Live2D</button>
          </div>
        </div>
        <div className="setting-row">
          <label>性格</label>
          <select
            className="setting-select"
            value={settings.personality}
            onChange={(e) => updateSetting('personality', e.target.value)}
          >
            <option>温柔体贴</option>
            <option>元气活泼</option>
            <option>冷静理性</option>
            <option>傲娇毒舌</option>
          </select>
        </div>
      </section>

      {/* AI模型 */}
      <section className="settings-section">
        <h3>🧠 AI模型</h3>
        <div className="setting-row">
          <label>办公引擎</label>
          <select
            className="setting-select"
            value={settings.workEngine}
            onChange={(e) => updateSetting('workEngine', e.target.value)}
          >
            <option value="ollama">Ollama 本地</option>
            <option value="openai">OpenAI GPT-4o</option>
            <option value="claude">Anthropic Claude</option>
            <option value="deepseek">DeepSeek</option>
          </select>
        </div>
        <div className="setting-row">
          <label>情感引擎</label>
          <select
            className="setting-select"
            value={settings.emotionEngine}
            onChange={(e) => updateSetting('emotionEngine', e.target.value)}
          >
            <option value="ollama">Ollama 本地</option>
            <option value="openai">OpenAI GPT-4o</option>
            <option value="deepseek">DeepSeek</option>
          </select>
        </div>
        <div className="setting-row">
          <label>API Key</label>
          <input
            className="setting-input"
            type="password"
            placeholder="sk-..."
            value={settings.apiKey}
            onChange={(e) => updateSetting('apiKey', e.target.value)}
          />
        </div>
      </section>

      {/* 语音 */}
      <section className="settings-section">
        <h3>🔊 语音</h3>
        <div className="setting-row">
          <label>TTS引擎</label>
          <select
            className="setting-select"
            value={settings.ttsEngine}
            onChange={(e) => updateSetting('ttsEngine', e.target.value)}
          >
            <option value="edge-tts">Edge TTS（轻量）</option>
            <option value="cosyvoice">CosyVoice2（低延迟）</option>
            <option value="fishspeech">Fish Speech（多语言）</option>
          </select>
        </div>
        <div className="setting-row">
          <label>语音克隆</label>
          <input className="setting-input" placeholder="上传10s参考音频" disabled />
        </div>
      </section>

      {/* 安全 */}
      <section className="settings-section">
        <h3>🔒 安全与隐私</h3>
        <div className="setting-row">
          <label>操作审批</label>
          <label className="switch">
            <input
              type="checkbox"
              checked={settings.approvalEnabled}
              onChange={(e) => updateSetting('approvalEnabled', e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>
        <div className="setting-row">
          <label>数据加密</label>
          <label className="switch">
            <input
              type="checkbox"
              checked={settings.encryptionEnabled}
              onChange={(e) => updateSetting('encryptionEnabled', e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>
        <div className="setting-row">
          <label>自动备份</label>
          <label className="switch">
            <input
              type="checkbox"
              checked={settings.autoBackup}
              onChange={(e) => updateSetting('autoBackup', e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>
      </section>
    </div>
  );
};

export default SettingsView;

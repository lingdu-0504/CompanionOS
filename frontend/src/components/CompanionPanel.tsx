import React, { useEffect, useState } from 'react';
import { useAppStore } from '../stores/appStore';
import { RelationRadar } from './RelationRadar';
import { TaskPeek } from './TaskPeek';
import './CompanionPanel.css';

import { API_BASE } from '../config';

const EMOTION_ICONS: Record<string, string> = {
  neutral: '😊',
  happy: '😄',
  comfort: '🤗',
  sad: '🥺',
  tired: '😴',
  curious: '🤔',
  love: '😍',
  angry: '😠',
  excited: '🤩',
  worried: '😟',
};

const EMOTION_BUBBLES: Record<string, string[]> = {
  neutral: ['有什么需要帮忙的吗？', '我在这里哦~', '随时为你效劳'],
  happy: ['看起来心情不错呢！', '今天天气真好~', '开心最重要啦！'],
  tired: ['辛苦了，注意休息哦~', '要不要休息一下？', '我陪你歇会儿'],
  sad: ['别难过了，有我陪着你', '一切都会好起来的', '抱抱~'],
  love: ['最喜欢你了~', '有你在真好', '每天都想见到你'],
  curious: ['这个问题很有意思呢！', '让我想想...', '继续说~'],
  comfort: ['我理解你的感受', '慢慢来，不急', '深呼吸~'],
  angry: ['冷静一下，我们一起解决', '深呼吸~', '别生气了嘛'],
  excited: ['太棒了！', '好期待啊~', '一起冲！'],
  worried: ['别担心，交给我吧', '有我在呢', '一切都会好的'],
};

const CompanionPanel: React.FC = () => {
  const { companion, vrmVisible, toggleVRM } = useAppStore();
  const [bubbleText, setBubbleText] = useState('有什么需要帮忙的吗？');
  const [bubbleVisible, setBubbleVisible] = useState(true);
  const [companionLoading, setCompanionLoading] = useState(true);
  const [companionError, setCompanionError] = useState(false);

  // Update emotion bubble based on companion state
  useEffect(() => {
    const emotion = companion.current_emotion || 'neutral';
    const texts = EMOTION_BUBBLES[emotion] || EMOTION_BUBBLES.neutral;
    const randomText = texts[Math.floor(Math.random() * texts.length)];
    setBubbleText(randomText);
    setBubbleVisible(true);

    const timer = setTimeout(() => setBubbleVisible(false), 5000);
    return () => clearTimeout(timer);
  }, [companion.current_emotion]);

  // Periodically fetch companion state
  useEffect(() => {
    let mounted = true;
    let timer: ReturnType<typeof setInterval>;

    const fetchCompanion = async () => {
      try {
        setCompanionError(false);
        const res = await fetch(`${API_BASE}/api/companion/state`);
        if (!mounted) return;
        const data = await res.json();
        if (data && mounted) {
          useAppStore.getState().setCompanion(data);
        }
      } catch {
        if (mounted) {
          setCompanionError(true);
        }
      } finally {
        if (mounted) {
          setCompanionLoading(false);
        }
      }
    };

    fetchCompanion();
    timer = setInterval(fetchCompanion, 10000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const handleVRMToggle = async () => {
    toggleVRM();
    try {
      await window.companionOS?.toggleVRM(!vrmVisible);
    } catch {
      // Not in Electron
    }
  };

  const handleInteract = async (type: string) => {
    try {
      await fetch(`${API_BASE}/api/companion/interact?interaction_type=${type}&delta=1.0`, {
        method: 'POST',
      });
      const res = await fetch(`${API_BASE}/api/companion/state`);
      const data = await res.json();
      if (data) useAppStore.getState().setCompanion(data);
    } catch {
      // Backend not available
    }
  };

  const emotionIcon = EMOTION_ICONS[companion.current_emotion] || '😊';

  return (
    <div className="companion-panel">
      {/* 伴侣形象区 */}
      <div className="companion-avatar">
        <div className="avatar-container">
          <div className="avatar-placeholder" onClick={() => handleInteract('praise')}>
            {companionLoading ? (
              <span className="loading" style={{ fontSize: 16 }}>加载中...</span>
            ) : (
              <span className="avatar-emoji">{emotionIcon}</span>
            )}
          </div>
          <div className="avatar-label">{companion.name}</div>
        </div>
        <button className="vrm-toggle" onClick={handleVRMToggle}>
          {vrmVisible ? '🎭 隐藏' : '🎭 显示'}
        </button>
      </div>

      {companionError && (
        <div className="error-message" style={{ fontSize: 12, textAlign: 'center' }}>
          伴侣状态同步失败
        </div>
      )}

      {/* 情感气泡 */}
      <div className={`emotion-bubble ${bubbleVisible ? 'visible' : 'hidden'}`}>
        <div className="bubble-content">{bubbleText}</div>
      </div>

      {/* 快捷互动 */}
      <div className="quick-interact">
        <button className="interact-btn" onClick={() => handleInteract('praise')} title="夸奖">👍</button>
        <button className="interact-btn" onClick={() => handleInteract('comfort')} title="安慰">🤗</button>
        <button className="interact-btn" onClick={() => handleInteract('chat')} title="闲聊">💬</button>
        <button className="interact-btn" onClick={() => handleInteract('emotional_support')} title="依靠">❤️</button>
      </div>

      {/* 关系雷达 */}
      <RelationRadar companion={companion} />

      {/* 关系等级 */}
      <div className="relation-level">
        <div className="relation-badge">
          Lv.{companion.relation_level} {companion.relation_name}
        </div>
        <div className="relation-bar">
          <div
            className="relation-fill"
            style={{
              width: `${(companion.affection + companion.trust + companion.intimacy + companion.comfort + companion.respect) / 5}%`,
            }}
          />
        </div>
      </div>

      {/* 任务速览 */}
      <TaskPeek />
    </div>
  );
};

export default CompanionPanel;

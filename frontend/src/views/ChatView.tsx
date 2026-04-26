import React, { useState, useRef, useEffect, useCallback } from 'react';
import { SendOutlined, AudioOutlined, PaperClipOutlined } from '@ant-design/icons';
import { useAppStore } from '../stores/appStore';
import type { ChatMessage } from '../types';
import './ChatView.css';

import { API_BASE } from '../config';

const ChatView: React.FC = () => {
  const { messages, addMessage, updateMessage, companion, loading, setLoading } = useAppStore();
  const [input, setInput] = useState('');
  const [sendError, setSendError] = useState(false);
  const [failedMessage, setFailedMessage] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      let content = `[附件] ${file.name}`;
      if (file.type === 'text/plain') {
        const text = await file.text();
        const preview = text.length > 500 ? text.slice(0, 500) + '...' : text;
        content += `\n${preview}`;
      } else if (file.type.startsWith('image/')) {
        content += '\n[图片文件]';
      } else {
        content += `\n[文件类型: ${file.type || '未知'}]`;
      }

      const userMsg: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content,
        timestamp: Date.now(),
      };
      addMessage(userMsg);
      sendMessage(content);
    } catch (err) {
      console.error('File read error:', err);
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleVoiceToggle = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());

        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        if (audioBlob.size === 0) return;

        try {
          const formData = new FormData();
          formData.append('audio', audioBlob, 'recording.webm');

          const res = await fetch(`${API_BASE}/api/voice/recognize`, {
            method: 'POST',
            body: formData,
          });

          if (!res.ok) throw new Error('ASR request failed');

          const data = await res.json();
          const transcribedText = data.text || data.content || '';

          if (transcribedText) {
            const userMsg: ChatMessage = {
              id: Date.now().toString(),
              role: 'user',
              content: transcribedText,
              timestamp: Date.now(),
            };
            addMessage(userMsg);
            sendMessage(transcribedText);
          }
        } catch (err) {
          console.error('Voice recognition error:', err);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error('Microphone access error:', err);
    }
  };

  const sendMessage = useCallback(async (retryText?: string) => {
    const messageText = retryText || input.trim();
    if (!messageText || loading) return;

    setSendError(false);
    setFailedMessage('');

    if (!retryText) {
      const userMsg: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content: messageText,
        timestamp: Date.now(),
      };
      addMessage(userMsg);
      setInput('');
    }

    setLoading(true);

    // Create streaming AI message placeholder
    const aiMsgId = (Date.now() + 1).toString();
    const aiMsg: ChatMessage = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    };
    addMessage(aiMsg);

    try {
      // Try SSE streaming first
      abortRef.current = new AbortController();
      const res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageText }),
        signal: abortRef.current.signal,
      });

      if (res.ok && res.body) {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';
        let intent = '';
        let emotion = '';
        let companionRemark = '';

        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const dataStr = line.slice(6).trim();
            if (dataStr === '[DONE]') break;

            try {
              const data = JSON.parse(dataStr);

              if (data.type === 'intent') {
                intent = data.intent;
              } else if (data.type === 'emotion') {
                emotion = data.emotion || emotion;
              } else if (data.type === 'token') {
                fullContent += data.content || '';
                updateMessage(aiMsgId, { content: fullContent });
              } else if (data.type === 'done') {
                fullContent = data.content || fullContent;
                companionRemark = data.companion_remark || companionRemark;
              } else if (data.type === 'eigent_result') {
                fullContent += `\n\n🔧 Agent执行结果: ${JSON.stringify(data.data, null, 2)}`;
                updateMessage(aiMsgId, { content: fullContent });
              } else if (data.content) {
                fullContent += data.content;
                updateMessage(aiMsgId, { content: fullContent });
              }
            } catch {
              // Not JSON, skip
            }
          }
        }

        updateMessage(aiMsgId, {
          content: fullContent,
          intent,
          emotion,
          companion_remark: companionRemark,
        });
      } else {
        throw new Error('Stream failed');
      }
    } catch {
      // Stream failed, fallback to non-streaming
      try {
        const data = await window.companionOS?.api?.chat(messageText)
          ?? await (await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: messageText }),
          })).json();

        updateMessage(aiMsgId, {
          content: data.content || '暂无回复',
          intent: data.intent,
          emotion: data.emotion,
          companion_remark: data.companion_remark,
          vrm_action: data.vrm_action,
        });
      } catch {
        updateMessage(aiMsgId, { content: '抱歉，连接后端服务失败，请确保后端已启动。' });
        setSendError(true);
        setFailedMessage(messageText);
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }, [input, loading, addMessage, updateMessage, setLoading]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-view">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="empty-icon">💬</div>
            <p>和{companion.name}开始对话吧</p>
            <p className="empty-hint">支持办公指令和情感闲聊</p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-msg ${msg.role}`}>
            {msg.role === 'assistant' && (
              <div className="msg-avatar">{companion.name[0]}</div>
            )}
            <div className="msg-body">
              <div className="msg-content">
                {msg.content || (
                  <div className="msg-typing">
                    <span></span><span></span><span></span>
                  </div>
                )}
              </div>
              {msg.companion_remark && (
                <div className="msg-remark">💬 {msg.companion_remark}</div>
              )}
              {msg.intent && (
                <span className={`msg-intent ${msg.intent}`}>
                  {msg.intent === 'work' ? '办公' : msg.intent === 'emotional' ? '情感' : msg.intent === 'greeting' ? '问候' : '混合'}
                </span>
              )}
            </div>
          </div>
        ))}
        {loading && messages[messages.length - 1]?.role === 'user' && (
          <div className="chat-msg assistant">
            <div className="msg-avatar">{companion.name[0]}</div>
            <div className="msg-body">
              <div className="msg-typing">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-bar">
        <input type="file" ref={fileInputRef} onChange={handleFileSelect} style={{ display: 'none' }} accept=".txt,image/*" />
        <button className="input-btn" title="附件" onClick={() => fileInputRef.current?.click()}><PaperClipOutlined /></button>
        <button className={`input-btn${isRecording ? ' recording' : ''}`} title={isRecording ? '停止录音' : '语音'} onClick={handleVoiceToggle}><AudioOutlined /></button>
        <textarea
          className="chat-textarea"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={`输入消息，和${companion.name}对话...`}
          rows={1}
        />
        <button
          className="send-btn"
          onClick={() => sendMessage()}
          disabled={!input.trim() || loading}
        >
          <SendOutlined />
        </button>
      </div>
      {sendError && (
        <div className="chat-retry-bar">
          <span className="retry-text">发送失败</span>
          <button className="retry-btn" onClick={() => sendMessage(failedMessage)} disabled={loading}>
            重试
          </button>
        </div>
      )}
    </div>
  );
};

export default ChatView;

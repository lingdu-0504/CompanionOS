# CompanionOS

> 国内首个虚拟伴侣AI办公一体桌面端应用

**可视化工作流办公 + 情感化虚拟伴侣 + 自托管隐私保障**

---

## 项目概览

CompanionOS 将「可视化工作流办公」「3D/2D情感伴侣」「多Agent协作」「自托管隐私」四合一，打造有温度的桌面AI助手。

### 核心特性

- 🧠 **双引擎AI**：Hermes办公引擎 + Neuro-sama情感引擎，意图识别自动路由
- 🔄 **可视化工作流**：React Flow画布，12+节点类型，拖拽编排办公流程
- 👩 **3D/2D伴侣**：VRM(3D) + Live2D(2D) 双渲染，8阶段关系进阶，5维情绪追踪
- 🔊 **语音交互**：Edge TTS + CosyVoice2 + FishSpeech，Whisper ASR
- 🔒 **全本地化**：SQLite存储，OS Keychain密钥管理，操作审批机制
- 🔗 **双总线协议**：MCP(工具通信) + A2A(Agent协作)

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 桌面框架 | Electron 33+ |
| 前端 | React 19 + TypeScript + Vite + Ant Design |
| 状态管理 | Zustand |
| 工作流画布 | React Flow (@xyflow/react) |
| 3D渲染 | Three.js + @pixiv/three-vrm (Phase 6) |
| 2D渲染 | pixi-live2d-display (Phase 6) |
| 后端 | Python 3.11+ + FastAPI |
| 工具协议 | MCP (Phase 2) |
| Agent协议 | A2A (Phase 2) |
| 记忆系统 | Letta/MemGPT (Phase 4) |
| 数据库 | SQLite + 文件系统 |
| TTS | Edge TTS + CosyVoice2 + FishSpeech (Phase 7) |
| ASR | Whisper (Phase 7) |

---

## 项目结构

```
CompanionOS/
├── electron/                          # Electron主进程
│   ├── main.js                       # 主进程入口
│   ├── preload.js                    # 预加载脚本
│   ├── window-manager.js             # 窗口管理器
│   ├── process-manager.js            # 子进程管理
│   └── tray.js                       # 系统托盘
│
├── frontend/                          # React前端
│   ├── src/
│   │   ├── App.tsx                   # 主应用（三栏布局）
│   │   ├── views/                    # 5个模式视图
│   │   │   ├── HomeView.tsx          # 首页
│   │   │   ├── ChatView.tsx          # 对话模式
│   │   │   ├── FlowView.tsx          # 工作流编辑器
│   │   │   ├── TaskView.tsx          # 任务管理
│   │   │   └── SettingsView.tsx      # 设置面板
│   │   ├── components/               # 通用组件
│   │   │   ├── Sidebar.tsx           # 侧栏导航
│   │   │   ├── CompanionPanel.tsx    # 伴侣区
│   │   │   ├── RelationRadar.tsx     # 关系雷达图
│   │   │   └── TaskPeek.tsx          # 任务速览
│   │   ├── stores/                   # Zustand状态
│   │   └── types/                    # 类型定义
│   └── vite.config.ts
│
├── backend/                           # Python统一后端
│   ├── server.py                     # FastAPI入口 (端口18080)
│   ├── router/                       # 意图识别+路由
│   │   ├── agent_router.py           # 办公/情感路由
│   │   └── intent_classifier.py      # 意图分类器
│   ├── workflow_engine/              # 工作流引擎
│   │   ├── engine.py                 # DAG解析执行
│   │   └── node_registry.py          # 节点注册表(12+节点)
│   ├── agent_bridge/                 # 智能体总线
│   │   ├── hermes_adapter.py         # Hermes办公引擎适配
│   │   ├── neuro_adapter.py          # Neuro-sama情感引擎适配
│   │   ├── mcp_gateway.py            # MCP统一网关
│   │   └── a2a_gateway.py            # A2A Agent间通信
│   ├── memory/                       # 记忆系统
│   │   ├── letta_bridge.py           # Letta记忆中枢桥接
│   │   └── sync.py                   # 多源记忆同步
│   ├── companion/                    # 伴侣引擎
│   │   └── utsuwa_engine.py          # Utsuwa关系/情绪引擎
│   ├── voice/                        # 语音服务
│   │   ├── service.py                # 统一语音服务
│   │   └── tts_edge.py              # Edge TTS
│   ├── security/                     # 安全层
│   │   └── __init__.py               # Keychain+审批+加密
│   ├── daemon/                       # 守护进程
│   │   └── __init__.py               # 文件监听+定时+队列
│   ├── data/                         # 本地数据存储
│   └── pyproject.toml                # Python依赖
│
├── package.json                       # Node.js依赖
├── electron-builder.yml              # 打包配置
├── .env.example                      # 环境变量模板
└── README.md
```

---

## 快速开始

### 前置条件

- Node.js >= 20
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) (Python包管理)
- pnpm (推荐)

### 安装依赖

```bash
# 安装前端依赖
cd frontend && npm install && cd ..

# 安装后端依赖
cd backend && uv sync && cd ..
```

### 开发模式

```bash
# 同时启动前端+后端+Electron
npm run dev

# 或分别启动
npm run dev:frontend   # 前端开发服务器 http://localhost:5173
npm run dev:backend    # 后端API服务 http://localhost:18080
npm run dev:electron   # Electron桌面窗口
```

### 环境变量

```bash
cp .env.example .env
# 编辑 .env 填入API Key等配置
```

### 构建打包

```bash
npm run build          # 构建并打包
npm run build:mac      # macOS
npm run build:win      # Windows
npm run build:linux    # Linux
```

---

## API 接口

后端服务运行在 `http://localhost:18080`

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 系统状态 |
| `/api/chat` | POST | 核心对话（意图识别+双引擎路由） |
| `/api/workflow` | GET/POST | 工作流列表/创建 |
| `/api/workflow/{id}/execute` | POST | 执行工作流 |
| `/api/workflow/node-types` | GET | 可用节点类型 |
| `/api/memory` | GET | 所有记忆块 |
| `/api/memory/{type}` | GET/PUT | 读写记忆块 |
| `/api/companion/state` | GET | 伴侣状态 |
| `/api/companion/interact` | POST | 伴侣互动 |
| `/api/voice/tts` | POST | 语音合成 |
| `/api/mcp/tools` | GET | MCP工具列表 |
| `/api/a2a/agents` | GET | A2A Agent列表 |
| `/ws` | WebSocket | 实时通信 |

---

## 开发进度

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 1 项目脚手架 | ✅ 完成 | Electron+React+FastAPI+Monorepo |
| Phase 2 核心后端服务 | 🔜 进行中 | MCP+A2A网关+Hermes集成 |
| Phase 3 前端UI框架 | ✅ 基础完成 | 三栏布局+5模式视图+伴侣区 |
| Phase 4 AI引擎集成 | 📋 待开始 | Hermes+Neuro-sama+Letta |
| Phase 5 工作流引擎 | 📋 待开始 | ReactFlow扩展+节点执行器 |
| Phase 6 伴侣渲染 | 📋 待开始 | VRM/Live2D+关系系统 |
| Phase 7 语音交互 | 📋 待开始 | CosyVoice2+Whisper |
| Phase 8 收尾交付 | 📋 待开始 | 测试+打包+文档 |

---

## 许可证

MIT License

---

*CompanionOS - 让每一次办公都有温度*

/**
 * CompanionOS 子进程管理器
 * 管理Python后端服务、Hermes MCP服务等子进程
 */

const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

class ProcessManager {
  constructor() {
    this.processes = new Map();
    this.uvPath = this._detectUvPath();
  }

  /**
   * 检测 uv 可执行文件路径
   * 支持多个常见安装位置
   */
  _detectUvPath() {
    const home = process.env.HOME || '/root';
    const candidates = [
      path.join(home, '.local/bin/uv'),
      path.join(home, '.cargo/bin/uv'),
      '/opt/homebrew/bin/uv',
      '/usr/local/bin/uv',
    ];

    // 首先检查常见路径
    for (const candidate of candidates) {
      if (fs.existsSync(candidate)) {
        console.log(`[ProcessManager] 检测到 uv: ${candidate}`);
        return candidate;
      }
    }

    // 尝试通过 which 命令查找
    try {
      const whichPath = execSync('which uv 2>/dev/null', { encoding: 'utf8' }).trim();
      if (whichPath && fs.existsSync(whichPath)) {
        console.log(`[ProcessManager] 通过 which 检测到 uv: ${whichPath}`);
        return whichPath;
      }
    } catch {
      // which 命令失败，忽略
    }

    // 默认回退
    console.warn('[ProcessManager] 未找到 uv，使用默认路径');
    return candidates[0];
  }

  /**
   * 启动Python后端服务
   */
  startBackend() {
    const backendDir = path.join(__dirname, '..', 'backend');
    const proc = spawn(
      this.uvPath,
      ['run', 'python', '-m', 'uvicorn', 'server:app', '--host', '127.0.0.1', '--port', '18080'],
      { cwd: backendDir, stdio: ['pipe', 'pipe', 'pipe'] }
    );

    this._registerProcess('backend', proc);
    return proc;
  }

  /**
   * 启动MCP网关服务
   */
  startMCPGateway() {
    const backendDir = path.join(__dirname, '..', 'backend');
    const proc = spawn(
      this.uvPath,
      ['run', 'python', '-m', 'mcp_gateway', '--port', '18081'],
      { cwd: backendDir, stdio: ['pipe', 'pipe', 'pipe'] }
    );
    this._registerProcess('mcp-gateway', proc);
    return proc;
  }

  /**
   * 启动A2A网关服务
   */
  startA2AGateway() {
    const backendDir = path.join(__dirname, '..', 'backend');
    const proc = spawn(
      this.uvPath,
      ['run', 'python', '-m', 'a2a_gateway', '--port', '18082'],
      { cwd: backendDir, stdio: ['pipe', 'pipe', 'pipe'] }
    );
    this._registerProcess('a2a-gateway', proc);
    return proc;
  }

  /**
   * 注册子进程
   */
  _registerProcess(name, proc) {
    this.processes.set(name, proc);

    proc.stdout.on('data', (data) => {
      console.log(`[${name}] ${data.toString().trim()}`);
    });

    proc.stderr.on('data', (data) => {
      console.error(`[${name}] ${data.toString().trim()}`);
    });

    proc.on('exit', (code) => {
      console.log(`[${name}] 进程退出，代码: ${code}`);
      this.processes.delete(name);
    });

    proc.on('error', (err) => {
      console.error(`[${name}] 进程错误: ${err.message}`);
    });
  }

  /**
   * 停止指定进程
   */
  stopProcess(name) {
    const proc = this.processes.get(name);
    if (proc) {
      proc.kill('SIGTERM');
      this.processes.delete(name);
    }
  }

  /**
   * 停止所有进程
   */
  stopAll() {
    for (const [name, proc] of this.processes) {
      try {
        proc.kill('SIGTERM');
      } catch (e) {
        console.error(`[ProcessManager] 停止 ${name} 失败:`, e.message);
      }
    }
    this.processes.clear();
  }

  /**
   * 获取运行中的进程列表
   */
  getRunningProcesses() {
    return Array.from(this.processes.keys());
  }

  /**
   * 检查进程是否运行中
   */
  isRunning(name) {
    return this.processes.has(name);
  }

  /**
   * 等待后端服务就绪
   */
  async waitForBackend(maxRetries = 30, interval = 1000) {
    const http = require('http');
    
    for (let i = 0; i < maxRetries; i++) {
      try {
        await new Promise((resolve, reject) => {
          const req = http.get('http://127.0.0.1:18080/api/status', (res) => {
            resolve(res.statusCode === 200);
          });
          req.on('error', reject);
          req.setTimeout(2000, () => {
            req.destroy();
            reject(new Error('timeout'));
          });
        });
        console.log('[ProcessManager] 后端服务已就绪');
        return true;
      } catch {
        if (i < maxRetries - 1) {
          await new Promise((r) => setTimeout(r, interval));
        }
      }
    }
    console.warn('[ProcessManager] 后端服务未就绪（超时），继续启动...');
    return false;
  }
}

module.exports = ProcessManager;

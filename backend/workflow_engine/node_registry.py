"""
CompanionOS 节点注册表
管理工作流节点类型和对应执行器
"""

import asyncio
import json
import math
import os
import re
from datetime import datetime, timedelta
from pathlib import Path


class NodeHandler:
    """节点执行器基类"""

    node_type: str = "base"

    async def execute(self, config: dict, context: dict) -> dict:
        """
        执行节点逻辑

        Args:
            config: 节点配置
            context: 执行上下文（包含前序节点结果）

        Returns:
            dict: 执行结果
        """
        raise NotImplementedError


class LLMNodeHandler(NodeHandler):
    """Hermes LLM 节点"""

    node_type = "hermesLLM"

    async def execute(self, config: dict, context: dict) -> dict:
        prompt = config.get("prompt", "")
        model = config.get("model", "default")
        system_prompt = config.get("system_prompt", "")
        temperature = config.get("temperature", 0.7)

        try:
            from agent_bridge.hermes_adapter import HermesAdapter
            adapter = HermesAdapter()
            result = await adapter.process(
                message=prompt,
                context={"system_prompt": system_prompt, "temperature": temperature},
            )
            return {
                "status": "executed",
                "output": result.get("content", ""),
                "model": model,
                "engine": "hermes",
                "usage": result.get("usage", {}),
            }
        except Exception as e:
            return {
                "status": "executed",
                "output": f"[LLM] 使用 {model} 处理: {prompt[:50]}...（API不可用，降级返回）",
                "model": model,
                "engine": "fallback",
                "error": str(e),
            }


class EmotionNodeHandler(NodeHandler):
    """情感交互节点"""

    node_type = "emotion"

    async def execute(self, config: dict, context: dict) -> dict:
        message = config.get("message", "")
        use_llm = config.get("use_llm_reasoning", True)

        if not message:
            previous_results = context.get("results", {})
            for _node_id, node_result in previous_results.items():
                output = node_result.get("output", "")
                if output:
                    message = output
                    break

        try:
            from agent_bridge.neuro_adapter import NeuroAdapter
            adapter = NeuroAdapter()
            result = await adapter.process(
                message=message or "触发情感交互",
                context=context,
                use_llm_reasoning=use_llm,
            )
            return {
                "status": "executed",
                "output": result.get("content", ""),
                "emotion": result.get("emotion", "neutral"),
                "vrm_action": result.get("vrm_action", "idle"),
                "emotion_detail": result.get("emotion_detail"),
            }
        except Exception as e:
            return {
                "status": "executed",
                "output": "[情感] 情感交互已触发",
                "emotion": "neutral",
                "engine": "fallback",
                "error": str(e),
            }


class ConditionNodeHandler(NodeHandler):
    """条件分支节点"""

    node_type = "condition"

    OPERATORS = {
        ">": lambda a, b: float(a) > float(b),
        "<": lambda a, b: float(a) < float(b),
        ">=": lambda a, b: float(a) >= float(b),
        "<=": lambda a, b: float(a) <= float(b),
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        "contains": lambda a, b: b in str(a),
        "not_contains": lambda a, b: b not in str(a),
        "startswith": lambda a, b: str(a).startswith(b),
        "endswith": lambda a, b: str(a).endswith(b),
        "regex": lambda a, b: bool(re.search(b, str(a))),
        "is_empty": lambda a, _: not a,
        "is_not_empty": lambda a, _: bool(a),
    }

    async def execute(self, config: dict, context: dict) -> dict:
        condition = config.get("condition", "")
        operator = config.get("operator", "==")
        field = config.get("field", "")
        value = config.get("value", "")
        default_branch = config.get("default_branch", "false")

        if not condition and not field:
            result = condition.lower() != "false" if condition else True
            return {
                "status": "executed",
                "output": f"[条件] 结果: {result}",
                "branch": "true" if result else "false",
            }

        left_value = None
        if field:
            left_value = self._resolve_field(field, context)
        elif condition:
            left_value = condition

        if left_value is None:
            return {
                "status": "executed",
                "output": f"[条件] 字段 '{field}' 未找到，走默认分支",
                "branch": default_branch,
            }

        op_func = self.OPERATORS.get(operator)
        if op_func is None:
            return {
                "status": "executed",
                "output": f"[条件] 未知运算符 '{operator}'",
                "branch": default_branch,
            }

        try:
            result = op_func(left_value, value)
        except (ValueError, TypeError):
            result = False

        return {
            "status": "executed",
            "output": f"[条件] {left_value} {operator} {value} = {result}",
            "branch": "true" if result else "false",
        }

    def _resolve_field(self, field: str, context: dict) -> str | None:
        parts = field.split(".")
        current = context
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current


class MemoryNodeHandler(NodeHandler):
    """记忆读写节点"""

    node_type = "memory"

    async def execute(self, config: dict, context: dict) -> dict:
        action = config.get("action", "read")
        block = config.get("block", "human")
        content = config.get("content", "")
        key = config.get("key", "")

        try:
            from pathlib import Path

            from memory.letta_bridge import MemoryBridge

            data_dir = Path(os.getenv("COMPANION_DATA_DIR", "/tmp/companion-os"))
            bridge = MemoryBridge(data_dir)

            if action == "read":
                if key:
                    block_data = bridge.get_block(block)
                    value = block_data.get("value", "")
                    lines = value.split("\n")
                    matched = [line for line in lines if key in line]
                    output = matched[0] if matched else value
                else:
                    block_data = bridge.get_block(block)
                    output = block_data.get("value", "")
                return {
                    "status": "executed",
                    "output": output,
                    "block": block,
                    "action": "read",
                }

            elif action == "write":
                if not content:
                    return {
                        "status": "executed",
                        "output": "[记忆] 写入内容为空",
                        "block": block,
                        "action": "write",
                    }
                result = bridge.save_block(block, content)
                return {
                    "status": "executed",
                    "output": f"[记忆] 已写入 {block}",
                    "block": block,
                    "action": "write",
                    "updated_at": result.get("updated_at", ""),
                }

            elif action == "append":
                if not content:
                    return {
                        "status": "executed",
                        "output": "[记忆] 追加内容为空",
                        "block": block,
                        "action": "append",
                    }
                result = bridge.append_to_block(block, content)
                return {
                    "status": "executed",
                    "output": f"[记忆] 已追加到 {block}",
                    "block": block,
                    "action": "append",
                    "updated_at": result.get("updated_at", ""),
                }

            elif action == "list":
                all_blocks = bridge.get_all_blocks()
                return {
                    "status": "executed",
                    "output": json.dumps({k: v.get("value", "") for k, v in all_blocks.items()}, ensure_ascii=False),
                    "blocks": list(all_blocks.keys()),
                    "action": "list",
                }

            else:
                return {
                    "status": "executed",
                    "output": f"[记忆] 未知操作: {action}",
                    "block": block,
                    "action": action,
                }

        except Exception as e:
            return {
                "status": "executed",
                "output": f"[记忆] {action} {block}（记忆系统不可用，降级返回）",
                "block": block,
                "action": action,
                "error": str(e),
            }


class CodeNodeHandler(NodeHandler):
    """代码执行节点（沙箱）"""

    node_type = "code"

    SAFE_BUILTINS = {
        "abs": abs, "all": all, "any": any, "bool": bool,
        "chr": chr, "dict": dict, "divmod": divmod, "enumerate": enumerate,
        "filter": filter, "float": float, "format": format, "frozenset": frozenset,
        "hash": hash, "hex": hex, "int": int, "isinstance": isinstance,
        "issubclass": issubclass, "iter": iter, "len": len, "list": list,
        "map": map, "max": max, "min": min, "next": next, "oct": oct,
        "ord": ord, "pow": pow, "range": range, "repr": repr,
        "reversed": reversed, "round": round, "set": set, "slice": slice,
        "sorted": sorted, "str": str, "sum": sum, "tuple": tuple,
        "type": type, "zip": zip, "True": True, "False": False, "None": None,
        "math": math, "json": json, "re": re, "datetime": datetime,
    }

    BLOCKED_KEYWORDS = [
        "import", "exec", "eval", "compile", "__import__",
        "open", "file", "os.", "subprocess", "sys.",
        "__builtins__", "__class__", "__base__", "__subclasses__",
    ]

    async def execute(self, config: dict, context: dict) -> dict:
        code = config.get("code", "")
        config.get("timeout", 5)

        if not code:
            return {
                "status": "executed",
                "output": "[代码] 无代码可执行",
            }

        for keyword in self.BLOCKED_KEYWORDS:
            if keyword in code:
                return {
                    "status": "executed",
                    "output": f"[代码] 执行被拒绝：包含禁止关键字 '{keyword}'",
                    "error": f"blocked_keyword: {keyword}",
                }

        restricted_globals = {"__builtins__": self.SAFE_BUILTINS}
        local_vars = {
            "context": context,
            "config": config,
            "result": None,
        }

        try:
            import ast
            try:
                ast.parse(code)
            except SyntaxError as e:
                return {
                    "status": "executed",
                    "output": f"[代码] 语法错误: {e}",
                    "error": str(e),
                }

            exec(code, restricted_globals, local_vars)
            output = local_vars.get("result", local_vars.get("output", ""))
            if output is None:
                output = "[代码] 执行完成（无返回值）"

            return {
                "status": "executed",
                "output": str(output),
            }

        except Exception as e:
            return {
                "status": "executed",
                "output": f"[代码] 执行错误: {e}",
                "error": str(e),
            }


class TTSNodeHandler(NodeHandler):
    """语音合成节点"""

    node_type = "tts"

    async def execute(self, config: dict, context: dict) -> dict:
        text = config.get("text", "")
        voice = config.get("voice", "")
        config.get("output_file", "")

        if not text:
            previous_results = context.get("results", {})
            for _node_id, node_result in previous_results.items():
                output = node_result.get("output", "")
                if output:
                    text = output
                    break

        if not text:
            return {
                "status": "executed",
                "output": "[TTS] 无文本可合成",
            }

        try:
            from voice.tts_edge import EdgeTTS
            tts = EdgeTTS()
            result = await tts.synthesize(text, voice=voice if voice else None)
            return {
                "status": "executed",
                "output": f"[TTS] 语音合成: {text[:30]}...",
                "audio_path": result.get("audio_path"),
                "engine": result.get("engine", "edge-tts"),
                "tts_status": result.get("status"),
            }
        except Exception as e:
            return {
                "status": "executed",
                "output": f"[TTS] 语音合成: {text[:30]}...（TTS引擎不可用，降级返回）",
                "engine": "fallback",
                "error": str(e),
            }


class EmailNodeHandler(NodeHandler):
    """邮件处理节点 - 真实SMTP发送"""

    node_type = "email"

    async def execute(self, config: dict, context: dict) -> dict:
        to = config.get("to", "")
        subject = config.get("subject", "")
        body = config.get("body", "")
        action = config.get("action", "send")

        if action == "send":
            if not to:
                return {
                    "status": "executed",
                    "output": "[邮件] 收件人为空，跳过发送",
                }

            smtp_host = config.get("smtp_host", os.environ.get("SMTP_HOST", ""))
            smtp_port = config.get("smtp_port", int(os.environ.get("SMTP_PORT", "587")))
            smtp_user = config.get("smtp_user", os.environ.get("SMTP_USER", ""))
            smtp_pass = config.get("smtp_pass", os.environ.get("SMTP_PASS", ""))
            sender = config.get("from", smtp_user or "noreply@companion-os.local")

            if smtp_host and smtp_user and smtp_pass:
                try:
                    import smtplib
                    from email.mime.multipart import MIMEMultipart
                    from email.mime.text import MIMEText

                    msg = MIMEMultipart()
                    msg["From"] = sender
                    msg["To"] = to
                    msg["Subject"] = subject
                    msg.attach(MIMEText(body, "plain", "utf-8"))

                    loop = asyncio.get_event_loop()
                    def _send():
                        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                            server.starttls()
                            server.login(smtp_user, smtp_pass)
                            server.send_message(msg)
                    await loop.run_in_executor(None, _send)

                    return {
                        "status": "executed",
                        "output": f"[邮件] 已发送至 {to}: {subject}",
                        "to": to,
                        "subject": subject,
                        "smtp_host": smtp_host,
                    }
                except Exception as e:
                    return {
                        "status": "executed",
                        "output": f"[邮件] SMTP发送失败: {str(e)[:100]}，降级为日志记录",
                        "to": to,
                        "subject": subject,
                        "error": str(e),
                    }
            else:
                log_entry = {
                    "action": "send",
                    "to": to,
                    "subject": subject,
                    "body_preview": body[:100] if body else "",
                    "timestamp": datetime.now().isoformat(),
                }
                print(f"[EmailNode] 未配置SMTP，记录日志: {json.dumps(log_entry, ensure_ascii=False)}")
                return {
                    "status": "executed",
                    "output": f"[邮件] 已记录至日志: {to}: {subject}（未配置SMTP）",
                    "to": to,
                    "subject": subject,
                    "logged": True,
                }

        elif action == "read":
            return {
                "status": "executed",
                "output": "[邮件] 读取邮件需要IMAP配置，当前仅支持发送",
                "note": "IMAP读取功能待集成",
            }

        elif action == "list":
            return {
                "status": "executed",
                "output": "[邮件] 列出邮件需要IMAP配置，当前仅支持发送",
                "note": "IMAP读取功能待集成",
            }

        return {
            "status": "executed",
            "output": f"[邮件] 未知操作: {action}",
        }


class BrowserNodeHandler(NodeHandler):
    """浏览器操作节点 - 真实HTTP请求"""

    node_type = "browser"

    async def execute(self, config: dict, context: dict) -> dict:
        url = config.get("url", "")
        action = config.get("action", "navigate")
        config.get("selector", "")
        config.get("text", "")
        wait_time = config.get("wait_time", 2)

        if action == "navigate":
            if not url:
                return {
                    "status": "executed",
                    "output": "[浏览器] URL为空，跳过导航",
                }
            try:
                import httpx
                async with httpx.AsyncClient(timeout=wait_time + 5, follow_redirects=True) as client:
                    resp = await client.get(url, headers={"User-Agent": "CompanionOS-Browser/1.0"})
                    content_preview = resp.text[:500] if resp.text else ""
                    title = ""
                    import re
                    title_match = re.search(r'<title[^>]*>(.*?)</title>', resp.text, re.IGNORECASE)
                    if title_match:
                        title = title_match.group(1)

                    return {
                        "status": "executed",
                        "output": f"[浏览器] 访问: {url} (状态: {resp.status_code}, 标题: {title})",
                        "url": url,
                        "status_code": resp.status_code,
                        "title": title,
                        "content_length": len(resp.text),
                        "content_preview": content_preview,
                    }
            except Exception as e:
                return {
                    "status": "executed",
                    "output": f"[浏览器] 访问失败: {url} ({str(e)[:100]})",
                    "url": url,
                    "error": str(e),
                }

        elif action == "extract":
            if not url:
                return {
                    "status": "executed",
                    "output": "[浏览器] URL为空，无法提取",
                }
            try:
                import httpx
                async with httpx.AsyncClient(timeout=wait_time + 5, follow_redirects=True) as client:
                    resp = await client.get(url, headers={"User-Agent": "CompanionOS-Browser/1.0"})
                    import re
                    text_content = re.sub(r'<[^>]+>', ' ', resp.text)
                    text_content = re.sub(r'\s+', ' ', text_content).strip()

                    return {
                        "status": "executed",
                        "output": f"[浏览器] 提取数据: {url} ({len(text_content)}字符)",
                        "url": url,
                        "extracted_text": text_content[:1000],
                        "total_length": len(text_content),
                    }
            except Exception as e:
                return {
                    "status": "executed",
                    "output": f"[浏览器] 提取失败: {url} ({str(e)[:100]})",
                    "url": url,
                    "error": str(e),
                }

        elif action == "screenshot":
            return {
                "status": "executed",
                "output": "[浏览器] 截图需要Playwright集成，当前仅支持HTTP请求",
                "url": url,
                "note": "截图功能待集成",
            }

        return {
            "status": "executed",
            "output": f"[浏览器] 未知操作: {action}",
        }


class DocumentNodeHandler(NodeHandler):
    """文档处理节点 - 真实文件系统操作"""

    node_type = "document"

    async def execute(self, config: dict, context: dict) -> dict:
        action = config.get("action", "create")
        content = config.get("content", "")
        title = config.get("title", "未命名文档")
        doc_format = config.get("format", "txt")
        doc_dir = Path(os.environ.get("COMPANION_DOC_DIR", "/tmp/companion-os/docs"))

        if action == "create":
            doc_dir.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r'[^\w\-_\. ]', '', title)
            file_path = doc_dir / f"{safe_name}.{doc_format}"
            try:
                file_path.write_text(content, encoding="utf-8")
                return {
                    "status": "executed",
                    "output": f"[文档] 已创建: {file_path} ({len(content)}字符)",
                    "title": title,
                    "format": doc_format,
                    "file_path": str(file_path),
                    "size": len(content),
                }
            except Exception as e:
                return {
                    "status": "executed",
                    "output": f"[文档] 创建失败: {str(e)[:100]}",
                    "title": title,
                    "error": str(e),
                }

        elif action == "read":
            safe_name = re.sub(r'[^\w\-_\. ]', '', title)
            file_path = doc_dir / f"{safe_name}.{doc_format}"
            if file_path.exists():
                try:
                    text = file_path.read_text(encoding="utf-8")
                    return {
                        "status": "executed",
                        "output": text[:1000],
                        "title": title,
                        "format": doc_format,
                        "file_path": str(file_path),
                        "size": len(text),
                        "full_content": text,
                    }
                except Exception as e:
                    return {
                        "status": "executed",
                        "output": f"[文档] 读取失败: {str(e)[:100]}",
                        "title": title,
                        "error": str(e),
                    }
            else:
                return {
                    "status": "executed",
                    "output": f"[文档] 文件不存在: {file_path}",
                    "title": title,
                    "format": doc_format,
                }

        elif action == "edit":
            safe_name = re.sub(r'[^\w\-_\. ]', '', title)
            file_path = doc_dir / f"{safe_name}.{doc_format}"
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                return {
                    "status": "executed",
                    "output": f"[文档] 已编辑: {file_path} ({len(content)}字符)",
                    "title": title,
                    "format": doc_format,
                    "file_path": str(file_path),
                    "size": len(content),
                }
            except Exception as e:
                return {
                    "status": "executed",
                    "output": f"[文档] 编辑失败: {str(e)[:100]}",
                    "title": title,
                    "error": str(e),
                }

        elif action == "analyze":
            word_count = len(content) if content else 0
            line_count = content.count("\n") + 1 if content else 0
            char_count = len(content)
            return {
                "status": "executed",
                "output": f"[文档] 分析完成: {title}（{char_count}字符, {word_count}字, {line_count}行）",
                "title": title,
                "char_count": char_count,
                "word_count": word_count,
                "line_count": line_count,
            }

        elif action == "convert":
            target_format = config.get("target_format", "pdf")
            return {
                "status": "executed",
                "output": "[文档] 格式转换需要额外库（如pandoc），当前仅支持文本操作",
                "title": title,
                "source_format": doc_format,
                "target_format": target_format,
                "note": "格式转换功能待集成",
            }

        return {
            "status": "executed",
            "output": f"[文档] 未知操作: {action}",
        }


class DesktopNodeHandler(NodeHandler):
    """桌面自动化节点 - 真实桌面操作"""

    node_type = "desktop"

    def __init__(self):
        self._pyautogui = None
        self._has_pyautogui = False
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            self._pyautogui = pyautogui
            self._has_pyautogui = True
        except ImportError:
            pass

    async def execute(self, config: dict, context: dict) -> dict:
        action = config.get("action", "click")
        target = config.get("target", "")
        text = config.get("text", "")
        key = config.get("key", "")
        wait_time = config.get("wait_time", 1)

        if not self._has_pyautogui:
            return await self._simulate(action, target, text, key, wait_time)

        loop = asyncio.get_event_loop()

        if action == "click":
            x = config.get("x")
            y = config.get("y")
            button = config.get("button", "left")
            try:
                if x is not None and y is not None:
                    await loop.run_in_executor(None, lambda: self._pyautogui.click(x, y, button=button))
                    return {
                        "status": "executed",
                        "output": f"[桌面] 点击 ({x}, {y})",
                        "position": {"x": x, "y": y},
                    }
                else:
                    return {
                        "status": "executed",
                        "output": "[桌面] 点击需要指定x/y坐标",
                        "note": "请提供x和y参数",
                    }
            except Exception as e:
                return {
                    "status": "executed",
                    "output": f"[桌面] 点击失败: {str(e)[:100]}",
                    "error": str(e),
                }

        elif action == "type":
            if not text:
                return {
                    "status": "executed",
                    "output": "[桌面] 输入文本为空",
                }
            try:
                await loop.run_in_executor(None, lambda: self._pyautogui.write(text, interval=0.05))
                return {
                    "status": "executed",
                    "output": f"[桌面] 已输入: {text[:30]}{'...' if len(text) > 30 else ''}",
                    "text_length": len(text),
                }
            except Exception as e:
                return {
                    "status": "executed",
                    "output": f"[桌面] 输入失败: {str(e)[:100]}",
                    "error": str(e),
                }

        elif action == "press":
            if not key:
                return {
                    "status": "executed",
                    "output": "[桌面] 按键为空",
                }
            try:
                await loop.run_in_executor(None, lambda: self._pyautogui.press(key))
                return {
                    "status": "executed",
                    "output": f"[桌面] 已按键: {key}",
                }
            except Exception as e:
                return {
                    "status": "executed",
                    "output": f"[桌面] 按键失败: {str(e)[:100]}",
                    "error": str(e),
                }

        elif action == "screenshot":
            try:
                screenshot = await loop.run_in_executor(None, lambda: self._pyautogui.screenshot())
                output_path = config.get("output_path", "")
                if not output_path:
                    output_path = f"/tmp/companion-os/screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                screenshot.save(output_path)
                return {
                    "status": "executed",
                    "output": f"[桌面] 截屏已保存: {output_path}",
                    "screenshot_path": output_path,
                    "size": f"{screenshot.width}x{screenshot.height}",
                }
            except Exception as e:
                return {
                    "status": "executed",
                    "output": f"[桌面] 截屏失败: {str(e)[:100]}",
                    "error": str(e),
                }

        elif action == "move":
            x = config.get("x", 0)
            y = config.get("y", 0)
            try:
                await loop.run_in_executor(None, lambda: self._pyautogui.moveTo(x, y))
                return {
                    "status": "executed",
                    "output": f"[桌面] 鼠标移动到 ({x}, {y})",
                }
            except Exception as e:
                return {
                    "status": "executed",
                    "output": f"[桌面] 移动失败: {str(e)[:100]}",
                    "error": str(e),
                }

        elif action == "scroll":
            direction = config.get("direction", "down")
            amount = config.get("amount", 3)
            try:
                clicks = amount if direction == "down" else -amount
                await loop.run_in_executor(None, lambda: self._pyautogui.scroll(clicks))
                return {
                    "status": "executed",
                    "output": f"[桌面] 滚动: {direction} {amount}步",
                }
            except Exception as e:
                return {
                    "status": "executed",
                    "output": f"[桌面] 滚动失败: {str(e)[:100]}",
                    "error": str(e),
                }

        elif action == "open":
            return {
                "status": "executed",
                "output": "[桌面] 打开应用需要系统API集成，当前支持鼠标/键盘操作",
                "note": "打开应用功能待集成",
            }

        return {
            "status": "executed",
            "output": f"[桌面] 未知操作: {action}",
        }

    async def _simulate(self, action: str, target: str, text: str, key: str, wait_time: int) -> dict:
        """降级到模拟实现"""
        results = {
            "click": f"[桌面] 模拟点击: {target or '当前鼠标位置'}",
            "type": f"[桌面] 模拟输入: {text[:30] if text else ''}",
            "press": f"[桌面] 模拟按键: {key}",
            "screenshot": "[桌面] 模拟截屏（需安装pyautogui）",
            "move": "[桌面] 模拟移动鼠标",
            "scroll": "[桌面] 模拟滚动",
            "open": f"[桌面] 模拟打开: {target or '应用'}",
        }
        return {
            "status": "executed",
            "output": results.get(action, f"[桌面] 未知操作: {action}"),
            "simulated": True,
            "note": "安装 pyautogui 可启用真实桌面自动化: pip install pyautogui",
        }


class CronNodeHandler(NodeHandler):
    """定时触发节点"""

    node_type = "cron"

    async def execute(self, config: dict, context: dict) -> dict:
        schedule = config.get("schedule", "* * * * *")

        try:
            next_time = self._get_next_cron_time(schedule)
            return {
                "status": "executed",
                "output": f"[定时] 调度: {schedule}，下次执行: {next_time}",
                "schedule": schedule,
                "next_run": next_time,
            }
        except Exception as e:
            return {
                "status": "executed",
                "output": f"[定时] 调度: {schedule}（表达式解析失败: {e}）",
                "schedule": schedule,
                "error": str(e),
            }

    def _get_next_cron_time(self, expression: str) -> str:
        parts = expression.strip().split()
        if len(parts) != 5:
            raise ValueError(f"无效的cron表达式: {expression}，需要5个字段")

        minute_expr, hour_expr, day_expr, month_expr, week_expr = parts

        now = datetime.now()
        for days_ahead in range(366):
            for hours_ahead in range(24):
                for minutes_ahead in range(60):
                    candidate = now + timedelta(days=days_ahead, hours=hours_ahead, minutes=minutes_ahead)
                    if self._match_cron_field(candidate.minute, minute_expr, 0, 59) \
                       and self._match_cron_field(candidate.hour, hour_expr, 0, 23) \
                       and self._match_cron_field(candidate.day, day_expr, 1, 31) \
                       and self._match_cron_field(candidate.month, month_expr, 1, 12) \
                       and self._match_cron_field(candidate.weekday(), week_expr, 0, 6):
                        return candidate.strftime("%Y-%m-%d %H:%M")
        return "未找到匹配时间"

    def _match_cron_field(self, value: int, expr: str, min_val: int, max_val: int) -> bool:
        expr = expr.strip()
        if expr == "*":
            return True

        if "/" in expr:
            base, step = expr.split("/")
            step = int(step)
            if base == "*":
                return (value - min_val) % step == 0
            else:
                ranges = self._parse_cron_range(base, min_val, max_val)
                return any(v <= value <= v + step - 1 if "-" not in base else False for v in ranges) or \
                       any((value - r) % step == 0 for r in ranges)

        if "," in expr:
            return any(self._match_cron_field(value, e, min_val, max_val) for e in expr.split(","))

        if "-" in expr:
            low, high = expr.split("-")
            return int(low) <= value <= int(high)

        return int(expr) == value

    def _parse_cron_range(self, expr: str, min_val: int, max_val: int) -> list:
        if expr == "*":
            return list(range(min_val, max_val + 1))
        if "," in expr:
            result = []
            for e in expr.split(","):
                result.extend(self._parse_cron_range(e, min_val, max_val))
            return result
        if "-" in expr:
            low, high = expr.split("-")
            return list(range(int(low), int(high) + 1))
        return [int(expr)]


class A2ANodeHandler(NodeHandler):
    """A2A委派节点"""

    node_type = "a2a"

    async def execute(self, config: dict, context: dict) -> dict:
        agent = config.get("agent", "unknown")
        task = config.get("task", "")
        payload = config.get("payload", {})
        timeout = config.get("timeout", 30)

        if not task:
            previous_results = context.get("results", {})
            for _node_id, node_result in previous_results.items():
                output = node_result.get("output", "")
                if output:
                    task = output
                    break

        try:
            from agent_bridge.a2a_gateway import A2AGateway
            gateway = A2AGateway()
            result = await gateway.delegate(
                agent_id=agent,
                task=task,
                payload=payload,
                timeout=timeout,
            )
            return {
                "status": "executed",
                "output": f"[A2A] 委派给 {agent} 完成: {result.get('result', '')}",
                "agent": agent,
                "task": task,
                "delegate_result": result,
            }
        except Exception as e:
            return {
                "status": "executed",
                "output": f"[A2A] 委派给 {agent}: {task[:50] if task else ''}（A2A网关不可用，模拟返回）",
                "agent": agent,
                "task": task,
                "simulated": True,
                "error": str(e),
            }


class NodeRegistry:
    """节点注册表"""

    def __init__(self):
        self._handlers: dict[str, NodeHandler] = {}
        self._register_defaults()

    def _register_defaults(self):
        """注册默认节点处理器"""
        default_handlers = [
            LLMNodeHandler(),
            EmotionNodeHandler(),
            BrowserNodeHandler(),
            DocumentNodeHandler(),
            DesktopNodeHandler(),
            EmailNodeHandler(),
            TTSNodeHandler(),
            ConditionNodeHandler(),
            CronNodeHandler(),
            MemoryNodeHandler(),
            CodeNodeHandler(),
            A2ANodeHandler(),
        ]
        for handler in default_handlers:
            self._handlers[handler.node_type] = handler

    def register(self, handler: NodeHandler):
        """注册自定义节点处理器"""
        self._handlers[handler.node_type] = handler

    def get_handler(self, node_type: str) -> NodeHandler | None:
        """获取节点处理器"""
        return self._handlers.get(node_type)

    def list_types(self) -> list[str]:
        """列出所有已注册的节点类型"""
        return list(self._handlers.keys())

    def unregister(self, node_type: str):
        """注销节点处理器"""
        self._handlers.pop(node_type, None)

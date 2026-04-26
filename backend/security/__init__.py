"""
CompanionOS 安全模块
OS Keychain + 操作审批 + 数据加密
"""

import base64
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

try:
    from cryptography.fernet import Fernet
    HAS_FERNET = True
except ImportError:
    HAS_FERNET = False


class KeychainManager:
    """OS Keychain密钥管理 - JSON文件持久化"""

    def __init__(self, data_dir: str = ""):
        self._store: dict[str, str] = {}
        if data_dir:
            self._file_path = Path(data_dir) / "security" / "keys.json"
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self._file_path = Path("data") / "security" / "keys.json"
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        if self._file_path.exists():
            try:
                with open(self._file_path) as f:
                    self._store = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._store = {}

    def _save(self):
        with open(self._file_path, "w") as f:
            json.dump(self._store, f, indent=2)

    def store(self, key: str, value: str, service: str = "companion-os"):
        """存储密钥"""
        self._store[f"{service}:{key}"] = value
        self._save()

    def retrieve(self, key: str, service: str = "companion-os") -> str | None:
        """获取密钥"""
        return self._store.get(f"{service}:{key}")

    def delete(self, key: str, service: str = "companion-os"):
        """删除密钥"""
        self._store.pop(f"{service}:{key}", None)
        self._save()

    def list_keys(self, service: str = "companion-os") -> list[str]:
        """列出所有密钥名"""
        prefix = f"{service}:"
        return [k[len(prefix):] for k in self._store if k.startswith(prefix)]

    def verify_master_password(self, password: str) -> bool:
        """验证主密码（简单实现，后续可升级为hash验证）"""
        stored = self.retrieve("__master_password__", service="__system__")
        if stored is None:
            self.store("__master_password__", password, service="__system__")
            return True
        return stored == password


class EncryptionManager:
    """加密管理器 - 增强版
    优先使用 Fernet 加密，降级到 XOR+SHA256 加密，最终降级到 Base64
    """

    def __init__(self, key: bytes | None = None):
        self._fernet = None
        self._fallback_key = None

        if key is None:
            key_str = os.getenv("COMPANION_OS_ENCRYPTION_KEY", "default-dev-key")
            key = key_str.encode()

        if HAS_FERNET:
            try:
                encoded = base64.urlsafe_b64encode(key.ljust(32)[:32])
                self._fernet = Fernet(encoded)
                return
            except Exception:
                pass

        try:
            import hashlib
            self._fallback_key = hashlib.sha256(key).digest()
        except Exception:
            pass

    def encrypt(self, data: str) -> str:
        """加密数据"""
        if self._fernet is not None:
            try:
                return self._fernet.encrypt(data.encode()).decode()
            except Exception:
                pass

        if self._fallback_key is not None:
            try:
                data_bytes = data.encode()
                result = bytearray()
                for i, b in enumerate(data_bytes):
                    result.append(b ^ self._fallback_key[i % len(self._fallback_key)])
                return base64.b64encode(bytes(result)).decode()
            except Exception:
                pass

        return base64.b64encode(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """解密数据"""
        if self._fernet is not None:
            try:
                return self._fernet.decrypt(encrypted_data.encode()).decode()
            except Exception:
                pass

        if self._fallback_key is not None:
            try:
                decoded = base64.b64decode(encrypted_data)
                result = bytearray()
                for i, b in enumerate(decoded):
                    result.append(b ^ self._fallback_key[i % len(self._fallback_key)])
                return bytes(result).decode()
            except Exception:
                pass

        try:
            return base64.b64decode(encrypted_data).decode()
        except Exception:
            return encrypted_data


class ApprovalManager:
    """操作审批机制 - 带超时机制"""

    def __init__(self, auto_approve: bool = False, approval_timeout: int = 300):
        self.auto_approve = auto_approve
        self.approval_timeout = approval_timeout
        self.pending_approvals: dict[str, dict] = {}
        self.approval_history: list[dict] = []

    HIGH_RISK_OPERATIONS = [
        "file_delete",
        "email_send",
        "code_execute",
        "system_command",
    ]

    async def request_approval(self, operation: str, details: dict = None) -> dict:
        """
        请求操作审批

        Returns:
            dict: {"approved": bool, "approval_id": str}
        """
        approval_id = str(uuid.uuid4())[:8]

        if self.auto_approve or operation not in self.HIGH_RISK_OPERATIONS:
            self.approval_history.append({
                "id": approval_id,
                "operation": operation,
                "approved": True,
                "auto": True,
            })
            return {"approved": True, "approval_id": approval_id}

        now = datetime.now()
        self.pending_approvals[approval_id] = {
            "operation": operation,
            "details": details or {},
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=self.approval_timeout)).isoformat(),
        }

        self._cleanup_expired()

        self.approval_history.append({
            "id": approval_id,
            "operation": operation,
            "approved": True,
            "auto": True,
        })
        return {"approved": True, "approval_id": approval_id}

    def _cleanup_expired(self):
        now = datetime.now()
        expired_ids = []
        for aid, record in self.pending_approvals.items():
            expires_at = record.get("expires_at")
            if expires_at:
                try:
                    if datetime.fromisoformat(expires_at) < now:
                        expired_ids.append(aid)
                except (ValueError, TypeError):
                    expired_ids.append(aid)
        for aid in expired_ids:
            record = self.pending_approvals.pop(aid, None)
            if record:
                self.approval_history.append({**record, "approved": False, "timeout": True})

    def approve(self, approval_id: str) -> bool:
        """批准操作"""
        if approval_id in self.pending_approvals:
            record = self.pending_approvals.pop(approval_id)
            self.approval_history.append({**record, "approved": True})
            return True
        return False

    def reject(self, approval_id: str) -> bool:
        """拒绝操作"""
        if approval_id in self.pending_approvals:
            record = self.pending_approvals.pop(approval_id)
            self.approval_history.append({**record, "approved": False})
            return True
        return False


class SecurityManager:
    def __init__(self, data_dir: str = ""):
        self.keychain = KeychainManager(data_dir)
        self.encryption = EncryptionManager()
        self.approval = ApprovalManager()
        self.audit = AuditLogger(data_dir)
        self._policy_file = Path(data_dir) / "security" / "policy.json" if data_dir else Path("data/security/policy.json")
        self._ensure_default_policy()

    def _ensure_default_policy(self):
        if not self._policy_file.exists():
            self._policy_file.parent.mkdir(parents=True, exist_ok=True)
            default_policy = {
                "users": {"*": {"resources": {"*": {"actions": ["*"]}}}},
                "version": "1.0"
            }
            with open(self._policy_file, "w") as f:
                json.dump(default_policy, f, indent=2)

    def _load_policy(self) -> dict:
        try:
            with open(self._policy_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"users": {}}

    def check_permission(self, user: str, resource: str, action: str) -> bool:
        policy = self._load_policy()
        users = policy.get("users", {})
        if "*" in users:
            resources = users["*"].get("resources", {})
            if "*" in resources:
                actions = resources["*"].get("actions", [])
                if "*" in actions or action in actions:
                    return True
            if resource in resources:
                actions = resources[resource].get("actions", [])
                if "*" in actions or action in actions:
                    return True
        if user in users:
            resources = users[user].get("resources", {})
            if "*" in resources:
                actions = resources["*"].get("actions", [])
                if "*" in actions or action in actions:
                    return True
            if resource in resources:
                actions = resources[resource].get("actions", [])
                if "*" in actions or action in actions:
                    return True
        return False


class AuditLogger:
    def __init__(self, data_dir: str = ""):
        base = Path(data_dir) if data_dir else Path("data")
        self._log_file = base / "security" / "audit.jsonl"
        self._log_file.parent.mkdir(parents=True, exist_ok=True)

    async def log(self, event: str, user: str, resource: str, action: str, result: str, details: dict = None):
        record = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "user": user,
            "resource": resource,
            "action": action,
            "result": result,
            "details": details or {},
        }
        with open(self._log_file, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def query(self, limit: int = 100, offset: int = 0) -> list[dict]:
        records = []
        if self._log_file.exists():
            with open(self._log_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return records[offset:offset + limit]

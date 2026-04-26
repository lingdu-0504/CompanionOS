import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import tempfile

import pytest

from daemon import CronScheduler, FileWatcher
from memory.letta_bridge import MemoryBridge
from memory.sync import MemorySync
from security import AuditLogger, EncryptionManager
from voice.tts_edge import EdgeTTS
from workflow_engine import NodeRegistry, WorkflowEngine


class TestDaemonModule:

    @pytest.mark.asyncio
    async def test_file_watcher_start_stop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = FileWatcher(Path(tmpdir))
            assert watcher._running is False

            await watcher.start()
            assert watcher._running is True
            assert watcher._task is not None

            await watcher.stop()
            assert watcher._running is False
            assert watcher._task is None

    @pytest.mark.asyncio
    async def test_file_watcher_watch_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []
            def callback(event_type, fpath):
                events.append((event_type, fpath))

            watcher = FileWatcher(Path(tmpdir), callback=callback, poll_interval=0.1)
            await watcher.start()

            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("hello")

            await asyncio.sleep(0.3)

            await watcher.stop()

            created_events = [e for e in events if e[0] == "created"]
            assert len(created_events) >= 1
            assert str(test_file) in created_events[0][1]

    @pytest.mark.asyncio
    async def test_cron_scheduler_add_task(self):
        scheduler = CronScheduler(check_interval=0.5)
        executed = []

        async def my_task():
            executed.append("ran")

        scheduler.add_task("test_task", "* * * * *", my_task)
        assert len(scheduler.tasks) == 1
        assert scheduler.tasks[0]["name"] == "test_task"
        assert scheduler.tasks[0]["schedule"] == "* * * * *"
        assert scheduler.tasks[0]["enabled"] is True

    @pytest.mark.asyncio
    async def test_cron_scheduler_remove_task(self):
        scheduler = CronScheduler(check_interval=0.5)

        async def my_task():
            pass

        scheduler.add_task("task_a", "* * * * *", my_task)
        scheduler.add_task("task_b", "0 9 * * *", my_task)
        assert len(scheduler.tasks) == 2

        scheduler.remove_task("task_a")
        assert len(scheduler.tasks) == 1
        assert scheduler.tasks[0]["name"] == "task_b"

        scheduler.remove_task("nonexistent")
        assert len(scheduler.tasks) == 1

    @pytest.mark.asyncio
    async def test_cron_scheduler_list_tasks(self):
        scheduler = CronScheduler(check_interval=0.5)

        async def my_task():
            pass

        scheduler.add_task("task_a", "* * * * *", my_task)
        scheduler.add_task("task_b", "0 9 * * *", my_task, enabled=False)

        tasks = scheduler.list_tasks()
        assert len(tasks) == 2

        names = [t["name"] for t in tasks]
        assert "task_a" in names
        assert "task_b" in names

        task_b = [t for t in tasks if t["name"] == "task_b"][0]
        assert task_b["enabled"] is False
        assert task_b["schedule"] == "0 9 * * *"
        assert task_b["last_run"] is None


class TestMemoryModule:

    @pytest.fixture
    def memory_bridge(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = MemoryBridge(Path(tmpdir))
            yield bridge

    @pytest.mark.asyncio
    async def test_memory_bridge_store_recall(self, memory_bridge):
        result = memory_bridge.save_block("human", "测试用户信息")
        assert result["label"] == "human"
        assert result["value"] == "测试用户信息"
        assert "updated_at" in result

        recalled = memory_bridge.get_block("human")
        assert recalled["value"] == "测试用户信息"

    @pytest.mark.asyncio
    async def test_memory_bridge_list(self, memory_bridge):
        memory_bridge.save_block("human", "用户信息")
        memory_bridge.save_block("work", "工作记忆")
        memory_bridge.save_block("emotional", "情感记录")

        all_blocks = memory_bridge.get_all_blocks()
        assert len(all_blocks) == 5
        assert "human" in all_blocks
        assert "persona" in all_blocks
        assert "work" in all_blocks
        assert "emotional" in all_blocks
        assert "skills" in all_blocks
        assert all_blocks["human"]["value"] == "用户信息"
        assert all_blocks["work"]["value"] == "工作记忆"

    @pytest.mark.asyncio
    async def test_memory_sync_sync(self, memory_bridge):
        sync = MemorySync(memory_bridge)

        interaction = {
            "user_input": "帮我写一份周报",
            "intent": "work",
            "response": "好的，我来帮你写周报",
            "emotion": "neutral",
        }
        await sync.sync_interaction(interaction)

        work_block = memory_bridge.get_block("work")
        assert "周报" in work_block["value"]

        emotional_block = memory_bridge.get_block("emotional")
        assert emotional_block["value"] == ""


class TestWorkflowEngine:

    @pytest.fixture
    def engine(self):
        return WorkflowEngine(NodeRegistry())

    def test_dag_topological_sort(self, engine):
        workflow = {
            "nodes": [
                {"id": "n1", "type": "hermesLLM", "label": "LLM", "config": {}},
                {"id": "n2", "type": "emotion", "label": "情感", "config": {}},
                {"id": "n3", "type": "tts", "label": "TTS", "config": {}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
                {"id": "e2", "source": "n2", "target": "n3"},
            ],
        }

        dag = engine.parse_dag(workflow)
        assert len(dag["layers"]) == 3
        assert dag["layers"][0] == ["n1"]
        assert dag["layers"][1] == ["n2"]
        assert dag["layers"][2] == ["n3"]

    def test_dag_cycle_detection(self, engine):
        workflow = {
            "nodes": [
                {"id": "n1", "type": "hermesLLM", "label": "LLM", "config": {}},
                {"id": "n2", "type": "emotion", "label": "情感", "config": {}},
                {"id": "n3", "type": "tts", "label": "TTS", "config": {}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
                {"id": "e2", "source": "n2", "target": "n3"},
                {"id": "e3", "source": "n3", "target": "n1"},
            ],
        }

        with pytest.raises(ValueError, match="循环依赖"):
            engine.parse_dag(workflow)

    def test_dag_single_node(self, engine):
        workflow = {
            "nodes": [
                {"id": "n1", "type": "hermesLLM", "label": "LLM", "config": {}},
            ],
            "edges": [],
        }

        dag = engine.parse_dag(workflow)
        assert len(dag["layers"]) == 1
        assert dag["layers"][0] == ["n1"]
        assert len(dag["nodes"]) == 1

    def test_dag_disconnected_nodes(self, engine):
        workflow = {
            "nodes": [
                {"id": "n1", "type": "hermesLLM", "label": "LLM", "config": {}},
                {"id": "n2", "type": "emotion", "label": "情感", "config": {}},
                {"id": "n3", "type": "tts", "label": "TTS", "config": {}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
            ],
        }

        dag = engine.parse_dag(workflow)
        assert len(dag["layers"]) == 2
        assert "n3" in dag["layers"][0] or "n3" in dag["layers"][1]
        assert dag["layers"][0] == sorted(dag["layers"][0])

    @pytest.mark.asyncio
    async def test_workflow_execute_simple(self, engine):
        workflow = {
            "nodes": [
                {"id": "n1", "type": "hermesLLM", "label": "LLM", "config": {"prompt": "测试"}},
                {"id": "n2", "type": "emotion", "label": "情感", "config": {}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
            ],
        }

        result = await engine.execute(workflow, inputs={"user": "test"})
        assert result["status"] == "completed"
        assert "results" in result
        assert "n1" in result["results"]
        assert "n2" in result["results"]
        assert "duration_ms" in result
        assert "started_at" in result
        assert "completed_at" in result


class TestSecurityModule:

    @pytest.fixture
    def encryption_manager(self):
        return EncryptionManager(key=b"test-key-32-bytes-for-fernet!!!")

    @pytest.fixture
    def audit_logger(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield AuditLogger(data_dir=tmpdir)

    def test_encryption_encrypt_decrypt(self, encryption_manager):
        original = "Hello, CompanionOS! 你好，伴侣系统！"
        encrypted = encryption_manager.encrypt(original)
        assert encrypted != original

        decrypted = encryption_manager.decrypt(encrypted)
        assert decrypted == original

    def test_encryption_different_keys(self):
        mgr1 = EncryptionManager(key=b"key-one-32-bytes-for-fernet!!!!")
        mgr2 = EncryptionManager(key=b"key-two-32-bytes-for-fernet!!!!")

        original = "Sensitive data"
        encrypted1 = mgr1.encrypt(original)
        encrypted2 = mgr2.encrypt(original)

        assert encrypted1 != encrypted2

        decrypted1 = mgr1.decrypt(encrypted1)
        assert decrypted1 == original

    @pytest.mark.asyncio
    async def test_audit_logger_log(self, audit_logger):
        await audit_logger.log(
            event="user_login",
            user="test_user",
            resource="system",
            action="login",
            result="success",
            details={"ip": "127.0.0.1"},
        )

        records = audit_logger.query()
        assert len(records) == 1
        assert records[0]["event"] == "user_login"
        assert records[0]["user"] == "test_user"
        assert records[0]["action"] == "login"
        assert records[0]["result"] == "success"
        assert records[0]["details"]["ip"] == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_audit_logger_query(self, audit_logger):
        for i in range(5):
            await audit_logger.log(
                event=f"event_{i}",
                user="test_user",
                resource="system",
                action="test",
                result="success",
            )

        all_records = audit_logger.query()
        assert len(all_records) == 5

        limited = audit_logger.query(limit=2)
        assert len(limited) == 2

        with_offset = audit_logger.query(limit=10, offset=2)
        assert len(with_offset) == 3


class TestVoiceModule:

    def test_edge_tts_voices(self):
        assert len(EdgeTTS.VOICES) >= 4
        assert "xiaoxiao" in EdgeTTS.VOICES
        assert "xiaoyi" in EdgeTTS.VOICES
        assert "yunjian" in EdgeTTS.VOICES
        assert "yunxi" in EdgeTTS.VOICES
        assert EdgeTTS.VOICES["xiaoxiao"] == "zh-CN-XiaoxiaoNeural"

    @pytest.mark.asyncio
    async def test_edge_tts_synthesize(self):
        tts = EdgeTTS()
        result = await tts.synthesize("你好，测试语音合成")

        assert "engine" in result
        assert result["engine"] == "edge-tts"
        assert result["status"] in ("completed", "not_installed", "error")

        if result["status"] == "completed":
            assert result["audio_path"] is not None
            assert Path(result["audio_path"]).exists()
        elif result["status"] == "not_installed":
            assert "text" in result
            assert result["text"] == "你好，测试语音合成"

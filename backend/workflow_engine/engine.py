"""
CompanionOS 工作流执行引擎
DAG解析 + 拓扑排序 + 并行执行
"""

import asyncio
from datetime import datetime

from workflow_engine.node_registry import NodeRegistry


class WorkflowEngine:
    """工作流执行引擎"""

    def __init__(self, node_registry: NodeRegistry | None = None):
        self.registry = node_registry or NodeRegistry()

    def parse_dag(self, workflow_data: dict) -> dict:
        """
        解析工作流JSON为DAG结构

        Returns:
            dict: {
                "nodes": dict[str, dict],
                "edges": list[dict],
                "layers": list[list[str]],  # 拓扑分层
            }
        """
        nodes = {n["id"]: n for n in workflow_data.get("nodes", [])}
        edges = workflow_data.get("edges", [])

        # 构建邻接表
        in_degree = {nid: 0 for nid in nodes}
        adjacency = {nid: [] for nid in nodes}

        for edge in edges:
            source = edge["source"]
            target = edge["target"]
            if source in adjacency and target in in_degree:
                adjacency[source].append(target)
                in_degree[target] += 1

        # 拓扑排序（Kahn算法）
        layers = []
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        visited = set()

        while queue:
            layer = sorted(queue)  # 同层节点排序保证确定性
            layers.append(layer)
            visited.update(layer)
            next_queue = []
            for nid in layer:
                for neighbor in adjacency[nid]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0 and neighbor not in visited:
                        next_queue.append(neighbor)
            queue = next_queue

        # 检测循环
        if len(visited) != len(nodes):
            raise ValueError("工作流存在循环依赖")

        return {
            "nodes": nodes,
            "edges": edges,
            "layers": layers,
        }

    async def execute(self, workflow_data: dict, inputs: dict = None) -> dict:
        """
        执行工作流

        Args:
            workflow_data: 工作流JSON配置
            inputs: 输入参数

        Returns:
            dict: 执行结果
        """
        inputs = inputs or {}
        start_time = datetime.now()

        dag = self.parse_dag(workflow_data)
        context = {"inputs": inputs, "results": {}}

        try:
            for layer in dag["layers"]:
                # 同层节点并行执行
                tasks = []
                for nid in layer:
                    node = dag["nodes"][nid]
                    tasks.append(self._execute_node(node, context))

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for nid, result in zip(layer, results, strict=False):
                    if isinstance(result, Exception):
                        context["results"][nid] = {
                            "status": "error",
                            "error": str(result),
                            "node_id": nid,
                        }
                    else:
                        context["results"][nid] = result

            end_time = datetime.now()
            return {
                "status": "completed",
                "results": context["results"],
                "started_at": start_time.isoformat(),
                "completed_at": end_time.isoformat(),
                "duration_ms": int((end_time - start_time).total_seconds() * 1000),
            }

        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "results": context["results"],
                "started_at": start_time.isoformat(),
            }

    async def _execute_node(self, node: dict, context: dict) -> dict:
        """执行单个节点"""
        node_type = node.get("type", "unknown")
        node_config = node.get("config", {})

        handler = self.registry.get_handler(node_type)
        if handler:
            result = await handler.execute(node_config, context)
        else:
            # 未注册的节点类型，返回占位结果
            result = {
                "status": "executed",
                "output": f"[{node_type}] 节点已执行（占位）",
                "node_id": node["id"],
            }

        result["node_id"] = node["id"]
        result["node_type"] = node_type
        return result

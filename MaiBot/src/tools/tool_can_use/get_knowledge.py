from src.tools.tool_can_use.base_tool import BaseTool
from src.chat.utils.utils import get_embedding
from src.common.database.database_model import Knowledges  # Updated import
from src.common.logger_manager import get_logger
from typing import Any, Union, List  # Added List
import json  # Added for parsing embedding
import math  # Added for cosine similarity

logger = get_logger("get_knowledge_tool")


class SearchKnowledgeTool(BaseTool):
    """从知识库中搜索相关信息的工具"""

    name = "search_knowledge"
    description = "使用工具从知识库中搜索相关信息"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索查询关键词"},
            "threshold": {"type": "number", "description": "相似度阈值，0.0到1.0之间"},
        },
        "required": ["query"],
    }

    async def execute(self, function_args: dict[str, Any]) -> dict[str, Any]:
        """执行知识库搜索

        Args:
            function_args: 工具参数

        Returns:
            dict: 工具执行结果
        """
        query = ""  # Initialize query to ensure it's defined in except block
        try:
            query = function_args.get("query")
            threshold = function_args.get("threshold", 0.4)

            # 调用知识库搜索
            embedding = await get_embedding(query, request_type="info_retrieval")
            if embedding:
                knowledge_info = self.get_info_from_db(embedding, limit=3, threshold=threshold)
                if knowledge_info:
                    content = f"你知道这些知识: {knowledge_info}"
                else:
                    content = f"你不太了解有关{query}的知识"
                return {"type": "knowledge", "id": query, "content": content}
            return {"type": "info", "id": query, "content": f"无法获取关于'{query}'的嵌入向量，你知识库炸了"}
        except Exception as e:
            logger.error(f"知识库搜索工具执行失败: {str(e)}")
            return {"type": "info", "id": query, "content": f"知识库搜索失败，炸了: {str(e)}"}

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量之间的余弦相似度"""
        dot_product = sum(p * q for p, q in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(p * p for p in vec1))
        magnitude2 = math.sqrt(sum(q * q for q in vec2))
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)

    @staticmethod
    def get_info_from_db(
        query_embedding: list[float], limit: int = 1, threshold: float = 0.5, return_raw: bool = False
    ) -> Union[str, list]:
        """从数据库中获取相关信息

        Args:
            query_embedding: 查询的嵌入向量
            limit: 最大返回结果数
            threshold: 相似度阈值
            return_raw: 是否返回原始结果

        Returns:
            Union[str, list]: 格式化的信息字符串或原始结果列表
        """
        if not query_embedding:
            return "" if not return_raw else []

        similar_items = []
        try:
            all_knowledges = Knowledges.select()
            for item in all_knowledges:
                try:
                    item_embedding_str = item.embedding
                    if not item_embedding_str:
                        logger.warning(f"Knowledge item ID {item.id} has empty embedding string.")
                        continue
                    item_embedding = json.loads(item_embedding_str)
                    if not isinstance(item_embedding, list) or not all(
                        isinstance(x, (int, float)) for x in item_embedding
                    ):
                        logger.warning(f"Knowledge item ID {item.id} has invalid embedding format after JSON parsing.")
                        continue
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse embedding for knowledge item ID {item.id}")
                    continue
                except AttributeError:
                    logger.warning(f"Knowledge item ID {item.id} missing 'embedding' attribute or it's not a string.")
                    continue

                similarity = SearchKnowledgeTool._cosine_similarity(query_embedding, item_embedding)

                if similarity >= threshold:
                    similar_items.append({"content": item.content, "similarity": similarity, "raw_item": item})

            # 按相似度降序排序
            similar_items.sort(key=lambda x: x["similarity"], reverse=True)

            # 应用限制
            results = similar_items[:limit]
            logger.debug(f"知识库查询后，符合条件的结果数量: {len(results)}")

        except Exception as e:
            logger.error(f"从 Peewee 数据库获取知识信息失败: {str(e)}")
            return "" if not return_raw else []

        if not results:
            return "" if not return_raw else []

        if return_raw:
            # Peewee 模型实例不能直接序列化为 JSON，如果需要原始模型，调用者需要处理
            # 这里返回包含内容和相似度的字典列表
            return [{"content": r["content"], "similarity": r["similarity"]} for r in results]
        else:
            # 返回所有找到的内容，用换行分隔
            return "\n".join(str(result["content"]) for result in results)


# 注册工具
# register_tool(SearchKnowledgeTool)

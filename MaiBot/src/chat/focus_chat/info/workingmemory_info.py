from typing import Dict, Optional, List
from dataclasses import dataclass
from .info_base import InfoBase


@dataclass
class WorkingMemoryInfo(InfoBase):
    type: str = "workingmemory"

    processed_info: str = ""

    def set_talking_message(self, message: str) -> None:
        """设置说话消息

        Args:
            message (str): 说话消息内容
        """
        self.data["talking_message"] = message

    def set_working_memory(self, working_memory: List[str]) -> None:
        """设置工作记忆

        Args:
            working_memory (str): 工作记忆内容
        """
        self.data["working_memory"] = working_memory

    def add_working_memory(self, working_memory: str) -> None:
        """添加工作记忆

        Args:
            working_memory (str): 工作记忆内容
        """
        working_memory_list = self.data.get("working_memory", [])
        # print(f"working_memory_list: {working_memory_list}")
        working_memory_list.append(working_memory)
        # print(f"working_memory_list: {working_memory_list}")
        self.data["working_memory"] = working_memory_list

    def get_working_memory(self) -> List[str]:
        """获取工作记忆

        Returns:
            List[str]: 工作记忆内容
        """
        return self.data.get("working_memory", [])

    def get_type(self) -> str:
        """获取信息类型

        Returns:
            str: 当前信息对象的类型标识符
        """
        return self.type

    def get_data(self) -> Dict[str, str]:
        """获取所有信息数据

        Returns:
            Dict[str, str]: 包含所有信息数据的字典
        """
        return self.data

    def get_info(self, key: str) -> Optional[str]:
        """获取特定属性的信息

        Args:
            key: 要获取的属性键名

        Returns:
            Optional[str]: 属性值，如果键不存在则返回 None
        """
        return self.data.get(key)

    def get_processed_info(self) -> Dict[str, str]:
        """获取处理后的信息

        Returns:
            Dict[str, str]: 处理后的信息数据
        """
        all_memory = self.get_working_memory()
        # print(f"all_memory: {all_memory}")
        memory_str = ""
        for memory in all_memory:
            memory_str += f"{memory}\n"

        self.processed_info = memory_str

        return self.processed_info

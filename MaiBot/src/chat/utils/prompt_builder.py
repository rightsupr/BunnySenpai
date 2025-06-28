from typing import Dict, Any, Optional, List, Union
import re
from contextlib import asynccontextmanager
import asyncio
import contextvars
from src.common.logger import get_module_logger

# import traceback
from rich.traceback import install

install(extra_lines=3)

logger = get_module_logger("prompt_build")


class PromptContext:
    def __init__(self):
        self._context_prompts: Dict[str, Dict[str, "Prompt"]] = {}
        # 使用contextvars创建协程上下文变量
        self._current_context_var = contextvars.ContextVar("current_context", default=None)
        self._context_lock = asyncio.Lock()  # 保留锁用于其他操作

    @property
    def _current_context(self) -> Optional[str]:
        """获取当前协程的上下文ID"""
        return self._current_context_var.get()

    @_current_context.setter
    def _current_context(self, value: Optional[str]):
        """设置当前协程的上下文ID"""
        self._current_context_var.set(value)

    @asynccontextmanager
    async def async_scope(self, context_id: Optional[str] = None):
        """创建一个异步的临时提示模板作用域"""
        # 保存当前上下文并设置新上下文
        if context_id is not None:
            async with self._context_lock:
                if context_id not in self._context_prompts:
                    self._context_prompts[context_id] = {}

            # 保存当前协程的上下文值，不影响其他协程
            previous_context = self._current_context
            # 设置当前协程的新上下文
            token = self._current_context_var.set(context_id)
        else:
            # 如果没有提供新上下文，保持当前上下文不变
            previous_context = self._current_context
            token = None

        try:
            yield self
        finally:
            # 恢复之前的上下文
            if context_id is not None:
                if token:
                    self._current_context_var.reset(token)
                else:
                    self._current_context = previous_context

    async def get_prompt_async(self, name: str) -> Optional["Prompt"]:
        """异步获取当前作用域中的提示模板"""
        async with self._context_lock:
            current_context = self._current_context
            logger.debug(f"获取提示词: {name} 当前上下文: {current_context}")
            if (
                current_context
                and current_context in self._context_prompts
                and name in self._context_prompts[current_context]
            ):
                return self._context_prompts[current_context][name]
            return None

    async def register_async(self, prompt: "Prompt", context_id: Optional[str] = None) -> None:
        """异步注册提示模板到指定作用域"""
        async with self._context_lock:
            target_context = context_id or self._current_context
            if target_context:
                self._context_prompts.setdefault(target_context, {})[prompt.name] = prompt


class PromptManager:
    def __init__(self):
        self._prompts = {}
        self._counter = 0
        self._context = PromptContext()
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def async_message_scope(self, message_id: Optional[str] = None):
        """为消息处理创建异步临时作用域，支持 message_id 为 None 的情况"""
        async with self._context.async_scope(message_id):
            yield self

    async def get_prompt_async(self, name: str) -> "Prompt":
        # 首先尝试从当前上下文获取
        context_prompt = await self._context.get_prompt_async(name)
        if context_prompt is not None:
            logger.debug(f"从上下文中获取提示词: {name} {context_prompt}")
            return context_prompt
        # 如果上下文中不存在，则使用全局提示模板
        async with self._lock:
            logger.debug(f"从全局获取提示词: {name}")
            if name not in self._prompts:
                raise KeyError(f"Prompt '{name}' not found")
            return self._prompts[name]

    def generate_name(self, template: str) -> str:
        """为未命名的prompt生成名称"""
        self._counter += 1
        return f"prompt_{self._counter}"

    def register(self, prompt: "Prompt") -> None:
        """注册一个prompt"""
        if not prompt.name:
            prompt.name = self.generate_name(prompt.template)
        self._prompts[prompt.name] = prompt

    def add_prompt(self, name: str, fstr: str) -> "Prompt":
        prompt = Prompt(fstr, name=name)
        self._prompts[prompt.name] = prompt
        return prompt

    async def format_prompt(self, name: str, **kwargs) -> str:
        prompt = await self.get_prompt_async(name)
        return prompt.format(**kwargs)


# 全局单例
global_prompt_manager = PromptManager()


class Prompt(str):
    # 临时标记，作为类常量
    _TEMP_LEFT_BRACE = "__ESCAPED_LEFT_BRACE__"
    _TEMP_RIGHT_BRACE = "__ESCAPED_RIGHT_BRACE__"

    @staticmethod
    def _process_escaped_braces(template: str) -> str:
        """处理模板中的转义花括号，将 \{ 和 \} 替换为临时标记"""
        return template.replace("\\{", Prompt._TEMP_LEFT_BRACE).replace("\\}", Prompt._TEMP_RIGHT_BRACE)

    @staticmethod
    def _restore_escaped_braces(template: str) -> str:
        """将临时标记还原为实际的花括号字符"""
        return template.replace(Prompt._TEMP_LEFT_BRACE, "{").replace(Prompt._TEMP_RIGHT_BRACE, "}")

    def __new__(cls, fstr: str, name: Optional[str] = None, args: Union[List[Any], tuple[Any, ...]] = None, **kwargs):
        # 如果传入的是元组，转换为列表
        if isinstance(args, tuple):
            args = list(args)
        should_register = kwargs.pop("_should_register", True)

        # 预处理模板中的转义花括号
        processed_fstr = cls._process_escaped_braces(fstr)

        # 解析模板
        template_args = []
        result = re.findall(r"\{(.*?)}", processed_fstr)
        for expr in result:
            if expr and expr not in template_args:
                template_args.append(expr)

        # 如果提供了初始参数，立即格式化
        if kwargs or args:
            formatted = cls._format_template(fstr, args=args, kwargs=kwargs)
            obj = super().__new__(cls, formatted)
        else:
            obj = super().__new__(cls, "")

        obj.template = fstr
        obj.name = name
        obj.args = template_args
        obj._args = args or []
        obj._kwargs = kwargs

        # 修改自动注册逻辑
        if should_register:
            if global_prompt_manager._context._current_context:
                # 如果存在当前上下文，则注册到上下文中
                # asyncio.create_task(global_prompt_manager._context.register_async(obj))
                pass
            else:
                # 否则注册到全局管理器
                global_prompt_manager.register(obj)
        return obj

    @classmethod
    async def create_async(
        cls, fstr: str, name: Optional[str] = None, args: Union[List[Any], tuple[Any, ...]] = None, **kwargs
    ):
        """异步创建Prompt实例"""
        prompt = cls(fstr, name, args, **kwargs)
        if global_prompt_manager._context._current_context:
            await global_prompt_manager._context.register_async(prompt)
        return prompt

    @classmethod
    def _format_template(cls, template: str, args: List[Any] = None, kwargs: Dict[str, Any] = None) -> str:
        # 预处理模板中的转义花括号
        processed_template = cls._process_escaped_braces(template)

        template_args = []
        result = re.findall(r"\{(.*?)}", processed_template)
        for expr in result:
            if expr and expr not in template_args:
                template_args.append(expr)
        formatted_args = {}
        formatted_kwargs = {}

        # 处理位置参数
        if args:
            # print(len(template_args), len(args), template_args, args)
            for i in range(len(args)):
                if i < len(template_args):
                    arg = args[i]
                    if isinstance(arg, Prompt):
                        formatted_args[template_args[i]] = arg.format(**kwargs)
                    else:
                        formatted_args[template_args[i]] = arg
                else:
                    logger.error(
                        f"构建提示词模板失败，解析到的参数列表{template_args}，长度为{len(template_args)}，输入的参数列表为{args}，提示词模板为{template}"
                    )
                    raise ValueError("格式化模板失败")

        # 处理关键字参数
        if kwargs:
            for key, value in kwargs.items():
                if isinstance(value, Prompt):
                    remaining_kwargs = {k: v for k, v in kwargs.items() if k != key}
                    formatted_kwargs[key] = value.format(**remaining_kwargs)
                else:
                    formatted_kwargs[key] = value

        try:
            # 先用位置参数格式化
            if args:
                processed_template = processed_template.format(**formatted_args)
            # 再用关键字参数格式化
            if kwargs:
                processed_template = processed_template.format(**formatted_kwargs)

            # 将临时标记还原为实际的花括号
            result = cls._restore_escaped_braces(processed_template)
            return result
        except (IndexError, KeyError) as e:
            raise ValueError(
                f"格式化模板失败: {template}, args={formatted_args}, kwargs={formatted_kwargs} {str(e)}"
            ) from e

    def format(self, *args, **kwargs) -> "str":
        """支持位置参数和关键字参数的格式化，使用"""
        ret = type(self)(
            self.template,
            self.name,
            args=list(args) if args else self._args,
            _should_register=False,
            **kwargs if kwargs else self._kwargs,
        )
        # print(f"prompt build result: {ret} name: {ret.name} ")
        return str(ret)

    def __str__(self) -> str:
        if self._kwargs or self._args:
            return super().__str__()
        return self.template

    def __repr__(self) -> str:
        return f"Prompt(template='{self.template}', name='{self.name}')"

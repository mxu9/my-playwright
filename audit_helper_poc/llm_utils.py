"""
LLM 工具模块：封装 langchain_openai 调用和 Token 使用跟踪
"""
import json
import logging
import re
from typing import List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


class TokenUsageTracker:
    """Token 使用跟踪器"""

    def __init__(self):
        self.calls: List[dict] = []  # 每次 LLM 调用的统计
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0

    def add_call(self, call_name: str, response) -> dict:
        """
        记录一次 LLM 调用的 token 使用。

        Args:
            call_name: 调用名称（用于标识）
            response: LLM 响应对象

        Returns:
            本次调用的 token 使用信息
        """
        # 初始化默认值
        token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

        if hasattr(response, 'response_metadata') and response.response_metadata:
            usage = response.response_metadata.get('token_usage', {})
            token_usage = {
                "prompt_tokens": usage.get('prompt_tokens', 0),
                "completion_tokens": usage.get('completion_tokens', 0),
                "total_tokens": usage.get('total_tokens', 0)
            }

        # 累加到总计
        self.total_prompt_tokens += token_usage["prompt_tokens"]
        self.total_completion_tokens += token_usage["completion_tokens"]
        self.total_tokens += token_usage["total_tokens"]

        call_info = {
            "call_name": call_name,
            "token_usage": token_usage
        }
        self.calls.append(call_info)
        return call_info

    def get_summary(self) -> dict:
        """获取 token 使用汇总"""
        return {
            "total_calls": len(self.calls),
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "calls_detail": self.calls
        }

    def reset(self):
        """重置统计"""
        self.calls = []
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0


class LLMClient:
    """LLM 客户端封装"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float = 0.1
    ):
        """
        初始化 LLM 客户端。

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model_name: 模型名称
            temperature: 温度参数，默认 0.1

        Raises:
            ValueError: 配置无效
        """
        if not api_key:
            raise ValueError("API_KEY 不能为空")

        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

        # 初始化 langchain 客户端
        self.client = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=temperature
        )

        # 初始化 token 使用跟踪器
        self.token_tracker = TokenUsageTracker()

    def invoke(
        self,
        system_prompt: str,
        user_content: str | list[dict],
        call_name: str = "llm_call"
    ) -> tuple[str, dict]:
        """
        调用 LLM。

        Args:
            system_prompt: 系统提示
            user_content: 用户内容（字符串或多模态内容列表）
            call_name: 调用名称（用于 token 统计）

        Returns:
            (响应内容, token使用信息)
        """
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]

        try:
            response = self.client.invoke(messages)
        except Exception as e:
            logging.error(f"LLM API 调用失败: {e}")
            raise

        # 记录 token 使用
        call_info = self.token_tracker.add_call(call_name, response)

        return response.content, call_info['token_usage']

    def invoke_with_json_response(
        self,
        system_prompt: str,
        user_content: str | list[dict],
        call_name: str = "llm_call"
    ) -> tuple[dict | None, dict]:
        """
        调用 LLM 并解析 JSON 响应。

        Args:
            system_prompt: 系统提示
            user_content: 用户内容
            call_name: 调用名称

        Returns:
            (解析后的JSON对象, token使用信息)
        """
        response_text, token_usage = self.invoke(
            system_prompt, user_content, call_name
        )

        # 尝试解析 JSON
        try:
            result = json.loads(response_text)
            return result, token_usage
        except json.JSONDecodeError:
            # 尝试提取 JSON（使用非贪婪匹配）
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return result, token_usage
                except json.JSONDecodeError:
                    logging.warning(f"无法解析提取的 JSON: {json_match.group()[:100]}")
            # 解析失败
            logging.warning(f"无法解析 LLM 响应: {response_text[:100]}...")
            return None, token_usage

    def get_token_summary(self) -> dict:
        """获取 token 使用汇总"""
        return self.token_tracker.get_summary()

    def reset_token_tracker(self):
        """重置 token 统计"""
        self.token_tracker.reset()


def build_multimodal_content(images: list[str], text: str) -> list[dict]:
    """
    构建多模态内容列表。

    Args:
        images: base64 编码的图片列表
        text: 文本提示

    Returns:
        多模态内容列表
    """
    content = []
    for img_base64 in images:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{img_base64}"
            }
        })
    if text:
        content.append({
            "type": "text",
            "text": text
        })
    return content
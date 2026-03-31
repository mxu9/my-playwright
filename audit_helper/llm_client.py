"""
LLM 客户端模块：封装 langchain_openai 调用
"""
import json
import logging
import re
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


# PDF 类别枚举
PDF_CATEGORIES = [
    "房租合同",
    "增值税纳税申报表",
    "企业所得税纳税申报表",
    "财务报表",
    "天眼查信息",
    "银行询证函",
    "银行明细对账单",
    "银行余额对账单",
    "其他",
]


class TokenUsageTracker:
    """Token 使用跟踪器"""

    def __init__(self):
        self.calls: List[dict] = []  # 每次 LLM 调用的统计
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0

    def add_call(self, call_name: str, response) -> dict:
        """
        记录一次 LLM 调用的 token 使用

        Args:
            call_name: 调用名称（用于标识）
            response: LLM 响应对象

        Returns:
            本次调用的 token 使用信息
        """
        # 从 response_metadata 中提取 token 使用信息
        token_usage = {}
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
    """LLM 客户端：调用大模型进行 PDF 分类"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str
    ):
        """
        初始化 LLM 客户端

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model_name: 模型名称

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
            temperature=0.1  # 低温度，更稳定的输出
        )

        # 初始化 token 使用跟踪器
        self.token_tracker = TokenUsageTracker()

    def classify(self, content: str | list[str], pdf_type: str) -> dict:
        """
        分类 PDF 内容

        Args:
            content: 文本内容（原生PDF）或 base64 图片列表（扫描件）
            pdf_type: "native" 或 "scanned"

        Returns:
            {"category": str, "confidence": float, "token_usage": dict}
        """
        system_prompt = self._build_system_prompt()

        if pdf_type == "native":
            # 文本分类
            user_message = HumanMessage(
                content=f"请分析以下 PDF 文档内容并分类：\n\n{content}"
            )
        else:
            # 多模态图片分类
            images_content = []
            for img_base64 in content:
                images_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}"
                    }
                })
            # 添加文字提示
            images_content.append({
                "type": "text",
                "text": "请分析以上 PDF 文档图片并分类。"
            })
            user_message = HumanMessage(content=images_content)

        messages = [
            SystemMessage(content=system_prompt),
            user_message
        ]

        try:
            response = self.client.invoke(messages)
        except Exception as e:
            logging.error(f"LLM API 调用失败: {e}")
            return {"category": "其他", "confidence": 0.0, "token_usage": {}}

        # 记录 token 使用
        call_info = self.token_tracker.add_call(f"classify_{pdf_type}", response)
        call_token_usage = call_info['token_usage']

        # 解析响应
        result = self._parse_response(response.content)
        result["token_usage"] = call_token_usage
        return result

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        categories_str = ", ".join(PDF_CATEGORIES)
        return f"""你是一个审计文档分类助手。请根据文档内容判断其类型。

可选的文档类型：
{categories_str}

请返回 JSON 格式的结果：
{{"category": "文档类型", "confidence": 0.0-1.0}}

注意：
1. category 必须是上述类型之一
2. confidence 是置信度，范围 0.0 到 1.0
3. 只返回 JSON，不要其他内容"""

    def _parse_response(self, response_text: str) -> dict:
        """解析 LLM 响应"""
        try:
            # 尝试直接解析 JSON
            result = json.loads(response_text)
            return self._validate_result(result)
        except json.JSONDecodeError:
            # 尝试提取 JSON（使用非贪婪匹配）
            json_match = re.search(r'\{[^{}]*\}', response_text)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return self._validate_result(result)
                except json.JSONDecodeError:
                    logging.warning(f"无法解析提取的 JSON: {json_match.group()[:100]}")
            # 解析失败，记录日志并返回默认值
            logging.warning(f"无法解析 LLM 响应: {response_text[:100]}...")
            return {"category": "其他", "confidence": 0.0}

    def _validate_result(self, result: dict) -> dict:
        """验证并规范化结果"""
        category = result.get("category", "其他")
        # 验证 category 是否在有效列表中
        if category not in PDF_CATEGORIES:
            category = "其他"
        validated = {
            "category": category,
            "confidence": float(result.get("confidence", 0.5))
        }
        # 保留 token_usage（如果存在）
        if "token_usage" in result:
            validated["token_usage"] = result["token_usage"]
        return validated

    def get_token_summary(self) -> dict:
        """获取 token 使用汇总"""
        return self.token_tracker.get_summary()

    def reset_token_tracker(self):
        """重置 token 统计"""
        self.token_tracker.reset()
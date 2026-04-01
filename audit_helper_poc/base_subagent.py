# audit_helper_poc/base_subagent.py
from abc import ABC, abstractmethod


class BaseSubagent(ABC):
    """PDF 处理子代理的抽象基类"""

    @property
    @abstractmethod
    def category(self) -> str:
        """
        返回该 subagent 处理的 PDF 类别名称。

        Returns:
            str: 类别名称，如 "房租合同"、"银行明细对账单" 等
        """
        pass

    @abstractmethod
    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        """
        处理 PDF 文件并提取结构化信息。

        Args:
            pdf_path: PDF 文件的绝对路径
            pdf_type: PDF 类型 ("native" 或 "scanned")
            config: 配置字典 (API_KEY, BASE_URL, MODEL_NAME)

        Returns:
            dict: {
                "success": bool,
                "data": dict | None,
                "error": str | None,
                "model": str,
                "token_usage": {
                    "prompt_tokens": int,
                    "completion_tokens": int,
                    "total_tokens": int
                }
            }
        """
        pass
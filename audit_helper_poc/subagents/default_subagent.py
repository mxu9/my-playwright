# audit_helper_poc/subagents/default_subagent.py
from ..base_subagent import BaseSubagent


class DefaultSubagent(BaseSubagent):
    """兜底处理子代理，处理"其他"类别"""

    @property
    def category(self) -> str:
        return "其他"

    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        return {
            "success": False,
            "data": None,
            "error": "无对应的处理 subagent",
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
# audit_helper_poc/subagents/tianyancha_subagent.py
from ..base_subagent import BaseSubagent


class TianyanchaSubagent(BaseSubagent):
    """天眼查信息处理子代理"""

    @property
    def category(self) -> str:
        return "天眼查信息"

    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        # 当前阶段：返回模拟数据，不实际调用 LLM
        return {
            "success": True,
            "data": {
                "company_name": "公司名称",
                "registration_date": "2020-01-01",
                "legal_representative": "法定代表人",
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 150,
                "total_tokens": 1150
            }
        }
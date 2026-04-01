# audit_helper_poc/subagents/bank_confirmation_subagent.py
from ..base_subagent import BaseSubagent


class BankConfirmationSubagent(BaseSubagent):
    """银行询证函处理子代理"""

    @property
    def category(self) -> str:
        return "银行询证函"

    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        # 当前阶段：返回模拟数据，不实际调用 LLM
        return {
            "success": True,
            "data": {
                "bank_name": "银行名称",
                "account_number": "账号",
                "balance": 100000.00,
                "confirmation_date": "2024-12-31",
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {
                "prompt_tokens": 1100,
                "completion_tokens": 180,
                "total_tokens": 1280
            }
        }
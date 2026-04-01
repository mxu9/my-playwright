# audit_helper_poc/subagents/bank_balance_subagent.py
from ..base_subagent import BaseSubagent


class BankBalanceSubagent(BaseSubagent):
    """银行余额对账单处理子代理"""

    @property
    def category(self) -> str:
        return "银行余额对账单"

    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        # 当前阶段：返回模拟数据，不实际调用 LLM
        return {
            "success": True,
            "data": {
                "bank_name": "银行名称",
                "account_number": "账号",
                "balance_date": "2024-12-31",
                "balance": 150000.00,
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {
                "prompt_tokens": 900,
                "completion_tokens": 120,
                "total_tokens": 1020
            }
        }
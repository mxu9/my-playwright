# audit_helper_poc/subagents/bank_detail_subagent.py
from ..base_subagent import BaseSubagent


class BankDetailSubagent(BaseSubagent):
    """银行明细对账单处理子代理"""

    @property
    def category(self) -> str:
        return "银行明细对账单"

    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        # 当前阶段：返回模拟数据，不实际调用 LLM
        return {
            "success": True,
            "data": {
                "account_info": {
                    "bank_name": "银行名称",
                    "account_number": "账号",
                    "account_name": "账户名称"
                },
                "period": {
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31"
                },
                "balance": {
                    "opening_balance": 100000.00,
                    "closing_balance": 150000.00
                },
                "transactions_summary": {
                    "total_deposits": 60000.00,
                    "total_withdrawals": 10000.00,
                    "transaction_count": 25
                }
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {
                "prompt_tokens": 2000,
                "completion_tokens": 400,
                "total_tokens": 2400
            }
        }
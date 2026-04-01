# audit_helper_poc/subagents/rent_contract_subagent.py
from ..base_subagent import BaseSubagent


class RentContractSubagent(BaseSubagent):
    """房租合同处理子代理"""

    @property
    def category(self) -> str:
        return "房租合同"

    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        # 当前阶段：返回模拟数据，不实际调用 LLM
        return {
            "success": True,
            "data": {
                "lease_term": {
                    "start_date": "2024-01-01",
                    "end_date": "2025-12-31",
                    "duration": "2年"
                },
                "rent": {
                    "monthly_rent": 5000,
                    "currency": "人民币",
                    "payment_cycle": "月付"
                },
                "parties": {
                    "landlord": "房东名称",
                    "tenant": "租户名称"
                },
                "property_address": "租赁地址"
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {
                "prompt_tokens": 1500,
                "completion_tokens": 300,
                "total_tokens": 1800
            }
        }
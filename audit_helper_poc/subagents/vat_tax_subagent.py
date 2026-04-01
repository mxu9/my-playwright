# audit_helper_poc/subagents/vat_tax_subagent.py
from ..base_subagent import BaseSubagent


class VatTaxSubagent(BaseSubagent):
    """增值税纳税申报表处理子代理"""

    @property
    def category(self) -> str:
        return "增值税纳税申报表"

    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        # 当前阶段：返回模拟数据，不实际调用 LLM
        return {
            "success": True,
            "data": {
                "tax_period": "2024年第一季度",
                "tax_amount": 15000.00,
                "sales_amount": 100000.00,
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {
                "prompt_tokens": 1200,
                "completion_tokens": 200,
                "total_tokens": 1400
            }
        }
# audit_helper_poc/subagents/income_tax_subagent.py
from ..base_subagent import BaseSubagent


class IncomeTaxSubagent(BaseSubagent):
    """企业所得税纳税申报表处理子代理"""

    @property
    def category(self) -> str:
        return "企业所得税纳税申报表"

    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        # 当前阶段：返回模拟数据，不实际调用 LLM
        return {
            "success": True,
            "data": {
                "tax_year": "2024",
                "taxable_income": 500000.00,
                "tax_amount": 125000.00,
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {
                "prompt_tokens": 1300,
                "completion_tokens": 250,
                "total_tokens": 1550
            }
        }
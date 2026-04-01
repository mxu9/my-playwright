# audit_helper_poc/subagents/financial_report_subagent.py
from ..base_subagent import BaseSubagent


class FinancialReportSubagent(BaseSubagent):
    """财务报表处理子代理"""

    @property
    def category(self) -> str:
        return "财务报表"

    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        # 当前阶段：返回模拟数据，不实际调用 LLM
        return {
            "success": True,
            "data": {
                "report_type": "资产负债表",
                "report_period": "2024年",
                "total_assets": 1000000.00,
                "total_liabilities": 500000.00,
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {
                "prompt_tokens": 1800,
                "completion_tokens": 350,
                "total_tokens": 2150
            }
        }
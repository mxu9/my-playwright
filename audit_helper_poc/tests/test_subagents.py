# audit_helper_poc/tests/test_subagents.py
import pytest
from unittest.mock import patch, MagicMock

from audit_helper_poc.subagents.default_subagent import DefaultSubagent
from audit_helper_poc.subagents import (
    VatTaxSubagent,
    IncomeTaxSubagent,
    FinancialReportSubagent,
    TianyanchaSubagent,
    BankConfirmationSubagent,
    BankDetailSubagent,
    BankBalanceSubagent,
)


def test_default_subagent_category():
    """测试 DefaultSubagent 的 category"""
    subagent = DefaultSubagent()
    assert subagent.category == "其他"


def test_default_subagent_invoke_returns_failure():
    """测试 DefaultSubagent invoke 返回失败状态"""
    subagent = DefaultSubagent()
    result = subagent.invoke(
        pdf_path="/test/file.pdf",
        pdf_type="native",
        config={"MODEL_NAME": "test-model"}
    )

    assert result["success"] is False
    assert result["data"] is None
    assert result["error"] == "无对应的处理 subagent"
    assert result["model"] == "test-model"
    assert result["token_usage"]["total_tokens"] == 0


def test_all_subagents_categories():
    """测试所有 subagent 的 category 属性"""
    expected = {
        VatTaxSubagent: "增值税纳税申报表",
        IncomeTaxSubagent: "企业所得税纳税申报表",
        FinancialReportSubagent: "财务报表",
        TianyanchaSubagent: "天眼查信息",
        BankConfirmationSubagent: "银行询证函",
        BankDetailSubagent: "银行明细对账单",
        BankBalanceSubagent: "银行余额对账单",
    }

    for cls, expected_category in expected.items():
        subagent = cls()
        assert subagent.category == expected_category


def test_all_subagents_invoke_returns_success():
    """测试所有 subagent invoke 返回成功"""
    # 模拟 subagent 使用简化配置
    mock_config = {"MODEL_NAME": "test-model"}

    # TianyanchaSubagent 需要完整配置和 mock
    full_config = {
        "API_KEY": "test_key",
        "BASE_URL": "https://api.test.com/v1",
        "MODEL_NAME": "test-model"
    }

    # 测试模拟 subagent（返回硬编码数据）
    for cls in [VatTaxSubagent, IncomeTaxSubagent, FinancialReportSubagent,
                BankConfirmationSubagent, BankDetailSubagent, BankBalanceSubagent]:
        subagent = cls()
        result = subagent.invoke("/test.pdf", "native", mock_config)
        assert result["success"] is True
        assert result["data"] is not None
        assert result["error"] is None
        assert result["token_usage"]["total_tokens"] > 0

    # 测试 TianyanchaSubagent（需要 mock LLM）
    with patch('audit_helper_poc.subagents.tianyancha_subagent.pdf_to_images') as mock_to_images, \
         patch('audit_helper_poc.subagents.tianyancha_subagent.LLMClient') as mock_llm_class:
        mock_to_images.return_value = ["base64img"]
        mock_llm = MagicMock()
        mock_llm.get_token_summary.return_value = {"total_tokens": 100}
        mock_llm.invoke_with_json_response.return_value = (
            {"企业名称": "测试", "confidence": 0.9},
            {"total_tokens": 100}
        )
        mock_llm_class.return_value = mock_llm

        subagent = TianyanchaSubagent()
        result = subagent.invoke("/test.pdf", "scanned", full_config)
        assert result["success"] is True
        assert result["data"] is not None
        assert result["error"] is None
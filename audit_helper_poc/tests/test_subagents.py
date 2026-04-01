# audit_helper_poc/tests/test_subagents.py
import pytest
from audit_helper_poc.subagents.default_subagent import DefaultSubagent
from audit_helper_poc.subagents.rent_contract_subagent import RentContractSubagent
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


def test_rent_contract_subagent_category():
    """测试 RentContractSubagent 的 category"""
    subagent = RentContractSubagent()
    assert subagent.category == "房租合同"


def test_rent_contract_subagent_invoke_returns_mock_data():
    """测试 RentContractSubagent invoke 返回模拟数据"""
    subagent = RentContractSubagent()
    result = subagent.invoke(
        pdf_path="/test/rent.pdf",
        pdf_type="native",
        config={"MODEL_NAME": "gpt-4o"}
    )

    assert result["success"] is True
    assert result["data"] is not None
    assert "lease_term" in result["data"]
    assert "rent" in result["data"]
    assert result["error"] is None
    assert result["model"] == "gpt-4o"
    assert result["token_usage"]["total_tokens"] > 0


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
    config = {"MODEL_NAME": "test-model"}

    for cls in [VatTaxSubagent, IncomeTaxSubagent, FinancialReportSubagent,
                TianyanchaSubagent, BankConfirmationSubagent, BankDetailSubagent,
                BankBalanceSubagent]:
        subagent = cls()
        result = subagent.invoke("/test.pdf", "native", config)
        assert result["success"] is True
        assert result["data"] is not None
        assert result["error"] is None
        assert result["token_usage"]["total_tokens"] > 0
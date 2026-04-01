# audit_helper_poc/tests/test_subagents.py
import pytest
from audit_helper_poc.subagents.default_subagent import DefaultSubagent
from audit_helper_poc.subagents.rent_contract_subagent import RentContractSubagent


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
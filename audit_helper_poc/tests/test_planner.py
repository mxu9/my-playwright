# audit_helper_poc/tests/test_planner.py
import pytest
from audit_helper_poc.planner import Planner


def test_planner_init():
    """测试 Planner 初始化"""
    planner = Planner()
    assert planner.config is not None
    assert planner.logger is not None
    assert len(planner._subagents) == 9  # 8 个 + 1 个 default


def test_planner_register_subagent():
    """测试注册自定义 subagent"""
    planner = Planner()

    class CustomSubagent:
        @property
        def category(self):
            return "自定义类别"

    planner.register_subagent(CustomSubagent())
    assert "自定义类别" in planner._subagents


def test_planner_has_all_categories():
    """测试包含所有类别"""
    planner = Planner()
    expected = [
        "房租合同", "增值税纳税申报表", "企业所得税纳税申报表",
        "财务报表", "天眼查信息", "银行询证函",
        "银行明细对账单", "银行余额对账单", "其他"
    ]
    for cat in expected:
        assert cat in planner._subagents
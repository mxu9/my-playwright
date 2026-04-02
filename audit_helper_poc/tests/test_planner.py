# audit_helper_poc/tests/test_planner.py
import pytest
from unittest.mock import patch, MagicMock

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


class TestSkipCategories:
    """测试跳过类型功能"""

    def test_skip_single_category(self):
        """测试跳过单个类型"""
        planner = Planner()
        planner.config["SKIP_CATEGORIES"] = "天眼查信息"

        with patch('audit_helper_poc.planner.detect_pdf_type') as mock_detect, \
             patch.object(planner, '_classify_pdf') as mock_classify, \
             patch.object(planner, '_init_llm_client') as mock_llm:

            mock_detect.return_value = "scanned"
            mock_classify.return_value = "天眼查信息"
            mock_llm.return_value = MagicMock()

            result = planner._process_single_file("/test.pdf")

            assert result["category"] == "天眼查信息"
            assert result["subagent_result"]["skipped"] is True
            assert result["subagent_result"]["success"] is True
            assert result["subagent_result"]["data"] is None

    def test_skip_multiple_categories(self):
        """测试跳过多个类型"""
        planner = Planner()
        planner.config["SKIP_CATEGORIES"] = "房租合同,银行明细对账单"

        with patch('audit_helper_poc.planner.detect_pdf_type') as mock_detect, \
             patch.object(planner, '_classify_pdf') as mock_classify, \
             patch.object(planner, '_init_llm_client') as mock_llm:

            mock_detect.return_value = "native"
            mock_classify.return_value = "房租合同"
            mock_llm.return_value = MagicMock()

            result = planner._process_single_file("/test.pdf")

            assert result["subagent_result"]["skipped"] is True

    def test_not_skip_unlisted_category(self):
        """测试不跳过未列出的类型"""
        planner = Planner()
        planner.config["SKIP_CATEGORIES"] = "房租合同"

        with patch('audit_helper_poc.planner.detect_pdf_type') as mock_detect, \
             patch.object(planner, '_classify_pdf') as mock_classify, \
             patch.object(planner, '_init_llm_client') as mock_llm:

            mock_detect.return_value = "scanned"
            mock_classify.return_value = "天眼查信息"
            mock_llm.return_value = MagicMock()

            # mock subagent invoke
            with patch.object(planner._subagents["天眼查信息"], 'invoke') as mock_invoke:
                mock_invoke.return_value = {
                    "success": True,
                    "data": {"企业名称": "测试"},
                    "error": None,
                    "model": "test",
                    "token_usage": {"total_tokens": 100}
                }

                result = planner._process_single_file("/test.pdf")

                assert result["subagent_result"].get("skipped") is not True
                assert result["subagent_result"]["data"] is not None

    def test_empty_skip_categories(self):
        """测试空配置不跳过"""
        planner = Planner()
        planner.config["SKIP_CATEGORIES"] = ""

        with patch('audit_helper_poc.planner.detect_pdf_type') as mock_detect, \
             patch.object(planner, '_classify_pdf') as mock_classify, \
             patch.object(planner, '_init_llm_client') as mock_llm:

            mock_detect.return_value = "scanned"
            mock_classify.return_value = "天眼查信息"
            mock_llm.return_value = MagicMock()

            with patch.object(planner._subagents["天眼查信息"], 'invoke') as mock_invoke:
                mock_invoke.return_value = {
                    "success": True,
                    "data": {},
                    "error": None,
                    "model": "test",
                    "token_usage": {"total_tokens": 100}
                }

                result = planner._process_single_file("/test.pdf")

                assert result["subagent_result"].get("skipped") is not True

    def test_skip_with_whitespace(self):
        """测试配置带空格也能正确匹配"""
        planner = Planner()
        planner.config["SKIP_CATEGORIES"] = " 天眼查信息 , 房租合同 "

        with patch('audit_helper_poc.planner.detect_pdf_type') as mock_detect, \
             patch.object(planner, '_classify_pdf') as mock_classify, \
             patch.object(planner, '_init_llm_client') as mock_llm:

            mock_detect.return_value = "scanned"
            mock_classify.return_value = "天眼查信息"
            mock_llm.return_value = MagicMock()

            result = planner._process_single_file("/test.pdf")

            assert result["subagent_result"]["skipped"] is True
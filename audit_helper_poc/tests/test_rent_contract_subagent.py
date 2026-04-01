"""
测试 RentContractSubagent
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from audit_helper_poc.subagents.rent_contract_subagent import (
    RentContractSubagent,
    LOCATE_PAGES_SYSTEM_PROMPT,
    EXTRACT_INFO_SYSTEM_PROMPT
)


class TestRentContractSubagent:
    """测试 RentContractSubagent"""

    def test_category(self):
        """测试 category 属性"""
        subagent = RentContractSubagent()
        assert subagent.category == "房租合同"

    def test_invoke_success(self, tmp_path):
        """测试成功处理流程"""
        subagent = RentContractSubagent()

        config = {
            "API_KEY": "test_key",
            "BASE_URL": "https://api.test.com/v1",
            "MODEL_NAME": "test-model"
        }

        with patch.object(subagent, '_ocr_pages') as mock_ocr, \
             patch.object(subagent, '_locate_pages') as mock_locate, \
             patch('audit_helper_poc.subagents.rent_contract_subagent.pdf_to_images') as mock_to_images, \
             patch('audit_helper_poc.subagents.rent_contract_subagent.LLMClient') as mock_llm_class:

            # 设置 mock
            mock_ocr.return_value = ["第一页内容", "第二页内容"]
            mock_locate.return_value = [1, 2]
            mock_to_images.return_value = ["base64img1", "base64img2"]

            mock_llm = MagicMock()
            mock_llm.get_token_summary.return_value = {
                "total_calls": 2,
                "total_tokens": 100
            }
            mock_llm.invoke_with_json_response.return_value = (
                {
                    "lease_term": {"start_date": "2024-01-01", "end_date": "2025-12-31"},
                    "rent": {"monthly_rent": 5000},
                    "confidence": 0.9
                },
                {"total_tokens": 50}
            )
            mock_llm_class.return_value = mock_llm

            # 创建临时 PDF 文件
            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf")

            result = subagent.invoke(str(pdf_file), "native", config)

            assert result["success"] is True
            assert result["data"] is not None
            assert result["error"] is None
            assert result["model"] == "test-model"
            assert "lease_term" in result["data"]

    def test_invoke_no_pages_located(self, tmp_path):
        """测试未能定位页面"""
        subagent = RentContractSubagent()

        config = {
            "API_KEY": "test_key",
            "BASE_URL": "https://api.test.com/v1",
            "MODEL_NAME": "test-model"
        }

        with patch.object(subagent, '_ocr_pages') as mock_ocr, \
             patch.object(subagent, '_locate_pages') as mock_locate, \
             patch('audit_helper_poc.subagents.rent_contract_subagent.LLMClient') as mock_llm_class:

            mock_ocr.return_value = ["无关节容"]
            mock_locate.return_value = []  # 未定位到页面

            mock_llm = MagicMock()
            mock_llm.get_token_summary.return_value = {"total_calls": 1}
            mock_llm_class.return_value = mock_llm

            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf")

            result = subagent.invoke(str(pdf_file), "native", config)

            assert result["success"] is False
            assert "未能定位" in result["error"]

    def test_invoke_exception(self, tmp_path):
        """测试异常处理"""
        subagent = RentContractSubagent()

        config = {
            "API_KEY": "test_key",
            "BASE_URL": "https://api.test.com/v1",
            "MODEL_NAME": "test-model"
        }

        with patch.object(subagent, '_ocr_pages') as mock_ocr:
            mock_ocr.side_effect = Exception("OCR 失败")

            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf")

            result = subagent.invoke(str(pdf_file), "native", config)

            assert result["success"] is False
            assert "OCR 失败" in result["error"]

    def test_parse_pages_response_json(self):
        """测试解析 JSON 格式响应"""
        subagent = RentContractSubagent()

        response = "[1, 3, 5]"
        pages = subagent._parse_pages_response(response)

        assert pages == [1, 3, 5]

    def test_parse_pages_response_with_text(self):
        """测试解析带文本的响应"""
        subagent = RentContractSubagent()

        response = "根据分析，相关页面为：[2, 4, 6]"
        pages = subagent._parse_pages_response(response)

        assert pages == [2, 4, 6]

    def test_parse_pages_response_numbers_only(self):
        """测试解析纯数字响应"""
        subagent = RentContractSubagent()

        response = "第 1 页和第 3 页"
        pages = subagent._parse_pages_response(response)

        assert pages == [1, 3]

    def test_apply_sliding_window(self):
        """测试滑动窗口"""
        subagent = RentContractSubagent()
        subagent.WINDOW_SIZE = 1

        pages = [3, 5]
        total_pages = 10

        expanded = subagent._apply_sliding_window(pages, total_pages)

        # 应包含原页面及相邻页
        assert 3 in expanded
        assert 2 in expanded  # 3-1
        assert 4 in expanded  # 3+1
        assert 5 in expanded
        assert 4 in expanded  # 5-1 (重复)
        assert 6 in expanded  # 5+1

    def test_apply_sliding_window_boundary(self):
        """测试滑动窗口边界"""
        subagent = RentContractSubagent()
        subagent.WINDOW_SIZE = 1

        pages = [1, 10]
        total_pages = 10

        expanded = subagent._apply_sliding_window(pages, total_pages)

        # 页码 1 不应扩展到 0
        assert 1 in expanded
        assert 2 in expanded
        assert 0 not in expanded

        # 页码 10 不应扩展到 11
        assert 10 in expanded
        assert 9 in expanded
        assert 11 not in expanded


class TestPrompts:
    """测试 Prompt 定义"""

    def test_locate_pages_prompt(self):
        """测试定位 Prompt 内容"""
        assert "租赁期限" in LOCATE_PAGES_SYSTEM_PROMPT
        assert "JSON 数组" in LOCATE_PAGES_SYSTEM_PROMPT

    def test_extract_info_prompt(self):
        """测试提取 Prompt 内容"""
        assert "lease_term" in EXTRACT_INFO_SYSTEM_PROMPT
        assert "rent" in EXTRACT_INFO_SYSTEM_PROMPT
        assert "parties" in EXTRACT_INFO_SYSTEM_PROMPT
        assert "confidence" in EXTRACT_INFO_SYSTEM_PROMPT
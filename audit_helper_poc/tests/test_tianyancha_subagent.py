"""
测试 TianyanchaSubagent
"""
import pytest
from unittest.mock import patch, MagicMock

from audit_helper_poc.subagents.tianyancha_subagent import (
    TianyanchaSubagent,
    EXTRACT_INFO_SYSTEM_PROMPT,
    EXTRACT_INFO_USER_PROMPT,
    EXPECTED_JSON_FORMAT
)


class TestTianyanchaSubagent:
    """测试 TianyanchaSubagent"""

    def test_category(self):
        """测试 category 属性"""
        subagent = TianyanchaSubagent()
        assert subagent.category == "天眼查信息"

    def test_invoke_missing_config(self):
        """测试缺少必要配置时返回错误"""
        subagent = TianyanchaSubagent()

        # 缺少 API_KEY 和 BASE_URL
        config = {"MODEL_NAME": "test-model"}

        result = subagent.invoke("/test.pdf", "scanned", config)

        assert result["success"] is False
        assert result["data"] is None
        assert "缺少必要配置" in result["error"]

    def test_invoke_success(self, tmp_path):
        """测试成功处理流程"""
        subagent = TianyanchaSubagent()

        config = {
            "API_KEY": "test_key",
            "BASE_URL": "https://api.test.com/v1",
            "MODEL_NAME": "test-model"
        }

        with patch('audit_helper_poc.subagents.tianyancha_subagent.pdf_to_images') as mock_to_images, \
             patch('audit_helper_poc.subagents.tianyancha_subagent.LLMClient') as mock_llm_class:

            # 设置 mock
            mock_to_images.return_value = ["base64img1", "base64img2"]

            mock_llm = MagicMock()
            mock_llm.get_token_summary.return_value = {
                "total_calls": 1,
                "total_tokens": 1800
            }
            mock_llm.invoke_with_json_response.return_value = (
                {
                    "企业名称": "测试公司",
                    "法定代表人": "张三",
                    "成立日期": "2020-01-01",
                    "注册资本": "100万人民币",
                    "登记机关": "北京市工商局",
                    "注册地址": "北京市朝阳区",
                    "通信地址": "北京市朝阳区",
                    "经营范围": "技术开发",
                    "股东信息": [
                        {"股东名称": "张三", "持股比例": "60%", "出资额": "60万人民币"}
                    ],
                    "2025年变更记录": [],
                    "confidence": 0.9
                },
                {"total_tokens": 1800}
            )
            mock_llm_class.return_value = mock_llm

            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf")

            result = subagent.invoke(str(pdf_file), "scanned", config)

            assert result["success"] is True
            assert result["data"] is not None
            assert result["error"] is None
            assert result["model"] == "test-model"
            assert result["data"]["企业名称"] == "测试公司"

    def test_invoke_no_images(self, tmp_path):
        """测试无法转换图片"""
        subagent = TianyanchaSubagent()

        config = {
            "API_KEY": "test_key",
            "BASE_URL": "https://api.test.com/v1",
            "MODEL_NAME": "test-model"
        }

        with patch('audit_helper_poc.subagents.tianyancha_subagent.pdf_to_images') as mock_to_images, \
             patch('audit_helper_poc.subagents.tianyancha_subagent.LLMClient') as mock_llm_class:

            mock_to_images.return_value = []  # 无图片

            mock_llm = MagicMock()
            mock_llm.get_token_summary.return_value = {"total_tokens": 0}
            mock_llm_class.return_value = mock_llm

            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf")

            result = subagent.invoke(str(pdf_file), "scanned", config)

            assert result["success"] is False
            assert "无法将 PDF 转换为图片" in result["error"]

    def test_invoke_llm_returns_invalid_json(self, tmp_path):
        """测试 LLM 返回无效 JSON"""
        subagent = TianyanchaSubagent()

        config = {
            "API_KEY": "test_key",
            "BASE_URL": "https://api.test.com/v1",
            "MODEL_NAME": "test-model"
        }

        with patch('audit_helper_poc.subagents.tianyancha_subagent.pdf_to_images') as mock_to_images, \
             patch('audit_helper_poc.subagents.tianyancha_subagent.LLMClient') as mock_llm_class:

            mock_to_images.return_value = ["base64img1"]

            mock_llm = MagicMock()
            mock_llm.get_token_summary.return_value = {"total_tokens": 500}
            mock_llm.invoke_with_json_response.return_value = (None, {"total_tokens": 500})
            mock_llm_class.return_value = mock_llm

            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf")

            result = subagent.invoke(str(pdf_file), "scanned", config)

            assert result["success"] is True
            assert result["data"]["企业名称"] is None
            assert result["data"]["confidence"] == 0.0

    def test_invoke_exception(self, tmp_path):
        """测试异常处理"""
        subagent = TianyanchaSubagent()

        config = {
            "API_KEY": "test_key",
            "BASE_URL": "https://api.test.com/v1",
            "MODEL_NAME": "test-model"
        }

        with patch('audit_helper_poc.subagents.tianyancha_subagent.pdf_to_images') as mock_to_images:
            mock_to_images.side_effect = Exception("PDF 转换失败")

            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf")

            result = subagent.invoke(str(pdf_file), "scanned", config)

            assert result["success"] is False
            assert "PDF 转换失败" in result["error"]


class TestPrompts:
    """测试 Prompt 定义"""

    def test_extract_info_system_prompt(self):
        """测试提取信息系统提示"""
        assert "金融合规审计专家" in EXTRACT_INFO_SYSTEM_PROMPT
        assert "天眼查" in EXTRACT_INFO_SYSTEM_PROMPT
        assert "企业名称" in EXTRACT_INFO_SYSTEM_PROMPT
        assert "法定代表人" in EXTRACT_INFO_SYSTEM_PROMPT
        assert "注册资本" in EXTRACT_INFO_SYSTEM_PROMPT
        assert "股东信息" in EXTRACT_INFO_SYSTEM_PROMPT
        assert "2025年" in EXTRACT_INFO_SYSTEM_PROMPT
        assert "变更记录" in EXTRACT_INFO_SYSTEM_PROMPT
        assert "XX万人民币" in EXTRACT_INFO_SYSTEM_PROMPT
        assert "JSON 格式" in EXTRACT_INFO_SYSTEM_PROMPT

    def test_extract_info_user_prompt(self):
        """测试提取信息用户提示"""
        assert "天眼查" in EXTRACT_INFO_USER_PROMPT
        assert "JSON" in EXTRACT_INFO_USER_PROMPT

    def test_expected_json_format(self):
        """测试期望的 JSON 格式"""
        assert "企业名称" in EXPECTED_JSON_FORMAT
        assert "法定代表人" in EXPECTED_JSON_FORMAT
        assert "成立日期" in EXPECTED_JSON_FORMAT
        assert "注册资本" in EXPECTED_JSON_FORMAT
        assert "股东信息" in EXPECTED_JSON_FORMAT
        assert "2025年变更记录" in EXPECTED_JSON_FORMAT
        assert "confidence" in EXPECTED_JSON_FORMAT
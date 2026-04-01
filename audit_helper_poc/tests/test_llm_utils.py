"""
测试 LLM 工具模块
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from audit_helper_poc.llm_utils import (
    TokenUsageTracker,
    LLMClient,
    build_multimodal_content
)


class TestTokenUsageTracker:
    """测试 TokenUsageTracker"""

    def test_init(self):
        """测试初始化"""
        tracker = TokenUsageTracker()
        assert tracker.calls == []
        assert tracker.total_prompt_tokens == 0
        assert tracker.total_completion_tokens == 0
        assert tracker.total_tokens == 0

    def test_add_call(self):
        """测试添加调用记录"""
        tracker = TokenUsageTracker()

        # 模拟响应对象
        response = Mock()
        response.response_metadata = {
            'token_usage': {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'total_tokens': 150
            }
        }

        call_info = tracker.add_call("test_call", response)

        assert call_info["call_name"] == "test_call"
        assert call_info["token_usage"]["prompt_tokens"] == 100
        assert call_info["token_usage"]["completion_tokens"] == 50
        assert tracker.total_prompt_tokens == 100
        assert tracker.total_tokens == 150

    def test_add_call_no_metadata(self):
        """测试响应无元数据的情况"""
        tracker = TokenUsageTracker()

        response = Mock()
        response.response_metadata = None

        call_info = tracker.add_call("test_call", response)

        assert call_info["token_usage"]["prompt_tokens"] == 0
        assert tracker.total_tokens == 0

    def test_get_summary(self):
        """测试获取汇总"""
        tracker = TokenUsageTracker()

        response = Mock()
        response.response_metadata = {
            'token_usage': {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'total_tokens': 150
            }
        }
        tracker.add_call("call1", response)
        tracker.add_call("call2", response)

        summary = tracker.get_summary()

        assert summary["total_calls"] == 2
        assert summary["total_prompt_tokens"] == 200
        assert summary["total_completion_tokens"] == 100
        assert summary["total_tokens"] == 300

    def test_reset(self):
        """测试重置"""
        tracker = TokenUsageTracker()

        response = Mock()
        response.response_metadata = {
            'token_usage': {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'total_tokens': 150
            }
        }
        tracker.add_call("test", response)
        tracker.reset()

        assert tracker.calls == []
        assert tracker.total_tokens == 0


class TestLLMClient:
    """测试 LLMClient"""

    def test_init_success(self):
        """测试成功初始化"""
        with patch('audit_helper_poc.llm_utils.ChatOpenAI'):
            client = LLMClient(
                api_key="test_key",
                base_url="https://api.test.com/v1",
                model_name="test-model"
            )
            assert client.api_key == "test_key"
            assert client.model_name == "test-model"

    def test_init_no_api_key(self):
        """测试无 API Key 初始化"""
        with pytest.raises(ValueError, match="API_KEY 不能为空"):
            LLMClient(
                api_key="",
                base_url="https://api.test.com/v1",
                model_name="test-model"
            )

    def test_invoke(self):
        """测试 invoke 方法"""
        with patch('audit_helper_poc.llm_utils.ChatOpenAI') as mock_chat:
            # 设置 mock
            mock_instance = MagicMock()
            mock_response = Mock()
            mock_response.content = "Hello"
            mock_response.response_metadata = {
                'token_usage': {
                    'prompt_tokens': 10,
                    'completion_tokens': 5,
                    'total_tokens': 15
                }
            }
            mock_instance.invoke.return_value = mock_response
            mock_chat.return_value = mock_instance

            client = LLMClient(
                api_key="test_key",
                base_url="https://api.test.com/v1",
                model_name="test-model"
            )

            response, token_usage = client.invoke(
                system_prompt="You are helpful",
                user_content="Hi",
                call_name="test"
            )

            assert response == "Hello"
            assert token_usage["total_tokens"] == 15

    def test_invoke_with_json_response(self):
        """测试 JSON 响应解析"""
        with patch('audit_helper_poc.llm_utils.ChatOpenAI') as mock_chat:
            mock_instance = MagicMock()
            mock_response = Mock()
            mock_response.content = '{"key": "value"}'
            mock_response.response_metadata = {
                'token_usage': {
                    'prompt_tokens': 10,
                    'completion_tokens': 5,
                    'total_tokens': 15
                }
            }
            mock_instance.invoke.return_value = mock_response
            mock_chat.return_value = mock_instance

            client = LLMClient(
                api_key="test_key",
                base_url="https://api.test.com/v1",
                model_name="test-model"
            )

            result, token_usage = client.invoke_with_json_response(
                system_prompt="Return JSON",
                user_content="Give me JSON"
            )

            assert result == {"key": "value"}
            assert token_usage["total_tokens"] == 15

    def test_invoke_with_json_response_invalid(self):
        """测试无效 JSON 响应"""
        with patch('audit_helper_poc.llm_utils.ChatOpenAI') as mock_chat:
            mock_instance = MagicMock()
            mock_response = Mock()
            mock_response.content = "This is not JSON"
            mock_response.response_metadata = {
                'token_usage': {
                    'prompt_tokens': 10,
                    'completion_tokens': 5,
                    'total_tokens': 15
                }
            }
            mock_instance.invoke.return_value = mock_response
            mock_chat.return_value = mock_instance

            client = LLMClient(
                api_key="test_key",
                base_url="https://api.test.com/v1",
                model_name="test-model"
            )

            result, token_usage = client.invoke_with_json_response(
                system_prompt="Return JSON",
                user_content="Give me JSON"
            )

            assert result is None
            assert token_usage["total_tokens"] == 15


class TestBuildMultimodalContent:
    """测试 build_multimodal_content"""

    def test_build_with_images_and_text(self):
        """测试构建多模态内容"""
        images = ["base64img1", "base64img2"]
        text = "Describe these images"

        content = build_multimodal_content(images, text)

        assert len(content) == 3
        assert content[0]["type"] == "image_url"
        assert "base64img1" in content[0]["image_url"]["url"]
        assert content[2]["type"] == "text"
        assert content[2]["text"] == "Describe these images"

    def test_build_with_only_images(self):
        """测试仅图片"""
        images = ["base64img1"]
        content = build_multimodal_content(images, "")

        assert len(content) == 1
        assert content[0]["type"] == "image_url"

    def test_build_with_only_text(self):
        """测试仅文本"""
        content = build_multimodal_content([], "Hello")

        assert len(content) == 1
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "Hello"

    def test_build_empty(self):
        """测试空内容"""
        content = build_multimodal_content([], "")

        assert len(content) == 0
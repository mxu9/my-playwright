import pytest
from unittest.mock import Mock, patch, MagicMock


def test_llm_client_initialization():
    """测试 LLM 客户端初始化"""
    from llm_client import LLMClient

    # Mock ChatOpenAI to avoid real API calls during initialization test
    with patch('llm_client.ChatOpenAI') as mock_chat:
        mock_chat.return_value = Mock()

        client = LLMClient(
            api_key="test_key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4o"
        )

        assert client.api_key == "test_key"
        assert client.base_url == "https://api.openai.com/v1"
        assert client.model_name == "gpt-4o"


def test_llm_client_invalid_config():
    """测试无效配置时抛出异常"""
    from llm_client import LLMClient

    with pytest.raises(ValueError):
        LLMClient(
            api_key="",  # 空的 API key
            base_url="https://api.openai.com/v1",
            model_name="gpt-4o"
        )


def test_classify_text_content():
    """测试文本内容分类（模拟 LLM 响应）"""
    from llm_client import LLMClient

    # 模拟 LLM 响应
    mock_response = Mock()
    mock_response.content = '{"category": "增值税纳税申报表", "confidence": 0.95}'

    # Mock ChatOpenAI to avoid real API calls
    mock_chat_instance = MagicMock()
    mock_chat_instance.invoke.return_value = mock_response

    with patch('llm_client.ChatOpenAI', return_value=mock_chat_instance):
        client = LLMClient(
            api_key="test_key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4o"
        )

        result = client.classify("这是一份增值税申报表...", "native")

        assert result["category"] == "增值税纳税申报表"
        assert result["confidence"] == 0.95


def test_classify_image_content():
    """测试图片内容分类（模拟 LLM 响应）"""
    from llm_client import LLMClient

    # 模拟 LLM 响应
    mock_response = Mock()
    mock_response.content = '{"category": "银行明细对账单", "confidence": 0.88}'

    # Mock ChatOpenAI to avoid real API calls
    mock_chat_instance = MagicMock()
    mock_chat_instance.invoke.return_value = mock_response

    with patch('llm_client.ChatOpenAI', return_value=mock_chat_instance):
        client = LLMClient(
            api_key="test_key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4o"
        )

        result = client.classify(["base64_image_data"], "scanned")

        assert result["category"] == "银行明细对账单"
        assert result["confidence"] == 0.88
# audit_helper_poc/tests/test_base_subagent.py
import pytest
from abc import ABC
from audit_helper_poc.base_subagent import BaseSubagent


def test_base_subagent_is_abstract():
    """测试 BaseSubagent 是抽象类"""
    assert ABC in BaseSubagent.__bases__


def test_base_subagent_cannot_instantiate():
    """测试不能直接实例化抽象类"""
    with pytest.raises(TypeError):
        BaseSubagent()


def test_base_subagent_has_category_property():
    """测试 category 是抽象属性"""
    # 子类必须实现 category
    class IncompleteSubagent(BaseSubagent):
        def invoke(self, pdf_path, pdf_type, config):
            return {}

    with pytest.raises(TypeError):
        IncompleteSubagent()


def test_base_subagent_has_invoke_method():
    """测试 invoke 是抽象方法"""
    class IncompleteSubagent(BaseSubagent):
        @property
        def category(self):
            return "test"

    with pytest.raises(TypeError):
        IncompleteSubagent()


def test_complete_subagent_can_instantiate():
    """测试完整实现的子类可以实例化"""
    class CompleteSubagent(BaseSubagent):
        @property
        def category(self):
            return "test_category"

        def invoke(self, pdf_path, pdf_type, config):
            return {
                "success": True,
                "data": {},
                "error": None,
                "model": config.get("MODEL_NAME", ""),
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }

    subagent = CompleteSubagent()
    assert subagent.category == "test_category"
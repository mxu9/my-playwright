# audit_helper_poc/tests/test_logger.py
import pytest
from audit_helper_poc.logger import Logger


def test_logger_init_default():
    """测试默认初始化"""
    logger = Logger()
    assert logger.name == "audit_helper_poc"
    assert logger.level == "INFO"


def test_logger_init_custom():
    """测试自定义初始化"""
    logger = Logger(name="test_logger", level="DEBUG")
    assert logger.name == "test_logger"
    assert logger.level == "DEBUG"


def test_logger_output_info():
    """测试 info 方法输出"""
    logger = Logger(level="INFO")
    # 应能正常调用，不抛异常
    logger.info("test message")


def test_logger_output_debug():
    """测试 debug 方法在 INFO 级别不输出"""
    logger = Logger(level="INFO")
    logger.debug("debug message")  # 不应输出，但不抛异常


def test_logger_all_levels():
    """测试所有日志级别方法"""
    logger = Logger(level="DEBUG")
    logger.debug("debug")
    logger.info("info")
    logger.warning("warning")
    logger.error("error")
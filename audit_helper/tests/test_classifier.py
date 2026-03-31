"""
PDFClassifier 测试模块
"""
import sys
from pathlib import Path

# 添加父目录到 sys.path 以支持包导入
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import os
import tempfile
from unittest.mock import Mock, patch
from classifier import PDFClassifier


def test_classifier_initialization():
    """测试分类器初始化"""

    # 创建临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("API_KEY=test_key\n")
        f.write("BASE_URL=https://api.openai.com/v1\n")
        f.write("MODEL_NAME=gpt-4o\n")
        f.write("TEXT_DENSITY_THRESHOLD=0.0001\n")
        f.write("PAGES_FOR_CLASSIFICATION=2\n")
        f.write("OUTPUT_DIR=output\n")
        f.write("OUTPUT_FILENAME=result.json\n")
        temp_path = f.name

    try:
        classifier = PDFClassifier(config_path=temp_path)

        assert classifier.config["API_KEY"] == "test_key"
        assert classifier.config["TEXT_DENSITY_THRESHOLD"] == 0.0001
    finally:
        os.unlink(temp_path)


def test_run_classify_pdfs():
    """测试完整分类流程（模拟组件）"""

    # 创建临时配置
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("API_KEY=test_key\n")
        f.write("BASE_URL=https://api.openai.com/v1\n")
        f.write("MODEL_NAME=gpt-4o\n")
        f.write("TEXT_DENSITY_THRESHOLD=0.0001\n")
        f.write("PAGES_FOR_CLASSIFICATION=2\n")
        f.write("OUTPUT_DIR=output\n")
        f.write("OUTPUT_FILENAME=result.json\n")
        config_path = f.name

    # 创建临时输入目录
    with tempfile.TemporaryDirectory() as input_dir:
        # 创建假 PDF 文件
        Path(os.path.join(input_dir, "test1.pdf")).touch()
        Path(os.path.join(input_dir, "test2.pdf")).touch()

        classifier = PDFClassifier(config_path=config_path)

        # 模拟 PDF 处理器
        classifier.pdf_processor.process = Mock(return_value={
            "pdf_type": "native",
            "content": "测试内容",
            "pages_processed": 2
        })

        # 模拟 LLM 客户端
        classifier.llm_client.classify = Mock(return_value={
            "category": "房租合同",
            "confidence": 0.95
        })

        # 运行分类
        with tempfile.TemporaryDirectory() as output_dir:
            result = classifier.run(input_dir=input_dir, output_dir=output_dir)

            assert result["total_files"] == 2
            assert len(result["results"]) == 2
            assert "summary" in result

    os.unlink(config_path)


def test_classify_single_pdf():
    """测试单个 PDF 分类"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("API_KEY=test_key\n")
        f.write("BASE_URL=https://api.openai.com/v1\n")
        f.write("MODEL_NAME=gpt-4o\n")
        config_path = f.name

    classifier = PDFClassifier(config_path=config_path)

    # 模拟组件
    classifier.pdf_processor.process = Mock(return_value={
        "pdf_type": "native",
        "content": "测试内容",
        "pages_processed": 2
    })
    classifier.llm_client.classify = Mock(return_value={
        "category": "增值税纳税申报表",
        "confidence": 0.88
    })

    # 创建临时 PDF 文件
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
        pdf_path = pdf_file.name

    try:
        result = classifier.classify_single(pdf_path)

        assert result["pdf_type"] == "native"
        assert result["category"] == "增值税纳税申报表"
        assert result["confidence"] == 0.88
        assert result["pages_processed"] == 2
    finally:
        os.unlink(pdf_path)
        os.unlink(config_path)


def test_config_validation_missing_keys(monkeypatch):
    """测试配置验证：缺少必填项时应抛出异常"""
    # 清除可能存在的环境变量，确保测试隔离
    for key in ["API_KEY", "BASE_URL", "MODEL_NAME", "TEXT_DENSITY_THRESHOLD", "PAGES_FOR_CLASSIFICATION"]:
        monkeypatch.delenv(key, raising=False)

    # 创建缺少必填项的配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("API_KEY=test_key\n")
        f.write("BASE_URL=https://api.openai.com/v1\n")
        # 缺少 MODEL_NAME
        config_path = f.name

    try:
        with pytest.raises(ValueError) as exc_info:
            PDFClassifier(config_path=config_path)
        assert "缺少必填配置项" in str(exc_info.value) or "配置缺少必填项" in str(exc_info.value)
    finally:
        os.unlink(config_path)


def test_run_with_error():
    """测试分类流程中的错误处理"""
    # 创建临时配置
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("API_KEY=test_key\n")
        f.write("BASE_URL=https://api.openai.com/v1\n")
        f.write("MODEL_NAME=gpt-4o\n")
        f.write("TEXT_DENSITY_THRESHOLD=0.0001\n")
        f.write("PAGES_FOR_CLASSIFICATION=2\n")
        f.write("OUTPUT_DIR=output\n")
        f.write("OUTPUT_FILENAME=result.json\n")
        config_path = f.name

    # 创建临时输入目录
    with tempfile.TemporaryDirectory() as input_dir:
        # 创建假 PDF 文件
        Path(os.path.join(input_dir, "error_test.pdf")).touch()

        classifier = PDFClassifier(config_path=config_path)

        # 模拟 PDF 处理器抛出异常
        classifier.pdf_processor.process = Mock(
            side_effect=Exception("PDF 处理失败")
        )

        # 运行分类
        with tempfile.TemporaryDirectory() as output_dir:
            result = classifier.run(input_dir=input_dir, output_dir=output_dir)

            # 验证错误被捕获并生成错误结果
            assert result["total_files"] == 1
            assert len(result["results"]) == 1
            error_result = result["results"][0]
            assert error_result["pdf_type"] == "unknown"
            assert error_result["category"] == "其他"
            assert error_result["confidence"] == 0.0
            assert "error" in error_result
            assert "PDF 处理失败" in error_result["error"]

            # 验证汇总中包含 unknown 计数
            assert "unknown_count" in result["summary"]
            assert result["summary"]["unknown_count"] == 1

    os.unlink(config_path)
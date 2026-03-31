"""
PDFClassifier 测试模块
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch


def test_classifier_initialization():
    """测试分类器初始化"""
    from classifier import PDFClassifier

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
    from classifier import PDFClassifier

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
    from classifier import PDFClassifier

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
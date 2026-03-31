import pytest
import os
from pathlib import Path
import sys

# 添加父目录到路径，以便导入模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_is_native_pdf_with_text_content():
    """测试原生 PDF（含文本）被正确识别"""
    from pdf_processor import PDFProcessor

    processor = PDFProcessor(
        text_density_threshold=0.0001,
        pages_for_classification=2
    )

    # 使用测试数据目录中已知为原生的 PDF
    # 增值税申报表通常是原生 PDF
    test_pdf = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "增值税及附加税费申报表（一般纳税人适用）-给力.pdf")
    if os.path.exists(test_pdf):
        result = processor._is_native_pdf(test_pdf)
        assert result == True


def test_is_native_pdf_with_scanned_content():
    """测试扫描件 PDF 被正确识别"""
    from pdf_processor import PDFProcessor

    processor = PDFProcessor(
        text_density_threshold=0.0001,
        pages_for_classification=2
    )

    # 使用测试数据目录中已知为扫描件的 PDF
    # 银行明细对账单通常是扫描件
    test_pdf = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "农业银行12月明细对账单.pdf")
    if os.path.exists(test_pdf):
        result = processor._is_native_pdf(test_pdf)
        assert result == False


def test_process_native_pdf():
    """测试处理原生 PDF 的完整流程"""
    from pdf_processor import PDFProcessor

    processor = PDFProcessor(
        text_density_threshold=0.0001,
        pages_for_classification=2
    )

    test_pdf = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "增值税及附加税费申报表（一般纳税人适用）-给力.pdf")
    if os.path.exists(test_pdf):
        result = processor.process(test_pdf)

        assert result["pdf_type"] == "native"
        assert isinstance(result["content"], str)
        assert len(result["content"]) > 0
        assert result["pages_processed"] == 2


def test_process_scanned_pdf():
    """测试处理扫描件的完整流程"""
    from pdf_processor import PDFProcessor

    processor = PDFProcessor(
        text_density_threshold=0.0001,
        pages_for_classification=2
    )

    test_pdf = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "农业银行12月明细对账单.pdf")
    if os.path.exists(test_pdf):
        result = processor.process(test_pdf)

        assert result["pdf_type"] == "scanned"
        assert isinstance(result["content"], list)
        assert len(result["content"]) > 0
        # base64 字符串应非空
        assert all(len(img) > 0 for img in result["content"])
        assert result["pages_processed"] == 2
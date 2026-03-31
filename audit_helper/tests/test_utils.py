import pytest
import os
from pathlib import Path


def test_load_config_missing_file():
    """测试配置文件不存在时抛出异常"""
    from utils import load_config

    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.env")


def test_load_config_missing_required_key():
    """测试缺少必填配置项时抛出异常"""
    from utils import load_config
    import tempfile

    # 创建临时配置文件，缺少 API_KEY
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("BASE_URL=https://api.openai.com/v1\n")
        f.write("MODEL_NAME=gpt-4o\n")
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="API_KEY"):
            load_config(temp_path)
    finally:
        os.unlink(temp_path)


def test_scan_pdf_files_empty_dir():
    """测试空目录返回空列表"""
    from utils import scan_pdf_files
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        result = scan_pdf_files(temp_dir)
        assert result == []


def test_scan_pdf_files_with_pdfs():
    """测试目录包含 PDF 文件"""
    from utils import scan_pdf_files
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建假的 PDF 文件
        Path(os.path.join(temp_dir, "test1.pdf")).touch()
        Path(os.path.join(temp_dir, "test2.pdf")).touch()
        Path(os.path.join(temp_dir, "ignore.txt")).touch()

        result = scan_pdf_files(temp_dir)
        assert len(result) == 2
        assert all(f.endswith(".pdf") for f in result)


import json


def test_write_json_output():
    """测试 JSON 输出功能"""
    from utils import write_json_output
    import tempfile

    test_data = {
        "processing_time": "2026-03-31T16:00:00",
        "total_files": 2,
        "results": [
            {"filename": "test.pdf", "category": "房租合同"}
        ]
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = os.path.join(temp_dir, "result.json")
        write_json_output(test_data, output_path)

        # 验证文件存在
        assert os.path.exists(output_path)

        # 验证内容正确
        with open(output_path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        assert loaded == test_data
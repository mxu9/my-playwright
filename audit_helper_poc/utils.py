# audit_helper_poc/utils.py
"""工具函数模块"""
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import dotenv_values


def load_config(config_path: str) -> dict:
    """
    从 .env 文件加载配置。

    Args:
        config_path: 配置文件路径

    Returns:
        dict: 配置字典
    """
    return dict(dotenv_values(config_path))


def scan_pdf_files(directory: str) -> list[str]:
    """
    扫描目录下的 PDF 文件。

    Args:
        directory: 目录路径

    Returns:
        list[str]: PDF 文件路径列表（排序后）
    """
    pdf_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))
    return sorted(pdf_files)


def write_json_output(data: dict, output_path: str) -> None:
    """
    写入 JSON 输出文件。

    Args:
        data: 数据字典
        output_path: 输出文件路径
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json_file(file_path: str) -> dict:
    """
    读取 JSON 文件。

    Args:
        file_path: 文件路径

    Returns:
        dict: JSON 数据
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_current_timestamp() -> str:
    """
    获取当前时间戳（ISO 格式）。

    Returns:
        str: ISO 格式时间戳
    """
    return datetime.now().isoformat()
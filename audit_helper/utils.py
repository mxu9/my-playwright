"""
审计助手工具函数模块
"""
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import dotenv_values


REQUIRED_CONFIG_KEYS = ["API_KEY", "BASE_URL", "MODEL_NAME"]

DEFAULT_CONFIG = {
    "TEXT_DENSITY_THRESHOLD": 0.01,
    "PAGES_FOR_CLASSIFICATION": 2,
    "OUTPUT_DIR": "output",
    "OUTPUT_FILENAME": "classification_result.json",
}


def load_config(config_path: str) -> dict:
    """
    加载配置文件

    Args:
        config_path: .env 配置文件路径

    Returns:
        配置字典

    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 缺少必填配置项
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    # 直接从文件读取配置，不影响全局环境变量
    env_values = dotenv_values(config_path)

    config = {}

    # 检查必填项
    for key in REQUIRED_CONFIG_KEYS:
        value = env_values.get(key)
        if not value:
            raise ValueError(f"缺少必填配置项: {key}")
        config[key] = value

    # 加载可选项（使用默认值）
    for key, default_value in DEFAULT_CONFIG.items():
        value = env_values.get(key)
        if value is not None:
            # 尝试转换类型
            if isinstance(default_value, float):
                config[key] = float(value)
            elif isinstance(default_value, int):
                config[key] = int(value)
            else:
                config[key] = value
        else:
            config[key] = default_value

    return config


def scan_pdf_files(directory: str) -> list[str]:
    """
    扫描目录中的所有 PDF 文件

    Args:
        directory: 目录路径

    Returns:
        PDF 文件路径列表（按文件名排序）
    """
    pdf_files = []
    directory_path = Path(directory)

    if not directory_path.exists():
        return pdf_files

    for file_path in directory_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() == ".pdf":
            pdf_files.append(str(file_path))

    # 按文件名排序
    pdf_files.sort(key=lambda x: Path(x).name)
    return pdf_files


def write_json_output(data: dict, output_path: str) -> None:
    """
    将数据写入 JSON 文件

    Args:
        data: 要写入的数据字典
        output_path: 输出文件路径
    """
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_current_timestamp() -> str:
    """
    获取当前时间戳（ISO 格式）

    Returns:
        ISO 格式时间字符串
    """
    return datetime.now().isoformat()
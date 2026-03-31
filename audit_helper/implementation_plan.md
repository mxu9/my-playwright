# 审计助手 PDF 分类模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 PDF 分类模块，自动判断 PDF 类型（原生/扫描件）并进行分类，输出汇总 JSON 结果。

**Architecture:** 采用分层架构：utils（工具层）→ pdf_processor（PDF处理层）→ llm_client（LLM调用层）→ classifier（协调层）。从底层向上逐层构建，每层独立可测。

**Tech Stack:** langchain 1.0.3, langchain-openai, pdfplumber, pdf2image, Pillow, python-dotenv

---

## 文件结构

| 文件 | 负责 |
|------|------|
| `audit_helper/utils.py` | 配置加载、文件遍历、JSON输出 |
| `audit_helper/pdf_processor.py` | PDF类型判断、内容提取 |
| `audit_helper/llm_client.py` | LLM调用封装、分类逻辑 |
| `audit_helper/classifier.py` | 主入口、流程协调 |
| `audit_helper/__init__.py` | 模块导出 |
| `audit_helper/requirements.txt` | 依赖清单 |
| `audit_helper/tests/test_utils.py` | utils 单元测试 |
| `audit_helper/tests/test_pdf_processor.py` | pdf_processor 单元测试 |
| `audit_helper/tests/test_llm_client.py` | llm_client 单元测试 |
| `audit_helper/tests/test_classifier.py` | classifier 集成测试 |

---

## Task 1: 配置与工具函数 (utils.py)

**Files:**
- Create: `audit_helper/utils.py`
- Create: `audit_helper/tests/test_utils.py`

### Step 1: 创建测试目录结构

```bash
mkdir -p audit_helper/tests
touch audit_helper/tests/__init__.py
```

### Step 2: 写配置加载的失败测试

**File:** `audit_helper/tests/test_utils.py`

```python
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
```

### Step 3: 运行测试确认失败

```bash
cd audit_helper && python -m pytest tests/test_utils.py::test_load_config_missing_file -v
```

Expected: FAIL - `ModuleNotFoundError: No module named 'utils'`

### Step 4: 实现配置加载函数

**File:** `audit_helper/utils.py`

```python
"""
审计助手工具函数模块
"""
import os
from pathlib import Path
from typing import dict
from dotenv import load_dotenv


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

    load_dotenv(config_path)

    config = {}

    # 检查必填项
    for key in REQUIRED_CONFIG_KEYS:
        value = os.getenv(key)
        if not value:
            raise ValueError(f"缺少必填配置项: {key}")
        config[key] = value

    # 加载可选项（使用默认值）
    for key, default_value in DEFAULT_CONFIG.items():
        value = os.getenv(key)
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
```

### Step 5: 运行测试确认通过

```bash
cd audit_helper && python -m pytest tests/test_utils.py::test_load_config_missing_file tests/test_utils.py::test_load_config_missing_required_key -v
```

Expected: PASS

### Step 6: 写文件遍历的测试

**File:** `audit_helper/tests/test_utils.py`（追加）

```python
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
```

### Step 7: 运行测试确认失败

```bash
cd audit_helper && python -m pytest tests/test_utils.py::test_scan_pdf_files_empty_dir -v
```

Expected: FAIL - `AttributeError: module 'utils' has no attribute 'scan_pdf_files'`

### Step 8: 实现文件遍历函数

**File:** `audit_helper/utils.py`（追加）

```python
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
```

### Step 9: 运行测试确认通过

```bash
cd audit_helper && python -m pytest tests/test_utils.py::test_scan_pdf_files_empty_dir tests/test_utils.py::test_scan_pdf_files_with_pdfs -v
```

Expected: PASS

### Step 10: 写 JSON 输出的测试

**File:** `audit_helper/tests/test_utils.py`（追加）

```python
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
```

### Step 11: 运行测试确认失败

```bash
cd audit_helper && python -m pytest tests/test_utils.py::test_write_json_output -v
```

Expected: FAIL - `AttributeError: module 'utils' has no attribute 'write_json_output'`

### Step 12: 实现 JSON 输出函数

**File:** `audit_helper/utils.py`（追加）

```python
import json
from datetime import datetime


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
```

### Step 13: 运行测试确认通过

```bash
cd audit_helper && python -m pytest tests/test_utils.py::test_write_json_output -v
```

Expected: PASS

### Step 14: 提交

```bash
git add audit_helper/utils.py audit_helper/tests/test_utils.py audit_helper/tests/__init__.py
git commit -m "feat(audit_helper): add utils module with config loading, file scanning, and JSON output"

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## Task 2: PDF 处理器 (pdf_processor.py)

**Files:**
- Create: `audit_helper/pdf_processor.py`
- Create: `audit_helper/tests/test_pdf_processor.py`

### Step 1: 写 PDF 类型判断的测试

**File:** `audit_helper/tests/test_pdf_processor.py`

```python
import pytest
import os
from pathlib import Path


def test_is_native_pdf_with_text_content():
    """测试原生 PDF（含文本）被正确识别"""
    from pdf_processor import PDFProcessor

    processor = PDFProcessor(
        text_density_threshold=0.01,
        pages_for_classification=2
    )

    # 使用测试数据目录中已知为原生的 PDF
    # 增值税申报表通常是原生 PDF
    test_pdf = "data/增值税及附加税费申报表（一般纳税人适用）-给力.pdf"
    if os.path.exists(test_pdf):
        result = processor._is_native_pdf(test_pdf)
        assert result == True


def test_is_native_pdf_with_scanned_content():
    """测试扫描件 PDF 被正确识别"""
    from pdf_processor import PDFProcessor

    processor = PDFProcessor(
        text_density_threshold=0.01,
        pages_for_classification=2
    )

    # 使用测试数据目录中已知为扫描件的 PDF
    # 银行明细对账单通常是扫描件
    test_pdf = "data/农业银行12月明细对账单.pdf"
    if os.path.exists(test_pdf):
        result = processor._is_native_pdf(test_pdf)
        assert result == False
```

### Step 2: 运行测试确认失败

```bash
cd audit_helper && python -m pytest tests/test_pdf_processor.py -v
```

Expected: FAIL - `ModuleNotFoundError: No module named 'pdf_processor'`

### Step 3: 实现 PDFProcessor 类骨架

**File:** `audit_helper/pdf_processor.py`

```python
"""
PDF 处理模块：类型判断与内容提取
"""
import os
import base64
import pdfplumber
from pdf2image import convert_from_path
from typing import Literal


class PDFProcessor:
    """PDF 处理器：判断类型并提取内容"""

    def __init__(
        self,
        text_density_threshold: float = 0.01,
        pages_for_classification: int = 2
    ):
        """
        初始化 PDF 处理器

        Args:
            text_density_threshold: 文本密度阈值，低于此值判定为扫描件
            pages_for_classification: 用于分类的前 N 页
        """
        self.text_density_threshold = text_density_threshold
        self.pages_for_classification = pages_for_classification

    def process(self, pdf_path: str) -> dict:
        """
        处理 PDF 文件，判断类型并提取内容

        Args:
            pdf_path: PDF 文件路径

        Returns:
            {
                "pdf_type": "native" | "scanned",
                "content": str | list[str],
                "pages_processed": int
            }
        """
        is_native = self._is_native_pdf(pdf_path)

        if is_native:
            content = self._extract_text(pdf_path, self.pages_for_classification)
            pdf_type = "native"
        else:
            content = self._extract_images(pdf_path, self.pages_for_classification)
            pdf_type = "scanned"

        return {
            "pdf_type": pdf_type,
            "content": content,
            "pages_processed": self.pages_for_classification
        }

    def _is_native_pdf(self, pdf_path: str) -> bool:
        """
        判断是否为原生 PDF

        Args:
            pdf_path: PDF 文件路径

        Returns:
            True 表示原生 PDF，False 表示扫描件
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_chars = 0
                total_area = 0

                # 检查前 N 页
                pages_to_check = min(self.pages_for_classification, len(pdf.pages))

                for i in range(pages_to_check):
                    page = pdf.pages[i]
                    text = page.extract_text() or ""
                    total_chars += len(text)

                    # 页面面积（像素单位）
                    width = page.width
                    height = page.height
                    total_area += width * height

                if total_area == 0:
                    return False

                # 文本密度计算
                density = total_chars / total_area

                return density >= self.text_density_threshold

        except Exception as e:
            # 无法打开或处理，默认视为扫描件
            print(f"处理 PDF 时出错: {e}")
            return False

    def _extract_text(self, pdf_path: str, pages: int) -> str:
        """
        从原生 PDF 提取文本内容

        Args:
            pdf_path: PDF 文件路径
            pages: 提取的页数

        Returns:
            提取的文本内容
        """
        text_content = []

        with pdfplumber.open(pdf_path) as pdf:
            pages_to_extract = min(pages, len(pdf.pages))

            for i in range(pages_to_extract):
                page = pdf.pages[i]
                text = page.extract_text() or ""
                text_content.append(text)

        return "\n\n".join(text_content)

    def _extract_images(self, pdf_path: str, pages: int) -> list[str]:
        """
        将扫描件 PDF 转为图片并返回 base64 编码列表

        Args:
            pdf_path: PDF 文件路径
            pages: 转换的页数

        Returns:
            base64 编码的图片列表
        """
        images = convert_from_path(
            pdf_path,
            first_page=1,
            last_page=pages,
            dpi=200  # 适中的 DPI，平衡清晰度和大小
        )

        base64_images = []
        for img in images:
            # 转为 base64
            from io import BytesIO
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            base64_images.append(img_base64)

        return base64_images
```

### Step 4: 运行测试确认通过

```bash
cd audit_helper && python -m pytest tests/test_pdf_processor.py -v
```

Expected: PASS（如果测试 PDF 存在）

### Step 5: 写 process 方法的集成测试

**File:** `audit_helper/tests/test_pdf_processor.py`（追加）

```python
def test_process_native_pdf():
    """测试处理原生 PDF 的完整流程"""
    from pdf_processor import PDFProcessor

    processor = PDFProcessor(
        text_density_threshold=0.01,
        pages_for_classification=2
    )

    test_pdf = "data/增值税及附加税费申报表（一般纳税人适用）-给力.pdf"
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
        text_density_threshold=0.01,
        pages_for_classification=2
    )

    test_pdf = "data/农业银行12月明细对账单.pdf"
    if os.path.exists(test_pdf):
        result = processor.process(test_pdf)

        assert result["pdf_type"] == "scanned"
        assert isinstance(result["content"], list)
        assert len(result["content"]) > 0
        # base64 字符串应非空
        assert all(len(img) > 0 for img in result["content"])
        assert result["pages_processed"] == 2
```

### Step 6: 运行测试确认通过

```bash
cd audit_helper && python -m pytest tests/test_pdf_processor.py -v
```

Expected: PASS

### Step 7: 提交

```bash
git add audit_helper/pdf_processor.py audit_helper/tests/test_pdf_processor.py
git commit -m "feat(audit_helper): add PDF processor with type detection and content extraction"

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## Task 3: LLM 客户端 (llm_client.py)

**Files:**
- Create: `audit_helper/llm_client.py`
- Create: `audit_helper/tests/test_llm_client.py`

### Step 1: 写 LLM 客户端初始化测试

**File:** `audit_helper/tests/test_llm_client.py`

```python
import pytest


def test_llm_client_initialization():
    """测试 LLM 客户端初始化"""
    from llm_client import LLMClient

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
```

### Step 2: 运行测试确认失败

```bash
cd audit_helper && python -m pytest tests/test_llm_client.py::test_llm_client_initialization -v
```

Expected: FAIL - `ModuleNotFoundError: No module named 'llm_client'`

### Step 3: 实现 LLMClient 类初始化

**File:** `audit_helper/llm_client.py`

```python
"""
LLM 客户端模块：封装 langchain_openai 调用
"""
import json
from typing import dict
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


# PDF 类别枚举
PDF_CATEGORIES = [
    "房租合同",
    "增值税纳税申报表",
    "企业所得税纳税申报表",
    "财务报表",
    "天眼查信息",
    "银行询证函",
    "银行明细对账单",
    "银行余额对账单",
    "其他",
]


class LLMClient:
    """LLM 客户端：调用大模型进行 PDF 分类"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str
    ):
        """
        初始化 LLM 客户端

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model_name: 模型名称

        Raises:
            ValueError: 配置无效
        """
        if not api_key:
            raise ValueError("API_KEY 不能为空")

        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

        # 初始化 langchain 客户端
        self.client = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=0.1  # 低温度，更稳定的输出
        )
```

### Step 4: 运行测试确认通过

```bash
cd audit_helper && python -m pytest tests/test_llm_client.py::test_llm_client_initialization tests/test_llm_client.py::test_llm_client_invalid_config -v
```

Expected: PASS

### Step 5: 写分类函数的测试（模拟 LLM）

**File:** `audit_helper/tests/test_llm_client.py`（追加）

```python
from unittest.mock import Mock, patch


def test_classify_text_content():
    """测试文本内容分类（模拟 LLM 响应）"""
    from llm_client import LLMClient

    client = LLMClient(
        api_key="test_key",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o"
    )

    # 模拟 LLM 响应
    mock_response = Mock()
    mock_response.content = '{"category": "增值税纳税申报表", "confidence": 0.95}'

    with patch.object(client.client, 'invoke', return_value=mock_response):
        result = client.classify("这是一份增值税申报表...", "native")

        assert result["category"] == "增值税纳税申报表"
        assert result["confidence"] == 0.95


def test_classify_image_content():
    """测试图片内容分类（模拟 LLM 响应）"""
    from llm_client import LLMClient

    client = LLMClient(
        api_key="test_key",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o"
    )

    # 模拟 LLM 响应
    mock_response = Mock()
    mock_response.content = '{"category": "银行明细对账单", "confidence": 0.88}'

    with patch.object(client.client, 'invoke', return_value=mock_response):
        result = client.classify(["base64_image_data"], "scanned")

        assert result["category"] == "银行明细对账单"
        assert result["confidence"] == 0.88
```

### Step 6: 运行测试确认失败

```bash
cd audit_helper && python -m pytest tests/test_llm_client.py::test_classify_text_content -v
```

Expected: FAIL - `AttributeError: 'LLMClient' object has no attribute 'classify'`

### Step 7: 实现分类函数

**File:** `audit_helper/llm_client.py`（追加）

```python
    def classify(self, content: str | list[str], pdf_type: str) -> dict:
        """
        分类 PDF 内容

        Args:
            content: 文本内容（原生PDF）或 base64 图片列表（扫描件）
            pdf_type: "native" 或 "scanned"

        Returns:
            {"category": str, "confidence": float}
        """
        system_prompt = self._build_system_prompt()

        if pdf_type == "native":
            # 文本分类
            user_message = HumanMessage(
                content=f"请分析以下 PDF 文档内容并分类：\n\n{content}"
            )
        else:
            # 多模态图片分类
            images_content = []
            for img_base64 in content:
                images_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}"
                    }
                })
            # 添加文字提示
            images_content.append({
                "type": "text",
                "text": "请分析以上 PDF 文档图片并分类。"
            })
            user_message = HumanMessage(content=images_content)

        messages = [
            SystemMessage(content=system_prompt),
            user_message
        ]

        response = self.client.invoke(messages)

        # 解析响应
        return self._parse_response(response.content)

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        categories_str = ", ".join(PDF_CATEGORIES)
        return f"""你是一个审计文档分类助手。请根据文档内容判断其类型。

可选的文档类型：
{categories_str}

请返回 JSON 格式的结果：
{{"category": "文档类型", "confidence": 0.0-1.0}}

注意：
1. category 必须是上述类型之一
2. confidence 是置信度，范围 0.0 到 1.0
3. 只返回 JSON，不要其他内容"""

    def _parse_response(self, response_text: str) -> dict:
        """解析 LLM 响应"""
        try:
            # 尝试直接解析 JSON
            result = json.loads(response_text)
            return {
                "category": result.get("category", "其他"),
                "confidence": float(result.get("confidence", 0.5))
            }
        except json.JSONDecodeError:
            # 尝试提取 JSON
            import re
            json_match = re.search(r'\{.*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "category": result.get("category", "其他"),
                    "confidence": float(result.get("confidence", 0.5))
                }
            # 默认返回
            return {"category": "其他", "confidence": 0.0}
```

### Step 8: 运行测试确认通过

```bash
cd audit_helper && python -m pytest tests/test_llm_client.py -v
```

Expected: PASS

### Step 9: 提交

```bash
git add audit_helper/llm_client.py audit_helper/tests/test_llm_client.py
git commit -m "feat(audit_helper): add LLM client with classification capability"

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## Task 4: 分类器主入口 (classifier.py)

**Files:**
- Create: `audit_helper/classifier.py`
- Create: `audit_helper/tests/test_classifier.py`

### Step 1: 写分类器初始化测试

**File:** `audit_helper/tests/test_classifier.py`

```python
import pytest
import os
import tempfile


def test_classifier_initialization():
    """测试分类器初始化"""
    from classifier import PDFClassifier

    # 创建临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("API_KEY=test_key\n")
        f.write("BASE_URL=https://api.openai.com/v1\n")
        f.write("MODEL_NAME=gpt-4o\n")
        f.write("TEXT_DENSITY_THRESHOLD=0.01\n")
        f.write("PAGES_FOR_CLASSIFICATION=2\n")
        f.write("OUTPUT_DIR=output\n")
        f.write("OUTPUT_FILENAME=result.json\n")
        temp_path = f.name

    try:
        classifier = PDFClassifier(config_path=temp_path)

        assert classifier.config["API_KEY"] == "test_key"
        assert classifier.config["TEXT_DENSITY_THRESHOLD"] == 0.01
    finally:
        os.unlink(temp_path)
```

### Step 2: 运行测试确认失败

```bash
cd audit_helper && python -m pytest tests/test_classifier.py::test_classifier_initialization -v
```

Expected: FAIL - `ModuleNotFoundError: No module named 'classifier'`

### Step 3: 实现 PDFClassifier 类初始化

**File:** `audit_helper/classifier.py`

```python
"""
PDF 分类器主模块：协调各组件完成分类流程
"""
import os
from pathlib import Path
from typing import dict

from utils import load_config, scan_pdf_files, write_json_output, get_current_timestamp
from pdf_processor import PDFProcessor
from llm_client import LLMClient


class PDFClassifier:
    """PDF 分类器：主入口类"""

    def __init__(self, config_path: str = ".env"):
        """
        初始化分类器

        Args:
            config_path: 配置文件路径
        """
        # 获取配置文件绝对路径
        if not os.path.isabs(config_path):
            # 相对于当前文件所在目录
            base_dir = Path(__file__).parent
            config_path = str(base_dir / config_path)

        self.config = load_config(config_path)
        self.config_path = config_path

        # 初始化组件
        self.pdf_processor = PDFProcessor(
            text_density_threshold=self.config["TEXT_DENSITY_THRESHOLD"],
            pages_for_classification=self.config["PAGES_FOR_CLASSIFICATION"]
        )

        self.llm_client = LLMClient(
            api_key=self.config["API_KEY"],
            base_url=self.config["BASE_URL"],
            model_name=self.config["MODEL_NAME"]
        )
```

### Step 4: 运行测试确认通过

```bash
cd audit_helper && python -m pytest tests/test_classifier.py::test_classifier_initialization -v
```

Expected: PASS

### Step 5: 写 run 方法的测试（模拟组件）

**File:** `audit_helper/tests/test_classifier.py`（追加）

```python
from unittest.mock import Mock, patch, MagicMock


def test_run_classify_pdfs():
    """测试完整分类流程（模拟组件）"""
    from classifier import PDFClassifier
    import tempfile

    # 创建临时配置
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("API_KEY=test_key\n")
        f.write("BASE_URL=https://api.openai.com/v1\n")
        f.write("MODEL_NAME=gpt-4o\n")
        f.write("TEXT_DENSITY_THRESHOLD=0.01\n")
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
    import tempfile

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
```

### Step 6: 运行测试确认失败

```bash
cd audit_helper && python -m pytest tests/test_classifier.py::test_run_classify_pdfs -v
```

Expected: FAIL - `AttributeError: 'PDFClassifier' object has no attribute 'run'`

### Step 7: 实现 run 和 classify_single 方法

**File:** `audit_helper/classifier.py`（追加）

```python
    def run(self, input_dir: str = "data", output_dir: str = None) -> dict:
        """
        执行分类流程

        Args:
            input_dir: 输入 PDF 目录
            output_dir: 输出目录（默认使用配置中的 OUTPUT_DIR）

        Returns:
            分类结果字典
        """
        # 处理路径
        if not os.path.isabs(input_dir):
            base_dir = Path(__file__).parent
            input_dir = str(base_dir / input_dir)

        if output_dir is None:
            output_dir = self.config["OUTPUT_DIR"]

        if not os.path.isabs(output_dir):
            base_dir = Path(__file__).parent
            output_dir = str(base_dir / output_dir)

        # 扫描 PDF 文件
        pdf_files = scan_pdf_files(input_dir)

        # 分类每个文件
        results = []
        for pdf_path in pdf_files:
            try:
                result = self.classify_single(pdf_path)
                results.append(result)
            except Exception as e:
                # 记录失败的文件
                results.append({
                    "filename": Path(pdf_path).name,
                    "file_path": pdf_path,
                    "error": str(e),
                    "category": "其他",
                    "confidence": 0.0
                })

        # 生成汇总
        summary = self._generate_summary(results)

        # 构建完整结果
        full_result = {
            "processing_time": get_current_timestamp(),
            "total_files": len(pdf_files),
            "results": results,
            "summary": summary
        }

        # 写入输出文件
        output_path = os.path.join(output_dir, self.config["OUTPUT_FILENAME"])
        write_json_output(full_result, output_path)

        return full_result

    def classify_single(self, pdf_path: str) -> dict:
        """
        分类单个 PDF 文件

        Args:
            pdf_path: PDF 文件路径

        Returns:
            分类结果
        """
        filename = Path(pdf_path).name

        # PDF 处理
        processed = self.pdf_processor.process(pdf_path)

        # LLM 分类
        classified = self.llm_client.classify(
            content=processed["content"],
            pdf_type=processed["pdf_type"]
        )

        return {
            "filename": filename,
            "file_path": pdf_path,
            "pdf_type": processed["pdf_type"],
            "category": classified["category"],
            "confidence": classified["confidence"],
            "pages_processed": processed["pages_processed"]
        }

    def _generate_summary(self, results: list[dict]) -> dict:
        """生成汇总统计"""
        native_count = sum(1 for r in results if r.get("pdf_type") == "native")
        scanned_count = sum(1 for r in results if r.get("pdf_type") == "scanned")

        # 类别分布
        category_distribution = {}
        for r in results:
            category = r.get("category", "其他")
            category_distribution[category] = category_distribution.get(category, 0) + 1

        return {
            "native_count": native_count,
            "scanned_count": scanned_count,
            "category_distribution": category_distribution
        }
```

### Step 8: 运行测试确认通过

```bash
cd audit_helper && python -m pytest tests/test_classifier.py -v
```

Expected: PASS

### Step 9: 提交

```bash
git add audit_helper/classifier.py audit_helper/tests/test_classifier.py
git commit -m "feat(audit_helper): add PDFClassifier main entry with run and classify_single methods"

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## Task 5: 模块导出与依赖清单

**Files:**
- Create: `audit_helper/__init__.py`
- Create: `audit_helper/requirements.txt`

### Step 1: 创建模块导出

**File:** `audit_helper/__init__.py`

```python
"""
审计助手模块

用于处理审计相关 PDF 文件，自动分类并提取信息。
"""

from classifier import PDFClassifier
from pdf_processor import PDFProcessor
from llm_client import LLMClient
from utils import load_config, scan_pdf_files, write_json_output

__version__ = "0.1.0"

__all__ = [
    "PDFClassifier",
    "PDFProcessor",
    "LLMClient",
    "load_config",
    "scan_pdf_files",
    "write_json_output",
]
```

### Step 2: 创建依赖清单

**File:** `audit_helper/requirements.txt`

```txt
# LangChain 核心包
langchain>=1.0.3
langchain-core>=1.0.3
langchain-openai>=1.0.2

# PDF 处理
pdfplumber>=0.10.0
pdf2image>=1.16.0

# 图片处理
Pillow>=10.0.0

# 配置加载
python-dotenv>=1.0.0
```

### Step 3: 提交

```bash
git add audit_helper/__init__.py audit_helper/requirements.txt
git commit -m "feat(audit_helper): add module exports and requirements.txt"

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## Task 6: 集成测试与验证

**Files:**
- Run: 使用 data 目录中的真实 PDF 进行测试

### Step 1: 更新 .env 配置

确保 `audit_helper/.env` 包含正确的 API 配置：

```env
# -------------------
# 多模态大模型 配置
# -------------------
API_KEY=sk-or-v1-xxx
BASE_URL=https://openrouter.ai/api/v1
MODEL_NAME=openai/gpt-4o

# -------------------
# PDF 处理参数
# -------------------
TEXT_DENSITY_THRESHOLD=0.01
PAGES_FOR_CLASSIFICATION=2

# -------------------
# 输出配置
# -------------------
OUTPUT_DIR=output
OUTPUT_FILENAME=classification_result.json
```

### Step 2: 运行集成测试脚本

**创建临时测试脚本:** `audit_helper/test_integration.py`

```python
#!/usr/bin/env python
"""集成测试：使用真实 PDF 进行分类"""

import os
import sys

# 确保能导入模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from classifier import PDFClassifier


def main():
    print("开始集成测试...")

    classifier = PDFClassifier(config_path=".env")

    print("配置加载成功:")
    print(f"  - 模型: {classifier.config['MODEL_NAME']}")
    print(f"  - 文本密度阈值: {classifier.config['TEXT_DENSITY_THRESHOLD']}")
    print(f"  - 分类页数: {classifier.config['PAGES_FOR_CLASSIFICATION']}")

    print("\n开始分类 data 目录中的 PDF...")

    result = classifier.run(input_dir="data")

    print(f"\n处理完成！共 {result['total_files']} 个文件")

    print("\n分类结果:")
    for r in result["results"]:
        print(f"  - {r['filename']}: {r['category']} (置信度: {r['confidence']}, 类型: {r['pdf_type']})")

    print("\n汇总统计:")
    print(f"  - 原生PDF: {result['summary']['native_count']}")
    print(f"  - 扫描件: {result['summary']['scanned_count']}")
    print(f"  - 类别分布: {result['summary']['category_distribution']}")

    print(f"\n结果已保存到: {classifier.config['OUTPUT_DIR']}/{classifier.config['OUTPUT_FILENAME']}")


if __name__ == "__main__":
    main()
```

### Step 3: 运行集成测试

```bash
cd audit_helper && python test_integration.py
```

Expected: 成功分类所有 PDF，输出 JSON 结果

### Step 4: 检查输出文件

```bash
cat audit_helper/output/classification_result.json
```

验证 JSON 格式正确，内容符合设计文档规范。

### Step 5: 删除临时测试脚本并提交

```bash
rm audit_helper/test_integration.py
git add audit_helper/output/.gitkeep  # 如果需要保留输出目录
git commit -m "test(audit_helper): verify integration test passes with real PDFs"

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## Self-Review Checklist

**已完成 Spec 覆盖检查：**
- [x] PDF 类型判断（原生/扫描件）→ Task 2: pdf_processor.py
- [x] 内容提取（文本/图片）→ Task 2: pdf_processor.py
- [x] LLM 分类调用 → Task 3: llm_client.py
- [x] 主流程协调 → Task 4: classifier.py
- [x] 配置加载 → Task 1: utils.py
- [x] 文件遍历 → Task 1: utils.py
- [x] JSON 输出 → Task 1: utils.py
- [x] 模块导出 → Task 5: __init__.py
- [x] 集成验证 → Task 6

**无 Placeholder：**
- 所有代码步骤包含完整实现代码
- 所有测试包含完整测试代码
- 所有命令包含预期输出说明

**类型一致性：**
- `PDFProcessor.process()` 返回 `{pdf_type, content, pages_processed}` 在所有引用处一致
- `LLMClient.classify()` 返回 `{category, confidence}` 在所有引用处一致
- `PDFClassifier.run()` 返回完整 JSON 结构符合设计文档规范
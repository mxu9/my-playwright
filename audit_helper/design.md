# 审计助手 PDF 分类模块设计文档

> 创建日期: 2026-03-31

## 1. 概述

### 1.1 项目背景

审计助手是一个用于处理审计相关 PDF 文件的模块，需要从各类文档中提取结构化信息。第一阶段重点实现 PDF 文件的类型判断与分类功能。

### 1.2 目标

- 自动判断 PDF 是原生文件还是扫描件
- 对 PDF 进行分类识别（房租合同、纳税申报表、银行对账单等）
- 输出汇总的 JSON 格式分类结果

### 1.3 范围

**第一阶段包含：**
- PDF 类型判断（原生/扫描件）
- PDF 内容提取
- PDF 分类
- 结果输出

**第二阶段（不在本次范围）：**
- 针对不同类型 PDF 的结构化信息提取

---

## 2. PDF 文件类型

支持的 PDF 类别：

| 类别 | 说明 |
|------|------|
| 房租合同 | 房屋租赁相关合同文件 |
| 增值税纳税申报表 | 增值税及附加税费申报表 |
| 企业所得税纳税申报表 | 居民企业企业所得税申报表 |
| 财务报表 | 财务报表报送与信息采集 |
| 天眼查信息 | 企业工商信息查询结果 |
| 银行询证函 | 银行出具的询证函 |
| 银行明细对账单 | 银行账户明细流水 |
| 银行余额对账单 | 银行账户余额证明 |
| 其他 | 无法识别的类型 |

---

## 3. 技术方案

### 3.1 判断原生/扫描件

**方法：文本密度检测**

使用 `pdfplumber` 打开 PDF，检测前 N 页的文本密度：

```
文本密度 = 提取的文本字符数 / 页面像素面积 × 1000
```

实际计算方式：统计提取的文本字符数与页面宽×高的比值，乘以常数因子归一化。典型原生 PDF 的文本密度通常在 0.05-0.5 范围，扫描件通常接近 0（因为无法提取文本）。

- 若文本密度 ≥ 阈值 → 原生 PDF
- 若文本密度 < 阈值 → 扫描件

**阈值与页数可配置：**
- `TEXT_DENSITY_THRESHOLD`：默认 0.01
- `PAGES_FOR_CLASSIFICATION`：默认 2

### 3.2 内容提取

| PDF 类型 | 提取方式 |
|----------|----------|
| 原生 PDF | pdfplumber 直接提取文本内容 |
| 扫描件 | pdf2image 转为图片 → base64 编码 |

### 3.3 分类识别

使用 langchain_openai 调用多模态大模型：

- 原生 PDF：文本内容送 LLM 分类
- 扫描件：图片 base64 送多模态 LLM 分类

**支持的模型：**
- gpt-4o（推荐）
- gemini-3.1-pro-preview
- glm-4.6v
- kimi-k2.5

所有模型通过 OpenAI 兼容 API 调用，使用 `langchain_openai.ChatOpenAI`。

---

## 4. 模块架构

### 4.1 目录结构

```
audit_helper/
├── __init__.py              # 模块入口，导出主要类
├── classifier.py            # PDF分类器主类
├── pdf_processor.py         # PDF处理：判断原生/扫描件、提取内容
├── llm_client.py            # LLM客户端封装（langchain_openai）
├── utils.py                 # 工具函数：文件遍历、JSON输出等
├── design.md                # 设计文档
├── .env                     # 配置文件
├── data/                    # 输入PDF目录
└── output/                  # 输出结果目录（自动创建）
    └── classification_result.json
```

### 4.2 类设计

#### PDFClassifier（主入口类）

```python
class PDFClassifier:
    """PDF分类器主入口"""
    
    def __init__(self, config_path: str = ".env"):
        """加载配置，初始化各组件"""
    
    def run(self, input_dir: str = "data") -> dict:
        """执行分类流程，返回结果"""
    
    def classify_single(self, pdf_path: str) -> dict:
        """分类单个PDF文件"""
```

#### PDFProcessor（PDF处理类）

```python
class PDFProcessor:
    """PDF处理：类型判断与内容提取"""
    
    def __init__(self, text_density_threshold: float, pages_for_classification: int):
        """初始化参数"""
    
    def process(self, pdf_path: str) -> dict:
        """
        处理PDF文件
        返回: {
            "pdf_type": "native" | "scanned",
            "content": str | list[base64],  # 文本或图片base64列表
            "pages_processed": int
        }
        """
    
    def _is_native_pdf(self, pdf_path: str) -> bool:
        """判断是否为原生PDF"""
    
    def _extract_text(self, pdf_path: str, pages: int) -> str:
        """提取文本内容"""
    
    def _extract_images(self, pdf_path: str, pages: int) -> list[str]:
        """转为图片并返回base64"""
```

#### LLMClient（LLM客户端）

```python
class LLMClient:
    """LLM客户端封装"""
    
    def __init__(self, api_key: str, base_url: str, model_name: str):
        """初始化langchain_openai客户端"""
    
    def classify(self, content: str | list[str], pdf_type: str) -> dict:
        """
        分类PDF内容
        返回: {
            "category": str,
            "confidence": float
        }
        """
```

---

## 5. 处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        PDFClassifier.run()                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. 扫描 input_dir，获取所有 PDF 文件列表                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. 对每个 PDF:                                                  │
│     PDFProcessor.process(pdf_path)                              │
│     ├─ 检测文本密度                                              │
│     ├─ 判断类型：原生/扫描件                                      │
│     ├─ 提取内容：文本或图片base64                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. LLMClient.classify(content, pdf_type)                       │
│     ├─ 原生PDF: 文本 → LLM                                       │
│     ├─ 扫描件: 图片base64 → 多模态LLM                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. 汇总结果，写入 output/classification_result.json            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. 配置

### 6.1 .env 配置项

```env
# -------------------
# 多模态大模型 配置（必填）
# -------------------
API_KEY=your_api_key
BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o

# -------------------
# PDF 处理参数（可选）
# -------------------
TEXT_DENSITY_THRESHOLD=0.01    # 文本密度阈值
PAGES_FOR_CLASSIFICATION=2     # 用于分类的前N页

# -------------------
# 输出配置（可选）
# -------------------
OUTPUT_DIR=output
OUTPUT_FILENAME=classification_result.json
```

---

## 7. 输出格式

### classification_result.json

```json
{
  "processing_time": "2026-03-31T16:00:00",
  "total_files": 8,
  "results": [
    {
      "filename": "房屋租赁合同.pdf",
      "file_path": "data/房屋租赁合同.pdf",
      "pdf_type": "native",
      "category": "房租合同",
      "confidence": 0.95,    // 置信度，范围 0.0-1.0
      "pages_processed": 2
    },
    {
      "filename": "农业银行12月明细对账单.pdf",
      "file_path": "data/农业银行12月明细对账单.pdf",
      "pdf_type": "scanned",
      "category": "银行明细对账单",
      "confidence": 0.88,    // 置信度，范围 0.0-1.0
      "pages_processed": 2
    }
  ],
  "summary": {
    "native_count": 3,
    "scanned_count": 5,
    "category_distribution": {
      "房租合同": 1,
      "增值税纳税申报表": 1,
      "企业所得税纳税申报表": 1,
      "天眼查信息": 1,
      "银行询证函": 1,
      "银行明细对账单": 1,
      "银行余额对账单": 1,
      "财务报表": 1
    }
  }
}
```

---

## 8. 技术依赖

| 库 | 版本 | 用途 |
|---|------|------|
| langchain | 1.0.3 | LLM框架 |
| langchain-openai | latest | OpenAI兼容API调用 |
| pdfplumber | latest | PDF文本提取 |
| pdf2image | latest | PDF转图片 |
| Pillow | latest | 图片处理 |
| python-dotenv | latest | 配置加载 |

---

## 9. 待办事项

- [ ] 实现 `utils.py`：文件遍历、JSON输出
- [ ] 实现 `pdf_processor.py`：PDF处理核心逻辑
- [ ] 实现 `llm_client.py`：LLM客户端封装
- [ ] 实现 `classifier.py`：主入口类
- [ ] 实现 `__init__.py`：模块导出
- [ ] 使用 data 目录中的 PDF 进行测试验证
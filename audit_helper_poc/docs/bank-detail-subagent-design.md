# 银行明细对账单子代理设计文档

> **日期:** 2026-04-02
> **状态:** 待实现

## 概述

实现 `BankDetailSubagent`，从银行明细对账单 PDF 中提取公司信息和月度期末余额。

## 架构

采用两步流程模式（参照 `bank_confirmation_subagent.py`）：

1. **定位阶段**：OCR 扫描全文档 → LLM 定位相关页面
2. **提取阶段**：多模态 LLM 从图片提取结构化数据

```
PDF → OCR全文本 → LLM定位页码 → 转换图片 → 多模态LLM提取 → JSON结果
```

## 输出数据结构

```json
{
  "company_info": {
    "account_name": "明细单所属公司户名 或 null",
    "account_number": "明细单所属账号 或 null"
  },
  "monthly_balances": [
    {"month": "2024-08", "balance": 100000.00},
    {"month": "2024-09", "balance": 120000.00},
    {"month": "2024-10", "balance": 115000.00}
  ],
  "confidence": 0.95
}
```

字段说明：
- `company_info.account_name`: 银行明细单所属公司的户名（通常在页眉）
- `company_info.account_number`: 银行明细单所属账号
- `monthly_balances`: 月度期末余额列表
  - `month`: 月份，格式 `YYYY-MM`
  - `balance`: 该月最后一笔交易后的账户余额
- `confidence`: 置信度（0.0-1.0）

## 信息定位逻辑

银行明细对账单的信息分布特征：

| 信息类型 | 分布特征 | 定位策略 |
|----------|----------|----------|
| 公司信息（户名、账号） | 通常出现在每页页眉 | 定位任意一页即可 |
| 月度期末余额 | 仅出现在该月最后一笔交易的页面 | 需定位所有包含期末余额的页面 |

LLM 定位 Prompt 会引导：
- 如果某页同时包含公司信息和某月期末余额 → 返回该页
- 如果分散在不同页 → 返回所有相关页（合并去重）

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `BANK_DETAIL_WINDOW_SIZE` | 0 | 滑动窗口大小（0=关闭） |
| `TEMPERATURE` | 0.1 | LLM 温度参数（继承） |

配置通过类属性默认值 + 环境变量覆盖：
```python
self._window_size = int(config.get("BANK_DETAIL_WINDOW_SIZE", "0"))
```

## Prompt 设计

### 定位 Prompt

**System Prompt:**
```
你是一个银行对账单索引专家。你的任务是从一份包含多页的银行明细对账单 OCR 文本中，识别出哪些页面包含关键信息。

关键信息定义：
- 公司信息：包含"户名"、"账号"或"账户名称"的页面（通常在页眉）
- 月末余额：包含"余额"字样的交易记录页面，特别关注该月最后一笔交易

输入说明：
文本将以 [PAGE_X_START] 和 [PAGE_X_END] 标识页码。

输出要求：
- 公司信息可能出现在每页页眉，只需定位任意一页
- 月末余额仅出现在该月最后一笔交易的页面
- 如果某页同时包含公司信息和月末余额，只需返回该页
- 如果分散在不同页，返回所有相关页
- 只返回页码列表，格式为 JSON

示例输出：
{"relevant_pages": [1, 3, 5, 8], "reason": "第1页包含公司户名和账号，第3/5/8页分别包含8/9/10月最后一笔交易及余额。"}
```

**User Prompt:**
```
请分析以下银行明细对账单 OCR 文本，找出包含公司信息和月度期末余额的页面页码。

{marked_text}

请返回页码列表（JSON 格式）：
```

### 提取 Prompt

**System Prompt:**
```
你是一位资深的银行审计专家。请直接观察提供的银行明细对账单页面图片，提取结构化数据。

提取准则：
- 公司信息：提取明细单所属公司的户名和账号（通常在页眉）
- 月末余额：识别每个月最后一笔交易后的账户余额
  - 按时间顺序判断最后一笔交易
  - 精确提取余额数值，保留小数位
  - 月份格式为 YYYY-MM

输出格式：
必须返回标准的 JSON 格式：
{
    "company_info": {
        "account_name": "户名 或 null",
        "account_number": "账号 或 null"
    },
    "monthly_balances": [
        {
            "month": "2024-08",
            "balance": 余额数值 或 null
        }
    ],
    "confidence": 0.0-1.0
}

注意：
- 如果某些信息在图片中找不到，对应字段设为 null
- monthly_balances 按月份升序排列
- confidence 表示对提取结果的置信度
- 只返回 JSON，不要其他内容
```

**User Prompt:**
```
请从以上银行明细对账单图片中提取公司信息和月度期末余额。
```

## 核心方法

| 方法 | 功能 | 说明 |
|------|------|------|
| `invoke()` | 主入口 | 协调整个处理流程 |
| `_init_llm_client()` | 初始化 LLM | 读取 TEMPERATURE 配置 |
| `_ocr_pages()` | OCR 处理 | 调用 `pdf_utils.ocr_pdf_pages()` |
| `_locate_pages()` | 定位页面 | 构建 marked_text → 调用 LLM |
| `_parse_pages_response()` | 解析定位响应 | 提取 `relevant_pages` 字段 |
| `_apply_sliding_window()` | 滑动窗口 | 可选，前后扩展页面 |
| `_extract_info()` | 提取信息 | 多模态 LLM → JSON |
| `_create_error_result()` | 错误结果 | 统一错误返回格式 |

## 错误处理

| 场景 | 处理 |
|------|------|
| 未定位到页面 | 返回错误："未能定位到包含关键信息的页面" |
| LLM 未返回有效 JSON | 返回空数据 + confidence=0 |
| PDF 转换失败 | 返回错误："无法将 PDF 转换为图片" |
| OCR 失败 | 返回错误："OCR 处理失败" |

## 文件清单

| 文件 | 操作 |
|------|------|
| `audit_helper_poc/subagents/bank_detail_subagent.py` | 修改（完整实现） |
| `audit_helper_poc/.env.example` | 修改（添加 `BANK_DETAIL_WINDOW_SIZE` 说明） |

## 参考

- `bank_confirmation_subagent.py`: 两步流程模式
- `rent_contract_subagent.py`: 滑动窗口实现
- `pdf_utils.py`: OCR 和图片转换工具
- `llm_utils.py`: LLM 客户端和多模态内容构建
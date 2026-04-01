# audit_helper_poc 框架实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 PDF 处理框架，包含 Planner、BaseSubagent 抽象基类、8 个具体 Subagent 和 Logger 模块，接口先行，使用模拟数据。

**Architecture:** Planner 从 .env 加载配置，维护 subagent 注册表，串行处理 PDF 文件，实时更新 process_result.json。各 subagent 继承 BaseSubagent，实现 invoke 方法返回模拟数据。

**Tech Stack:** Python 3.x, abc (抽象基类), logging, dotenv, pytest

---

## 文件结构

```
audit_helper_poc/
├── __init__.py              # 包入口
├── logger.py                # 日志模块
├── base_subagent.py         # 抽象基类
├── planner.py               # 主控制器
├── utils.py                 # 工具函数
├── subagents/
│   ├── __init__.py          # subagent 注册
│   ├── default_subagent.py
│   ├── rent_contract_subagent.py
│   ├── vat_tax_subagent.py
│   ├── income_tax_subagent.py
│   ├── financial_report_subagent.py
│   ├── tianyancha_subagent.py
│   ├── bank_confirmation_subagent.py
│   ├── bank_detail_subagent.py
│   └── bank_balance_subagent.py
└── tests/
    ├── __init__.py
    ├── test_logger.py
    ├── test_base_subagent.py
    ├── test_subagents.py
    └── test_planner.py
```

---

### Task 1: Logger 模块

**Files:**
- Create: `audit_helper_poc/logger.py`
- Create: `audit_helper_poc/tests/__init__.py`
- Create: `audit_helper_poc/tests/test_logger.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd audit_helper_poc && python -m pytest tests/test_logger.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

- [ ] **Step 3: Write minimal implementation**

```python
# audit_helper_poc/logger.py
import logging


class Logger:
    """日志管理器"""
    
    LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    
    def __init__(self, name: str = "audit_helper_poc", level: str = "INFO"):
        """
        初始化日志器。
        
        Args:
            name: 日志器名称
            level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        """
        self.name = name
        self.level = level
        self._logger = logging.getLogger(name)
        self._logger.setLevel(self.LEVELS.get(level, logging.INFO))
        
        # 如果没有 handler，添加一个
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(self.LEVELS.get(level, logging.INFO))
            formatter = logging.Formatter('[%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
    
    def debug(self, message: str) -> None:
        """输出 DEBUG 级别日志"""
        self._logger.debug(message)
    
    def info(self, message: str) -> None:
        """输出 INFO 级别日志"""
        self._logger.info(message)
    
    def warning(self, message: str) -> None:
        """输出 WARNING 级别日志"""
        self._logger.warning(message)
    
    def error(self, message: str) -> None:
        """输出 ERROR 级别日志"""
        self._logger.error(message)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd audit_helper_poc && python -m pytest tests/test_logger.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add audit_helper_poc/logger.py audit_helper_poc/tests/__init__.py audit_helper_poc/tests/test_logger.py
git commit -m "feat: add Logger module with configurable log level"
```

---

### Task 2: BaseSubagent 抽象基类

**Files:**
- Create: `audit_helper_poc/__init__.py`
- Create: `audit_helper_poc/base_subagent.py`
- Create: `audit_helper_poc/tests/test_base_subagent.py`

- [ ] **Step 1: Write the failing test**

```python
# audit_helper_poc/tests/test_base_subagent.py
import pytest
from abc import ABC
from audit_helper_poc.base_subagent import BaseSubagent


def test_base_subagent_is_abstract():
    """测试 BaseSubagent 是抽象类"""
    assert ABC in BaseSubagent.__bases__


def test_base_subagent_cannot_instantiate():
    """测试不能直接实例化抽象类"""
    with pytest.raises(TypeError):
        BaseSubagent()


def test_base_subagent_has_category_property():
    """测试 category 是抽象属性"""
    # 子类必须实现 category
    class IncompleteSubagent(BaseSubagent):
        def invoke(self, pdf_path, pdf_type, config):
            return {}
    
    with pytest.raises(TypeError):
        IncompleteSubagent()


def test_base_subagent_has_invoke_method():
    """测试 invoke 是抽象方法"""
    class IncompleteSubagent(BaseSubagent):
        @property
        def category(self):
            return "test"
    
    with pytest.raises(TypeError):
        IncompleteSubagent()


def test_complete_subagent_can_instantiate():
    """测试完整实现的子类可以实例化"""
    class CompleteSubagent(BaseSubagent):
        @property
        def category(self):
            return "test_category"
        
        def invoke(self, pdf_path, pdf_type, config):
            return {
                "success": True,
                "data": {},
                "error": None,
                "model": config.get("MODEL_NAME", ""),
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }
    
    subagent = CompleteSubagent()
    assert subagent.category == "test_category"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd audit_helper_poc && python -m pytest tests/test_base_subagent.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write minimal implementation**

```python
# audit_helper_poc/__init__.py
"""audit_helper_poc - PDF 处理框架"""
from .base_subagent import BaseSubagent
from .logger import Logger
from .planner import Planner

__all__ = ["BaseSubagent", "Logger", "Planner"]
```

```python
# audit_helper_poc/base_subagent.py
from abc import ABC, abstractmethod


class BaseSubagent(ABC):
    """PDF 处理子代理的抽象基类"""
    
    @property
    @abstractmethod
    def category(self) -> str:
        """
        返回该 subagent 处理的 PDF 类别名称。
        
        Returns:
            str: 类别名称，如 "房租合同"、"银行明细对账单" 等
        """
        pass
    
    @abstractmethod
    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        """
        处理 PDF 文件并提取结构化信息。
        
        Args:
            pdf_path: PDF 文件的绝对路径
            pdf_type: PDF 类型 ("native" 或 "scanned")
            config: 配置字典 (API_KEY, BASE_URL, MODEL_NAME)
        
        Returns:
            dict: {
                "success": bool,
                "data": dict | None,
                "error": str | None,
                "model": str,
                "token_usage": {
                    "prompt_tokens": int,
                    "completion_tokens": int,
                    "total_tokens": int
                }
            }
        """
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd audit_helper_poc && python -m pytest tests/test_base_subagent.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add audit_helper_poc/__init__.py audit_helper_poc/base_subagent.py audit_helper_poc/tests/test_base_subagent.py
git commit -m "feat: add BaseSubagent abstract base class"
```

---

### Task 3: DefaultSubagent (兜底处理)

**Files:**
- Create: `audit_helper_poc/subagents/__init__.py`
- Create: `audit_helper_poc/subagents/default_subagent.py`
- Modify: `audit_helper_poc/tests/test_subagents.py`

- [ ] **Step 1: Write the failing test**

```python
# audit_helper_poc/tests/test_subagents.py
import pytest
from audit_helper_poc.subagents.default_subagent import DefaultSubagent


def test_default_subagent_category():
    """测试 DefaultSubagent 的 category"""
    subagent = DefaultSubagent()
    assert subagent.category == "其他"


def test_default_subagent_invoke_returns_failure():
    """测试 DefaultSubagent invoke 返回失败状态"""
    subagent = DefaultSubagent()
    result = subagent.invoke(
        pdf_path="/test/file.pdf",
        pdf_type="native",
        config={"MODEL_NAME": "test-model"}
    )
    
    assert result["success"] is False
    assert result["data"] is None
    assert result["error"] == "无对应的处理 subagent"
    assert result["model"] == "test-model"
    assert result["token_usage"]["total_tokens"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd audit_helper_poc && python -m pytest tests/test_subagents.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write minimal implementation**

```python
# audit_helper_poc/subagents/__init__.py
"""Subagent 注册模块"""
from .default_subagent import DefaultSubagent
from .rent_contract_subagent import RentContractSubagent
from .vat_tax_subagent import VatTaxSubagent
from .income_tax_subagent import IncomeTaxSubagent
from .financial_report_subagent import FinancialReportSubagent
from .tianyancha_subagent import TianyanchaSubagent
from .bank_confirmation_subagent import BankConfirmationSubagent
from .bank_detail_subagent import BankDetailSubagent
from .bank_balance_subagent import BankBalanceSubagent

__all__ = [
    "DefaultSubagent",
    "RentContractSubagent",
    "VatTaxSubagent",
    "IncomeTaxSubagent",
    "FinancialReportSubagent",
    "TianyanchaSubagent",
    "BankConfirmationSubagent",
    "BankDetailSubagent",
    "BankBalanceSubagent",
]
```

```python
# audit_helper_poc/subagents/default_subagent.py
from ..base_subagent import BaseSubagent


class DefaultSubagent(BaseSubagent):
    """兜底处理子代理，处理"其他"类别"""
    
    @property
    def category(self) -> str:
        return "其他"
    
    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        return {
            "success": False,
            "data": None,
            "error": "无对应的处理 subagent",
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd audit_helper_poc && python -m pytest tests/test_subagents.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add audit_helper_poc/subagents/__init__.py audit_helper_poc/subagents/default_subagent.py audit_helper_poc/tests/test_subagents.py
git commit -m "feat: add DefaultSubagent for fallback handling"
```

---

### Task 4: RentContractSubagent (房租合同)

**Files:**
- Create: `audit_helper_poc/subagents/rent_contract_subagent.py`
- Modify: `audit_helper_poc/tests/test_subagents.py`

- [ ] **Step 1: Write the failing test**

```python
# 在 audit_helper_poc/tests/test_subagents.py 中添加
from audit_helper_poc.subagents.rent_contract_subagent import RentContractSubagent


def test_rent_contract_subagent_category():
    """测试 RentContractSubagent 的 category"""
    subagent = RentContractSubagent()
    assert subagent.category == "房租合同"


def test_rent_contract_subagent_invoke_returns_mock_data():
    """测试 RentContractSubagent invoke 返回模拟数据"""
    subagent = RentContractSubagent()
    result = subagent.invoke(
        pdf_path="/test/rent.pdf",
        pdf_type="native",
        config={"MODEL_NAME": "gpt-4o"}
    )
    
    assert result["success"] is True
    assert result["data"] is not None
    assert "lease_term" in result["data"]
    assert "rent" in result["data"]
    assert result["error"] is None
    assert result["model"] == "gpt-4o"
    assert result["token_usage"]["total_tokens"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd audit_helper_poc && python -m pytest tests/test_subagents.py::test_rent_contract_subagent_category -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write minimal implementation**

```python
# audit_helper_poc/subagents/rent_contract_subagent.py
from ..base_subagent import BaseSubagent


class RentContractSubagent(BaseSubagent):
    """房租合同处理子代理"""
    
    @property
    def category(self) -> str:
        return "房租合同"
    
    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        # 当前阶段：返回模拟数据
        return {
            "success": True,
            "data": {
                "lease_term": {
                    "start_date": "2024-01-01",
                    "end_date": "2025-12-31",
                    "duration": "2年"
                },
                "rent": {
                    "monthly_rent": 5000,
                    "currency": "人民币",
                    "payment_cycle": "月付"
                },
                "parties": {
                    "landlord": "房东名称",
                    "tenant": "租户名称"
                },
                "property_address": "租赁地址"
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {
                "prompt_tokens": 1500,
                "completion_tokens": 300,
                "total_tokens": 1800
            }
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd audit_helper_poc && python -m pytest tests/test_subagents.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add audit_helper_poc/subagents/rent_contract_subagent.py audit_helper_poc/tests/test_subagents.py
git commit -m "feat: add RentContractSubagent with mock data"
```

---

### Task 5: 剩余 Subagents (批量创建)

**Files:**
- Create: `audit_helper_poc/subagents/vat_tax_subagent.py`
- Create: `audit_helper_poc/subagents/income_tax_subagent.py`
- Create: `audit_helper_poc/subagents/financial_report_subagent.py`
- Create: `audit_helper_poc/subagents/tianyancha_subagent.py`
- Create: `audit_helper_poc/subagents/bank_confirmation_subagent.py`
- Create: `audit_helper_poc/subagents/bank_detail_subagent.py`
- Create: `audit_helper_poc/subagents/bank_balance_subagent.py`
- Modify: `audit_helper_poc/tests/test_subagents.py`

- [ ] **Step 1: Write the failing test**

```python
# 在 audit_helper_poc/tests/test_subagents.py 中添加
from audit_helper_poc.subagents import (
    VatTaxSubagent,
    IncomeTaxSubagent,
    FinancialReportSubagent,
    TianyanchaSubagent,
    BankConfirmationSubagent,
    BankDetailSubagent,
    BankBalanceSubagent,
)


def test_all_subagents_categories():
    """测试所有 subagent 的 category 属性"""
    expected = {
        VatTaxSubagent: "增值税纳税申报表",
        IncomeTaxSubagent: "企业所得税纳税申报表",
        FinancialReportSubagent: "财务报表",
        TianyanchaSubagent: "天眼查信息",
        BankConfirmationSubagent: "银行询证函",
        BankDetailSubagent: "银行明细对账单",
        BankBalanceSubagent: "银行余额对账单",
    }
    
    for cls, expected_category in expected.items():
        subagent = cls()
        assert subagent.category == expected_category


def test_all_subagents_invoke_returns_success():
    """测试所有 subagent invoke 返回成功"""
    config = {"MODEL_NAME": "test-model"}
    
    for cls in [VatTaxSubagent, IncomeTaxSubagent, FinancialReportSubagent,
                TianyanchaSubagent, BankConfirmationSubagent, BankDetailSubagent,
                BankBalanceSubagent]:
        subagent = cls()
        result = subagent.invoke("/test.pdf", "native", config)
        assert result["success"] is True
        assert result["data"] is not None
        assert result["error"] is None
        assert result["token_usage"]["total_tokens"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd audit_helper_poc && python -m pytest tests/test_subagents.py::test_all_subagents_categories -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Write minimal implementation**

```python
# audit_helper_poc/subagents/vat_tax_subagent.py
from ..base_subagent import BaseSubagent


class VatTaxSubagent(BaseSubagent):
    """增值税纳税申报表处理子代理"""
    
    @property
    def category(self) -> str:
        return "增值税纳税申报表"
    
    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        return {
            "success": True,
            "data": {
                "tax_period": "2024年第一季度",
                "tax_amount": 15000.00,
                "sales_amount": 100000.00,
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {"prompt_tokens": 1200, "completion_tokens": 200, "total_tokens": 1400}
        }
```

```python
# audit_helper_poc/subagents/income_tax_subagent.py
from ..base_subagent import BaseSubagent


class IncomeTaxSubagent(BaseSubagent):
    """企业所得税纳税申报表处理子代理"""
    
    @property
    def category(self) -> str:
        return "企业所得税纳税申报表"
    
    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        return {
            "success": True,
            "data": {
                "tax_year": "2024",
                "taxable_income": 500000.00,
                "tax_amount": 125000.00,
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {"prompt_tokens": 1300, "completion_tokens": 250, "total_tokens": 1550}
        }
```

```python
# audit_helper_poc/subagents/financial_report_subagent.py
from ..base_subagent import BaseSubagent


class FinancialReportSubagent(BaseSubagent):
    """财务报表处理子代理"""
    
    @property
    def category(self) -> str:
        return "财务报表"
    
    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        return {
            "success": True,
            "data": {
                "report_type": "资产负债表",
                "report_period": "2024年",
                "total_assets": 1000000.00,
                "total_liabilities": 500000.00,
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {"prompt_tokens": 1800, "completion_tokens": 350, "total_tokens": 2150}
        }
```

```python
# audit_helper_poc/subagents/tianyancha_subagent.py
from ..base_subagent import BaseSubagent


class TianyanchaSubagent(BaseSubagent):
    """天眼查信息处理子代理"""
    
    @property
    def category(self) -> str:
        return "天眼查信息"
    
    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        return {
            "success": True,
            "data": {
                "company_name": "公司名称",
                "registration_date": "2020-01-01",
                "legal_representative": "法定代表人",
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {"prompt_tokens": 1000, "completion_tokens": 150, "total_tokens": 1150}
        }
```

```python
# audit_helper_poc/subagents/bank_confirmation_subagent.py
from ..base_subagent import BaseSubagent


class BankConfirmationSubagent(BaseSubagent):
    """银行询证函处理子代理"""
    
    @property
    def category(self) -> str:
        return "银行询证函"
    
    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        return {
            "success": True,
            "data": {
                "bank_name": "银行名称",
                "account_number": "账号",
                "balance": 100000.00,
                "confirmation_date": "2024-12-31",
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {"prompt_tokens": 1100, "completion_tokens": 180, "total_tokens": 1280}
        }
```

```python
# audit_helper_poc/subagents/bank_detail_subagent.py
from ..base_subagent import BaseSubagent


class BankDetailSubagent(BaseSubagent):
    """银行明细对账单处理子代理"""
    
    @property
    def category(self) -> str:
        return "银行明细对账单"
    
    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        return {
            "success": True,
            "data": {
                "account_info": {
                    "bank_name": "银行名称",
                    "account_number": "账号",
                    "account_name": "账户名称"
                },
                "period": {
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31"
                },
                "balance": {
                    "opening_balance": 100000.00,
                    "closing_balance": 150000.00
                },
                "transactions_summary": {
                    "total_deposits": 60000.00,
                    "total_withdrawals": 10000.00,
                    "transaction_count": 25
                }
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {"prompt_tokens": 2000, "completion_tokens": 400, "total_tokens": 2400}
        }
```

```python
# audit_helper_poc/subagents/bank_balance_subagent.py
from ..base_subagent import BaseSubagent


class BankBalanceSubagent(BaseSubagent):
    """银行余额对账单处理子代理"""
    
    @property
    def category(self) -> str:
        return "银行余额对账单"
    
    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        return {
            "success": True,
            "data": {
                "bank_name": "银行名称",
                "account_number": "账号",
                "balance_date": "2024-12-31",
                "balance": 150000.00,
            },
            "error": None,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": {"prompt_tokens": 900, "completion_tokens": 120, "total_tokens": 1020}
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd audit_helper_poc && python -m pytest tests/test_subagents.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add audit_helper_poc/subagents/*.py audit_helper_poc/tests/test_subagents.py
git commit -m "feat: add all remaining subagents with mock data"
```

---

### Task 6: Utils 模块

**Files:**
- Create: `audit_helper_poc/utils.py`

- [ ] **Step 1: Write minimal implementation**

```python
# audit_helper_poc/utils.py
"""工具函数模块，复用 audit_helper 的功能"""
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import dotenv_values


def load_config(config_path: str) -> dict:
    """从 .env 文件加载配置"""
    return dict(dotenv_values(config_path))


def scan_pdf_files(directory: str) -> list[str]:
    """扫描目录下的 PDF 文件"""
    pdf_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))
    return sorted(pdf_files)


def write_json_output(data: dict, output_path: str) -> None:
    """写入 JSON 输出文件"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json_file(file_path: str) -> dict:
    """读取 JSON 文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_current_timestamp() -> str:
    """获取当前时间戳 (ISO 格式)"""
    return datetime.now().isoformat()
```

- [ ] **Step 2: Run quick verification**

Run: `cd audit_helper_poc && python -c "from utils import load_config, scan_pdf_files, write_json_output, get_current_timestamp; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add audit_helper_poc/utils.py
git commit -m "feat: add utils module with config loading and file scanning"
```

---

### Task 7: Planner 主控制器

**Files:**
- Create: `audit_helper_poc/planner.py`
- Create: `audit_helper_poc/tests/test_planner.py`

- [ ] **Step 1: Write the failing test**

```python
# audit_helper_poc/tests/test_planner.py
import pytest
import os
import json
from pathlib import Path
from audit_helper_poc.planner import Planner


def test_planner_init():
    """测试 Planner 初始化"""
    planner = Planner()
    assert planner.config is not None
    assert planner.logger is not None
    assert len(planner._subagents) == 9  # 8 + default


def test_planner_register_subagent():
    """测试注册 subagent"""
    planner = Planner()
    
    class CustomSubagent:
        @property
        def category(self):
            return "自定义类别"
    
    planner.register_subagent(CustomSubagent())
    assert "自定义类别" in planner._subagents


def test_planner_has_all_categories():
    """测试 Planner 包含所有类别"""
    planner = Planner()
    expected_categories = [
        "房租合同", "增值税纳税申报表", "企业所得税纳税申报表",
        "财务报表", "天眼查信息", "银行询证函",
        "银行明细对账单", "银行余额对账单", "其他"
    ]
    for cat in expected_categories:
        assert cat in planner._subagents
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd audit_helper_poc && python -m pytest tests/test_planner.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write minimal implementation**

```python
# audit_helper_poc/planner.py
"""PDF 处理主控制器"""
import os
import json
from pathlib import Path
from typing import Optional

from .logger import Logger
from .utils import load_config, scan_pdf_files, write_json_output, read_json_file, get_current_timestamp
from .base_subagent import BaseSubagent
from .subagents import (
    DefaultSubagent,
    RentContractSubagent,
    VatTaxSubagent,
    IncomeTaxSubagent,
    FinancialReportSubagent,
    TianyanchaSubagent,
    BankConfirmationSubagent,
    BankDetailSubagent,
    BankBalanceSubagent,
)


# PDF 类别列表
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


class Planner:
    """PDF 处理主控制器"""
    
    def __init__(
        self,
        config_path: str = ".env",
        log_level: str = "INFO"
    ):
        """
        初始化 Planner。
        
        Args:
            config_path: 配置文件路径
            log_level: 日志级别
        """
        # 获取配置文件绝对路径
        if not os.path.isabs(config_path):
            base_dir = Path(__file__).parent
            config_path = str(base_dir / config_path)
        
        self.config_path = config_path
        self.config = load_config(config_path)
        
        # 初始化日志
        self.log_level = self.config.get("LOG_LEVEL", log_level)
        self.logger = Logger(name="audit_helper_poc", level=self.log_level)
        
        # 初始化 subagent 注册表
        self._subagents: dict[str, BaseSubagent] = {}
        
        # 自动注册所有内置 subagent
        self._register_builtin_subagents()
        
        self.logger.info(f"Planner 初始化完成，日志级别: {self.log_level}")
    
    def _register_builtin_subagents(self) -> None:
        """注册所有内置 subagent"""
        subagents = [
            RentContractSubagent(),
            VatTaxSubagent(),
            IncomeTaxSubagent(),
            FinancialReportSubagent(),
            TianyanchaSubagent(),
            BankConfirmationSubagent(),
            BankDetailSubagent(),
            BankBalanceSubagent(),
            DefaultSubagent(),  # 兜底
        ]
        
        for subagent in subagents:
            self.register_subagent(subagent)
    
    def register_subagent(self, subagent: BaseSubagent) -> None:
        """注册 subagent"""
        self._subagents[subagent.category] = subagent
        self.logger.debug(f"注册 subagent: {subagent.category}")
    
    def process(
        self,
        input_dir: str,
        output_file: str = "process_result.json"
    ) -> dict:
        """
        执行完整的 PDF 处理流程。
        
        Args:
            input_dir: PDF 文件目录
            output_file: 输出结果文件名
        
        Returns:
            处理结果汇总
        """
        # 处理路径
        if not os.path.isabs(input_dir):
            base_dir = Path(__file__).parent
            input_dir = str(base_dir / input_dir)
        
        if not os.path.isabs(output_file):
            base_dir = Path(__file__).parent
            output_file = str(base_dir / output_file)
        
        # 扫描 PDF 文件
        self.logger.info(f"扫描目录: {input_dir}")
        pdf_files = scan_pdf_files(input_dir)
        self.logger.info(f"发现 {len(pdf_files)} 个 PDF 文件")
        
        if not pdf_files:
            self.logger.warning("没有找到 PDF 文件")
            return {
                "start_time": get_current_timestamp(),
                "end_time": get_current_timestamp(),
                "input_dir": input_dir,
                "total_files": 0,
                "files": [],
                "summary": {}
            }
        
        # 初始化结果文件
        self.logger.info(f"创建结果文件: {output_file}")
        self._init_result_file(pdf_files, output_file)
        
        overall_start_time = get_current_timestamp()
        
        # 串行处理每个文件
        for i, pdf_path in enumerate(pdf_files):
            self.logger.info(f"开始处理文件 {i + 1}/{len(pdf_files)}: {os.path.basename(pdf_path)}")
            
            # 更新状态为 processing
            file_start_time = get_current_timestamp()
            self._update_file_status(output_file, i, "processing", start_time=file_start_time)
            
            # 处理文件
            result = self._process_single_file(pdf_path)
            
            # 更新状态为 completed
            file_end_time = get_current_timestamp()
            self._update_file_result(output_file, i, result, end_time=file_end_time)
            
            status = "success" if result["subagent_result"]["success"] else "failed"
            self.logger.info(f"文件 {i + 1}/{len(pdf_files)} 处理完成，状态: {status}")
        
        overall_end_time = get_current_timestamp()
        
        # 生成汇总并写入
        final_result = self._finalize_result(output_file, overall_start_time, overall_end_time, input_dir)
        
        self.logger.info("所有文件处理完成")
        self.logger.info(f"总耗时: {self._calculate_duration(overall_start_time, overall_end_time)}")
        
        return final_result
    
    def _init_result_file(self, pdf_files: list[str], output_file: str) -> None:
        """初始化结果文件"""
        files_data = []
        for pdf_path in pdf_files:
            files_data.append({
                "filename": os.path.basename(pdf_path),
                "file_path": pdf_path,
                "status": "not_started",
                "start_time": None,
                "end_time": None,
                "pdf_type": None,
                "category": None,
                "subagent_result": None
            })
        
        initial_data = {
            "start_time": None,
            "end_time": None,
            "input_dir": None,
            "total_files": len(pdf_files),
            "files": files_data,
            "summary": {}
        }
        
        write_json_output(initial_data, output_file)
    
    def _update_file_status(
        self,
        output_file: str,
        file_index: int,
        status: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> None:
        """更新文件状态"""
        data = read_json_file(output_file)
        data["files"][file_index]["status"] = status
        if start_time:
            data["files"][file_index]["start_time"] = start_time
        if end_time:
            data["files"][file_index]["end_time"] = end_time
        write_json_output(data, output_file)
    
    def _update_file_result(
        self,
        output_file: str,
        file_index: int,
        result: dict,
        end_time: str
    ) -> None:
        """更新文件处理结果"""
        data = read_json_file(output_file)
        data["files"][file_index]["status"] = "completed"
        data["files"][file_index]["end_time"] = end_time
        data["files"][file_index]["pdf_type"] = result["pdf_type"]
        data["files"][file_index]["category"] = result["category"]
        data["files"][file_index]["subagent_result"] = result["subagent_result"]
        write_json_output(data, output_file)
    
    def _process_single_file(self, pdf_path: str) -> dict:
        """处理单个文件"""
        # 模拟 PDF 类型检测
        pdf_type = "native"  # 当前阶段使用模拟值
        self.logger.debug(f"检测 PDF 类型: {pdf_type}")
        
        # 模拟分类
        category = "房租合同"  # 当前阶段使用模拟值
        self.logger.debug(f"分类结果: {category}")
        
        # 获取对应的 subagent
        subagent = self._subagents.get(category, self._subagents["其他"])
        self.logger.info(f"调用 subagent: {subagent.__class__.__name__}")
        
        # 调用 invoke
        subagent_result = subagent.invoke(pdf_path, pdf_type, self.config)
        
        return {
            "pdf_type": pdf_type,
            "category": category,
            "subagent_result": subagent_result
        }
    
    def _finalize_result(
        self,
        output_file: str,
        start_time: str,
        end_time: str,
        input_dir: str
    ) -> dict:
        """生成最终汇总结果"""
        data = read_json_file(output_file)
        data["start_time"] = start_time
        data["end_time"] = end_time
        data["input_dir"] = input_dir
        
        # 计算汇总
        native_count = sum(1 for f in data["files"] if f["pdf_type"] == "native")
        scanned_count = sum(1 for f in data["files"] if f["pdf_type"] == "scanned")
        
        category_distribution = {}
        total_tokens = 0
        for f in data["files"]:
            cat = f.get("category", "其他")
            category_distribution[cat] = category_distribution.get(cat, 0) + 1
            if f["subagent_result"]:
                total_tokens += f["subagent_result"]["token_usage"]["total_tokens"]
        
        data["summary"] = {
            "native_count": native_count,
            "scanned_count": scanned_count,
            "category_distribution": category_distribution,
            "total_token_usage": {
                "prompt_tokens": sum(f["subagent_result"]["token_usage"]["prompt_tokens"] 
                                     for f in data["files"] if f["subagent_result"]),
                "completion_tokens": sum(f["subagent_result"]["token_usage"]["completion_tokens"] 
                                         for f in data["files"] if f["subagent_result"]),
                "total_tokens": total_tokens
            }
        }
        
        write_json_output(data, output_file)
        return data
    
    def _calculate_duration(self, start: str, end: str) -> str:
        """计算耗时"""
        from datetime import datetime
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        delta = end_dt - start_dt
        total_seconds = int(delta.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}分{seconds}秒"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd audit_helper_poc && python -m pytest tests/test_planner.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add audit_helper_poc/planner.py audit_helper_poc/tests/test_planner.py
git commit -m "feat: add Planner main controller with registration and process flow"
```

---

### Task 8: 验证完整流程

**Files:**
- Create: `audit_helper_poc/.env.example`

- [ ] **Step 1: 创建示例配置文件**

```bash
# audit_helper_poc/.env.example
API_KEY=your_api_key_here
BASE_URL=https://api.example.com/v1
MODEL_NAME=gpt-4o
LOG_LEVEL=INFO
```

- [ ] **Step 2: 运行完整测试**

Run: `cd audit_helper_poc && python -m pytest tests/ -v`
Expected: PASS (all tests)

- [ ] **Step 3: Commit**

```bash
git add audit_helper_poc/.env.example
git commit -m "docs: add .env.example configuration template"
```

---

## 自检清单

**1. Spec coverage:**
- ✅ Logger 模块 (Task 1)
- ✅ BaseSubagent 抽象基类 (Task 2)
- ✅ DefaultSubagent 兜底处理 (Task 3)
- ✅ 8 个具体 Subagent (Task 4-5)
- ✅ Utils 模块 (Task 6)
- ✅ Planner 主控制器 (Task 7)
- ✅ 配置文件示例 (Task 8)

**2. Placeholder scan:** 无 TBD/TODO，所有代码完整。

**3. Type consistency:** 所有 subagent invoke 返回格式统一，category 属性名称与注册表 key 一致。
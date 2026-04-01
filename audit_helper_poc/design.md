# audit_helper_poc 设计文档

## 概述

audit_helper_poc 是一个 PDF 处理框架，用于：
1. 读取 PDF 文件
2. 判断 PDF 类型（原生件/扫描件）
3. 分类 PDF 类别（房租合同、银行对账单等）
4. 调用对应 subagent 提取结构化信息

## 架构

```
audit_helper_poc/
├── __init__.py
├── planner.py              # 主控制器
├── base_subagent.py        # 抽象基类
├── logger.py               # 日志模块
├── subagents/
│   ├── __init__.py         # subagent 注册
│   ├── default_subagent.py         # 兜底处理（"其他"类别）
│   ├── rent_contract_subagent.py       # 房租合同
│   ├── vat_tax_subagent.py             # 增值税纳税申报表
│   ├── income_tax_subagent.py          # 企业所得税纳税申报表
│   ├── financial_report_subagent.py    # 财务报表
│   ├── tianyancha_subagent.py          # 天眼查信息
│   ├── bank_confirmation_subagent.py   # 银行询证函
│   ├── bank_detail_subagent.py         # 银行明细对账单
│   └── bank_balance_subagent.py        # 银行余额对账单
└── utils.py                # 工具函数（复用 audit_helper）
```

## 支持的 PDF 类别

| 类别 | Subagent 文件 |
|------|---------------|
| 房租合同 | rent_contract_subagent.py |
| 增值税纳税申报表 | vat_tax_subagent.py |
| 企业所得税纳税申报表 | income_tax_subagent.py |
| 财务报表 | financial_report_subagent.py |
| 天眼查信息 | tianyancha_subagent.py |
| 银行询证函 | bank_confirmation_subagent.py |
| 银行明细对账单 | bank_detail_subagent.py |
| 银行余额对账单 | bank_balance_subagent.py |
| 其他 | default_subagent.py（兜底） |

## 核心类设计

### 1. BaseSubagent（抽象基类）

```python
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
            pdf_type: PDF 类型
                - "native": 原生件（可提取文本）
                - "scanned": 扫描件（图片形式）
            config: 配置字典，包含：
                - API_KEY: API 密钥
                - BASE_URL: API 基础 URL
                - MODEL_NAME: 模型名称
        
        Returns:
            dict: 统一返回格式
                {
                    "success": bool,           # 处理是否成功
                    "data": dict | None,       # 提取的结构化数据（各 subagent 特定格式）
                    "error": str | None,       # 错误信息，成功时为 null
                    "model": str,              # 使用的 LLM 模型名称
                    "token_usage": {           # Token 使用信息
                        "prompt_tokens": int,
                        "completion_tokens": int,
                        "total_tokens": int
                    }
                }
        """
        pass
```

### 2. Logger（日志模块）

```python
import logging

class Logger:
    """日志管理器"""
    
    def __init__(self, name: str = "audit_helper_poc", level: str = "INFO"):
        """
        初始化日志器。
        
        Args:
            name: 日志器名称
            level: 日志级别，可选值：
                - "DEBUG": 详细调试信息
                - "INFO": 一般信息（默认）
                - "WARNING": 警告信息
                - "ERROR": 错误信息
        """
        pass
    
    def debug(self, message: str) -> None:
        """输出 DEBUG 级别日志"""
        pass
    
    def info(self, message: str) -> None:
        """输出 INFO 级别日志"""
        pass
    
    def warning(self, message: str) -> None:
        """输出 WARNING 级别日志"""
        pass
    
    def error(self, message: str) -> None:
        """输出 ERROR 级别日志"""
        pass
```

### 3. Planner（主控制器）

```python
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
            config_path: 配置文件路径，默认为 ".env"
            log_level: 日志级别，默认 "INFO"
        
        功能：
            - 从 .env 加载配置（API_KEY、BASE_URL、MODEL_NAME 等）
            - 初始化 Logger
            - 初始化 subagent 注册表
            - 自动注册所有内置 subagent
        """
        pass
    
    def register_subagent(self, subagent: BaseSubagent) -> None:
        """
        注册 subagent 到处理注册表。
        
        Args:
            subagent: BaseSubagent 实例
        
        注册表结构：
            self._subagents = {
                "房租合同": RentContractSubagent(),
                "银行明细对账单": BankDetailSubagent(),
                ...
                "其他": DefaultSubagent()  # 兜底
            }
        """
        pass
    
    def process(self, input_dir: str, output_file: str = "process_result.json") -> dict:
        """
        执行完整的 PDF 处理流程（串行处理）。
        
        Args:
            input_dir: PDF 文件所在的目录路径
            output_file: 输出结果文件名，默认 "process_result.json"
        
        流程：
            1. 扫描目录下的 PDF 文件
            2. 立即创建 process_result.json，初始化所有文件状态为 "not_started"
            3. 串行处理每个文件：
               a. 更新状态为 "processing"，记录 start_time
               b. 检测 PDF 类型（native/scanned）
               c. 分类 PDF 类别
               d. 调用对应 subagent.invoke()（串行调用）
               e. 更新状态为 "completed"，记录 end_time，写入结果
            4. 输出汇总信息
        
        输出文件 process_result.json 结构：
            {
                "start_time": "2024-04-01T10:00:00",
                "end_time": "2024-04-01T10:30:00",
                "input_dir": str,
                "total_files": int,
                "files": [
                    {
                        "filename": str,
                        "file_path": str,
                        "status": "not_started" | "processing" | "completed" | "skipped",
                        "start_time": "2024-04-01T10:00:00" | null,
                        "end_time": "2024-04-01T10:05:00" | null,
                        "pdf_type": "native" | "scanned" | null,
                        "category": str | null,
                        "subagent_result": {
                            "success": bool,
                            "data": dict,
                            "error": str,
                            "model": str,
                            "token_usage": dict
                        } | null
                    }
                ],
                "summary": {
                    "native_count": int,
                    "scanned_count": int,
                    "category_distribution": dict,
                    "total_token_usage": dict
                }
            }
        
        Returns:
            dict: 处理结果汇总（与输出文件内容相同）
        """
        pass
    
    def _init_result_file(self, pdf_files: list[str], output_file: str) -> None:
        """
        初始化结果文件，所有文件状态设为 "not_started"。
        
        Args:
            pdf_files: PDF 文件路径列表
            output_file: 输出文件路径
        """
        pass
    
    def _update_file_status(
        self,
        output_file: str,
        file_index: int,
        status: str,
        start_time: str = None,
        end_time: str = None
    ) -> None:
        """
        更新指定文件的处理状态。
        
        Args:
            output_file: 输出文件路径
            file_index: 文件索引
            status: 新状态
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
        """
        pass
```

### 3. 各具体 Subagent 示例

#### DefaultSubagent（兜底处理）

```python
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

#### RentContractSubagent（房租合同）

```python
class RentContractSubagent(BaseSubagent):
    """房租合同处理子代理"""
    
    @property
    def category(self) -> str:
        return "房租合同"
    
    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        # 当前阶段：返回模拟数据，不实际调用 LLM
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

#### BankDetailSubagent（银行明细对账单）

```python
class BankDetailSubagent(BaseSubagent):
    """银行明细对账单处理子代理"""
    
    @property
    def category(self) -> str:
        return "银行明细对账单"
    
    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        # 当前阶段：返回模拟数据，不实际调用 LLM
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
            "token_usage": {
                "prompt_tokens": 2000,
                "completion_tokens": 400,
                "total_tokens": 2400
            }
        }
```

## 配置

配置从 `.env` 文件加载，必需项：
- `API_KEY`: API 密钥
- `BASE_URL`: API 基础 URL
- `MODEL_NAME`: 模型名称

可选配置项：
- `TEXT_DENSITY_THRESHOLD`: 文本密度阈值（判断 native/scanned）
- `PAGES_FOR_CLASSIFICATION`: 用于分类的页数
- `LOG_LEVEL`: 日志级别，默认 "INFO"

## 日志输出示例

```
[INFO] Planner 初始化完成，日志级别: INFO
[INFO] 扫描目录: data/
[INFO] 发现 5 个 PDF 文件
[INFO] 创建结果文件: process_result.json
[INFO] 开始处理文件 1/5: 合同1.pdf
[DEBUG] 检测 PDF 类型: native
[DEBUG] 分类结果: 房租合同
[INFO] 调用 subagent: RentContractSubagent
[INFO] 文件 1/5 处理完成，状态: success
[INFO] 开始处理文件 2/5: 银行对账单.pdf
...
[INFO] 所有文件处理完成
[INFO] 总耗时: 30 分钟
[INFO] 总 Token 使用: 15000
```

## 实现原则

1. **接口先行**：先定义接口，不实现具体 LLM 调用逻辑
2. **模拟数据**：各 subagent 返回模拟的 JSON 数据
3. **注册机制**：Planner 内部维护 subagent 注册表（dict）
4. **兜底处理**：DefaultSubagent 处理"其他"类别，返回失败状态
5. **复用代码**：复用 audit_helper 的 utils.py 和 pdf_processor.py
6. **串行处理**：Planner 依次调用 subagent，不并行处理
7. **实时更新**：process_result.json 在扫描完成后立即创建，处理过程中实时更新状态
8. **状态追踪**：每个文件有 status、start_time、end_time 字段
9. **日志输出**：支持可配置的日志级别（DEBUG/INFO/WARNING/ERROR）

## 后续扩展

完成框架后，后续工作：
1. 为每个 subagent 实现具体的 LLM 调用逻辑
2. 定义每个类别特定的 data 结构
3. 添加错误处理和重试机制
4. 优化 token 使用效率
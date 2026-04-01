# audit_helper_poc/planner.py
"""PDF 处理主控制器"""
import os
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


class Planner:
    """PDF 处理主控制器"""

    def __init__(self, config_path: str = ".env", log_level: str = "INFO"):
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

    def process(self, input_dir: str, output_file: str = "process_result.json") -> dict:
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

        # 生成汇总
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
        # 当前阶段：模拟处理
        pdf_type = "native"
        self.logger.debug(f"检测 PDF 类型: {pdf_type}")

        category = "房租合同"  # 模拟值
        self.logger.debug(f"分类结果: {category}")

        subagent = self._subagents.get(category, self._subagents["其他"])
        self.logger.info(f"调用 subagent: {subagent.__class__.__name__}")

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
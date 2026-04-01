# audit_helper_poc/planner.py
"""PDF 处理主控制器"""
import os
from datetime import datetime
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
from .pdf_utils import detect_pdf_type, ocr_pdf_pages, build_marked_text, pdf_to_images
from .llm_utils import LLMClient, build_multimodal_content


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


# PDF 分类 Prompt
CLASSIFY_SYSTEM_PROMPT = """你是一个审计文档分类助手。请根据文档内容判断其类型。

可选的文档类型：
{categories_str}

请返回 JSON 格式的结果：
{{"category": "文档类型", "confidence": 0.0-1.0}}

注意：
1. category 必须是上述类型之一
2. confidence 是置信度，范围 0.0 到 1.0
3. 只返回 JSON，不要其他内容"""

CLASSIFY_TEXT_PROMPT = "请分析以下 PDF 文档内容并分类：\n\n{content}"

CLASSIFY_IMAGE_PROMPT = "请分析以上 PDF 文档图片并分类。"


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

        # 初始化 LLM 客户端
        self._llm_client: Optional[LLMClient] = None

        # 初始化 subagent 注册表
        self._subagents: dict[str, BaseSubagent] = {}

        # 自动注册所有内置 subagent
        self._register_builtin_subagents()

        self.logger.info(f"Planner 初始化完成，日志级别: {self.log_level}")

    def _init_llm_client(self) -> LLMClient:
        """初始化 LLM 客户端"""
        if self._llm_client is None:
            self._llm_client = LLMClient(
                api_key=self.config["API_KEY"],
                base_url=self.config["BASE_URL"],
                model_name=self.config["MODEL_NAME"]
            )
        else:
            self._llm_client.reset_token_tracker()
        return self._llm_client

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

            try:
                # 处理文件
                result = self._process_single_file(pdf_path)
                status = "success" if result["subagent_result"]["success"] else "failed"
            except Exception as e:
                self.logger.error(f"处理文件失败: {e}")
                result = {
                    "pdf_type": None,
                    "category": None,
                    "subagent_result": {
                        "success": False,
                        "data": None,
                        "error": str(e),
                        "model": self.config.get("MODEL_NAME", ""),
                        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                    }
                }
                status = "error"

            # 更新状态为 completed
            file_end_time = get_current_timestamp()
            self._update_file_result(output_file, i, result, end_time=file_end_time)

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
        # Step 1: 检测 PDF 类型
        text_density_threshold = float(self.config.get("TEXT_DENSITY_THRESHOLD", 0.0001))
        pages_to_check = int(self.config.get("PAGES_FOR_CLASSIFICATION", 2))
        pdf_type = detect_pdf_type(pdf_path, text_density_threshold, pages_to_check)
        self.logger.debug(f"检测 PDF 类型: {pdf_type}")

        # Step 2: 初始化 LLM 客户端
        llm_client = self._init_llm_client()

        # Step 3: 分类 PDF
        category = self._classify_pdf(pdf_path, pdf_type, llm_client)
        self.logger.debug(f"分类结果: {category}")

        # Step 4: 获取对应的 subagent
        subagent = self._subagents.get(category, self._subagents["其他"])
        self.logger.info(f"调用 subagent: {subagent.__class__.__name__}")

        # Step 5: 执行 subagent
        subagent_result = subagent.invoke(pdf_path, pdf_type, self.config)

        return {
            "pdf_type": pdf_type,
            "category": category,
            "subagent_result": subagent_result
        }

    def _classify_pdf(self, pdf_path: str, pdf_type: str, llm_client: LLMClient) -> str:
        """
        分类 PDF 文档类型。

        Args:
            pdf_path: PDF 文件路径
            pdf_type: PDF 类型 ("native" 或 "scanned")
            llm_client: LLM 客户端

        Returns:
            分类结果
        """
        try:
            if pdf_type == "native":
                # 原生 PDF：提取文本分类
                content = self._extract_text_for_classification(pdf_path)
                response, _ = llm_client.invoke(
                    system_prompt=CLASSIFY_SYSTEM_PROMPT.format(
                        categories_str=", ".join(PDF_CATEGORIES)
                    ),
                    user_content=CLASSIFY_TEXT_PROMPT.format(content=content),
                    call_name="classify_text"
                )
            else:
                # 扫描件 PDF：图片分类
                response, _ = self._classify_via_images(pdf_path, llm_client)

            # 解析响应
            result = self._parse_classify_response(response)
            category = result.get("category", "其他")
            confidence = result.get("confidence", 0.5)

            self.logger.info(f"分类结果: {category}, 置信度: {confidence}")
            return category

        except Exception as e:
            self.logger.error(f"分类失败: {e}")
            return "其他"

    def _extract_text_for_classification(self, pdf_path: str) -> str:
        """
        提取 PDF 文本用于分类。

        Args:
            pdf_path: PDF 文件路径

        Returns:
            提取的文本内容
        """
        pages_for_classification = int(self.config.get("PAGES_FOR_CLASSIFICATION", 2))

        try:
            import pdfplumber
        except ImportError:
            raise ImportError("未安装 pdfplumber，请运行: pip install pdfplumber")

        text_content = []
        with pdfplumber.open(pdf_path) as pdf:
            pages_to_extract = min(pages_for_classification, len(pdf.pages))
            for i in range(pages_to_extract):
                page = pdf.pages[i]
                text = page.extract_text() or ""
                text_content.append(text)

        return "\n\n".join(text_content)

    def _classify_via_images(self, pdf_path: str, llm_client: LLMClient) -> tuple[str, dict]:
        """
        通过图片进行 PDF 分类。

        Args:
            pdf_path: PDF 文件路径
            llm_client: LLM 客户端

        Returns:
            (响应内容, token使用信息)
        """
        from .pdf_utils import pdf_page_count

        pages_for_classification = int(self.config.get("PAGES_FOR_CLASSIFICATION", 2))
        total_pages = pdf_page_count(pdf_path)
        pages_to_convert = min(pages_for_classification, total_pages)

        self.logger.debug(f"转换前 {pages_to_convert} 页为图片进行分类")

        # 转换为图片
        images = pdf_to_images(pdf_path, list(range(1, pages_to_convert + 1)))

        if not images:
            self.logger.warning("无法转换 PDF 为图片")
            return '{"category": "其他", "confidence": 0.0}', {}

        # 构建多模态内容
        content = []
        for img_base64 in images:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_base64}"
                }
            })
        content.append({
            "type": "text",
            "text": CLASSIFY_IMAGE_PROMPT
        })

        # 调用 LLM 分类
        return llm_client.invoke(
            system_prompt=CLASSIFY_SYSTEM_PROMPT.format(
                categories_str=", ".join(PDF_CATEGORIES)
            ),
            user_content=content,
            call_name="classify_image"
        )

    def _parse_classify_response(self, response: str) -> dict:
        """解析分类响应"""
        import json
        import re

        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取 JSON（使用非贪婪匹配）
            match = re.search(r'\{[^{}]*\}', response)
            if match:
                try:
                    result = json.loads(match.group())
                except json.JSONDecodeError:
                    self.logger.warning(f"无法解析分类响应: {response[:100]}...")
                    return {"category": "其他", "confidence": 0.0}
            else:
                return {"category": "其他", "confidence": 0.0}

        # 验证 category 是否在有效列表中
        category = result.get("category", "其他")
        if category not in PDF_CATEGORIES:
            category = "其他"

        return {
            "category": category,
            "confidence": float(result.get("confidence", 0.5))
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
            token_usage = f.get("subagent_result", {}) or {}
            token_usage = token_usage.get("token_usage", {})
            total_tokens += token_usage.get("total_tokens", 0)

        data["summary"] = {
            "native_count": native_count,
            "scanned_count": scanned_count,
            "category_distribution": category_distribution,
            "total_token_usage": {
                "prompt_tokens": sum(
                    f.get("subagent_result", {}).get("token_usage", {}).get("prompt_tokens", 0)
                    for f in data["files"]
                ),
                "completion_tokens": sum(
                    f.get("subagent_result", {}).get("token_usage", {}).get("completion_tokens", 0)
                    for f in data["files"]
                ),
                "total_tokens": total_tokens
            }
        }

        write_json_output(data, output_file)
        return data

    def _calculate_duration(self, start: str, end: str) -> str:
        """计算耗时"""
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        delta = end_dt - start_dt
        total_seconds = int(delta.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}分{seconds}秒"
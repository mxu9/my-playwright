"""
PDF 分类器主模块：协调各组件完成分类流程
"""
import os
import logging
from pathlib import Path

from .utils import load_config, scan_pdf_files, write_json_output, get_current_timestamp
from .pdf_processor import PDFProcessor
from .llm_client import LLMClient


logger = logging.getLogger(__name__)


class PDFClassifier:
    """PDF 分类器：主入口类"""

    # 必需的配置项
    REQUIRED_CONFIG_KEYS = [
        "API_KEY",
        "BASE_URL",
        "MODEL_NAME",
        "TEXT_DENSITY_THRESHOLD",
        "PAGES_FOR_CLASSIFICATION"
    ]

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

        # 验证必需的配置项
        self._validate_config()

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

    def _validate_config(self):
        """验证配置是否包含所有必需项"""
        for key in self.REQUIRED_CONFIG_KEYS:
            if key not in self.config:
                raise ValueError(f"配置缺少必填项: {key}")

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
                logger.error(f"分类失败: {pdf_path}, 错误: {e}")
                results.append({
                    "filename": Path(pdf_path).name,
                    "file_path": pdf_path,
                    "error": str(e),
                    "pdf_type": "unknown",
                    "category": "其他",
                    "confidence": 0.0,
                    "pages_processed": 0
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
        unknown_count = sum(1 for r in results if r.get("pdf_type") == "unknown")

        # 类别分布
        category_distribution = {}
        for r in results:
            category = r.get("category", "其他")
            category_distribution[category] = category_distribution.get(category, 0) + 1

        return {
            "native_count": native_count,
            "scanned_count": scanned_count,
            "unknown_count": unknown_count,
            "category_distribution": category_distribution
        }
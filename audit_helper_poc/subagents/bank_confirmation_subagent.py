"""
银行询证函处理子代理

处理流程：
1. 使用 PaddleOCR 处理 PDF 所有页面
2. 调用 LLM 定位包含账户信息的页面
3. 将定位到的页面转为图片
4. 调用多模态 LLM 提取结构化信息
"""
import logging
from typing import Optional

from ..base_subagent import BaseSubagent
from ..llm_utils import LLMClient, build_multimodal_content
from ..pdf_utils import pdf_to_images, ocr_pdf_pages, build_marked_text


logger = logging.getLogger(__name__)


# 定位 Prompt
LOCATE_PAGES_SYSTEM_PROMPT = """你是一个金融文档索引专家。你的任务是从一份包含多页的银行询证函 OCR 文本中，识别出哪些页面包含核心账户信息。

核心信息定义：
- 包含"银行账号"、"账号"或"Account Number"的页面
- 包含"币种"、"货币"或"Currency"的页面
- 包含"账户余额"、"期末余额"、"余额"或"Balance"的表格页面

输入说明：
文本将以 [PAGE_X_START] 和 [PAGE_X_END] 标识页码。

输出要求：
- 只返回相关的页码列表，格式为 JSON
- 如果某一项信息跨页，请同时包含相邻页码
- 不要进行任何数据提取，仅输出页码

示例输出：
{"relevant_pages": [1, 2, 5], "reason": "第1-2页包含基本账户列表，第5页包含外币余额明细。"}"""

LOCATE_PAGES_USER_PROMPT = """请分析以下银行询证函 OCR 文本，找出包含账户信息的页面页码。

{marked_text}

请返回页码列表（JSON 格式）："""


# 提取 Prompt
EXTRACT_INFO_SYSTEM_PROMPT = """你是一位资深的银行审计专家。请直接观察提供的询证函页面图片，提取结构化的账户数据。

提取准则：
- 银行账号：完整记录，包含所有空格或横杠，确保数字无误
- 币种：识别 ISO 代码（如 CNY, USD）或中文（如人民币、美元）
- 账户余额：精确到小数点后两位。严禁对数字进行四舍五入
- 账户类型：识别账户性质（如：基本户、一般户、临时户、专用户等）
- 交叉校验：如果图片中存在"大写金额"与"小写金额"，请核对两者是否一致

输出格式：
必须返回标准的 JSON 格式：
{
    "accounts": [
        {
            "bank_name": "银行名称 或 null",
            "account_number": "账号 或 null",
            "account_type": "账户类型 或 null",
            "currency": "币种 或 null",
            "balance": 余额数值 或 null
        }
    ],
    "confidence": 0.0-1.0
}

注意：
- 如果某些信息在图片中找不到，对应字段设为 null
- confidence 表示对提取结果的置信度
- 只返回 JSON，不要其他内容"""

EXTRACT_INFO_USER_PROMPT = "请从以上银行询证函图片中提取账户信息。"


class BankConfirmationSubagent(BaseSubagent):
    """银行询证函处理子代理"""

    # 默认滑动窗口大小（0 = 关闭）
    DEFAULT_WINDOW_SIZE = 0

    def __init__(self):
        self._llm_client: Optional[LLMClient] = None
        self._ocr_engine = None
        self._window_size: int = self.DEFAULT_WINDOW_SIZE

    @property
    def category(self) -> str:
        return "银行询证函"

    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        """
        处理银行询证函 PDF，提取账户信息。

        Args:
            pdf_path: PDF 文件路径
            pdf_type: PDF 类型 ("native" 或 "scanned")
            config: 配置字典 (API_KEY, BASE_URL, MODEL_NAME, etc.)

        Returns:
            处理结果字典
        """
        try:
            # 初始化 LLM 客户端
            self._init_llm_client(config)

            # 读取滑动窗口配置
            self._window_size = int(config.get("BANK_CONFIRMATION_WINDOW_SIZE",
                                               str(self.DEFAULT_WINDOW_SIZE)))

            # Step 1: OCR 所有页面
            logger.info(f"开始 OCR 处理: {pdf_path}")
            page_texts = self._ocr_pages(pdf_path)
            logger.info(f"OCR 完成，共 {len(page_texts)} 页")

            # Step 2: 定位相关页面
            logger.info("正在定位包含账户信息的页面...")
            located_pages = self._locate_pages(page_texts, config)
            logger.info(f"定位到页面: {located_pages}")

            if not located_pages:
                return self._create_error_result("未能定位到包含账户信息的页面", config)

            # Step 3: 转换为图片
            logger.info(f"正在转换页面为图片: {located_pages}")
            images = pdf_to_images(pdf_path, list(located_pages))
            logger.info(f"已转换 {len(images)} 页为图片")

            # Step 4: 提取信息
            logger.info("正在调用 LLM 提取账户信息...")
            data = self._extract_info(images, config)

            return {
                "success": True,
                "data": data,
                "error": None,
                "model": config.get("MODEL_NAME", ""),
                "token_usage": self._llm_client.get_token_summary()
            }

        except Exception as e:
            logger.error(f"处理银行询证函失败: {e}")
            return self._create_error_result(str(e), config)

    def _init_llm_client(self, config: dict):
        """初始化 LLM 客户端"""
        if self._llm_client is None:
            # 读取 TEMPERATURE 配置，默认 0.1
            temperature = float(config.get("TEMPERATURE", "0.1"))
            self._llm_client = LLMClient(
                api_key=config["API_KEY"],
                base_url=config["BASE_URL"],
                model_name=config["MODEL_NAME"],
                temperature=temperature
            )
        else:
            self._llm_client.reset_token_tracker()

    def _ocr_pages(self, pdf_path: str) -> list[str]:
        """OCR 处理所有页面"""
        return ocr_pdf_pages(pdf_path, self._ocr_engine)

    def _locate_pages(self, page_texts: list[str], config: dict) -> list[int]:
        """
        定位包含账户信息的页面。

        Args:
            page_texts: 每页 OCR 文本
            config: 配置

        Returns:
            页码列表（1-indexed）
        """
        # 构建带标记的文本
        marked_text = build_marked_text(page_texts)

        # 调用 LLM
        user_content = LOCATE_PAGES_USER_PROMPT.format(marked_text=marked_text)
        response, _ = self._llm_client.invoke(
            system_prompt=LOCATE_PAGES_SYSTEM_PROMPT,
            user_content=user_content,
            call_name="locate_pages"
        )

        # 解析响应
        pages = self._parse_pages_response(response)

        # 应用滑动窗口（如果启用）
        if self._window_size > 0:
            expanded_pages = self._apply_sliding_window(pages, len(page_texts))
            return sorted(expanded_pages)

        return sorted(pages)

    def _parse_pages_response(self, response: str) -> list[int]:
        """解析 LLM 返回的页码列表"""
        import json
        import re

        try:
            # 尝试直接解析 JSON
            result = json.loads(response)
            # 提取 relevant_pages 字段
            if isinstance(result, dict) and "relevant_pages" in result:
                return result["relevant_pages"]
            elif isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 对象
        match = re.search(r'\{[^{}]*\}', response)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, dict) and "relevant_pages" in result:
                    return result["relevant_pages"]
            except json.JSONDecodeError:
                pass

        # 尝试提取 JSON 数组
        match = re.search(r'\[[\d\s,]+\]', response)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # 尝试提取所有数字
        return [int(n) for n in re.findall(r'\d+', response)]

    def _apply_sliding_window(self, pages: list[int], total_pages: int) -> set[int]:
        """应用滑动窗口，扩展相邻页"""
        expanded = set()

        for page in pages:
            expanded.add(page)
            for offset in range(1, self._window_size + 1):
                if page - offset >= 1:
                    expanded.add(page - offset)
                if page + offset <= total_pages:
                    expanded.add(page + offset)

        return expanded

    def _extract_info(self, images: list[str], config: dict) -> dict:
        """
        提取账户信息。

        Args:
            images: base64 图片列表
            config: 配置

        Returns:
            提取的结构化数据
        """
        # 构建多模态内容
        multimodal_content = build_multimodal_content(images,
                                                       EXTRACT_INFO_USER_PROMPT)

        # 调用 LLM
        result, _ = self._llm_client.invoke_with_json_response(
            system_prompt=EXTRACT_INFO_SYSTEM_PROMPT,
            user_content=multimodal_content,
            call_name="extract_info"
        )

        if result is None:
            return {
                "accounts": [],
                "confidence": 0.0
            }

        return result

    def _create_error_result(self, error: str, config: dict) -> dict:
        """创建错误结果"""
        token_usage = {}
        if self._llm_client:
            token_usage = self._llm_client.get_token_summary()

        return {
            "success": False,
            "data": None,
            "error": error,
            "model": config.get("MODEL_NAME", ""),
            "token_usage": token_usage
        }
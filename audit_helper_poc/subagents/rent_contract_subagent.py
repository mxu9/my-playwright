"""
房租合同处理子代理

处理流程：
1. 使用 PaddleOCR 处理 PDF 所有页面
2. 调用 LLM 定位包含租赁信息的页面
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
LOCATE_PAGES_SYSTEM_PROMPT = """你是一个文档分析助手。你需要从一份租赁合同文档中找出包含"租赁期限和租金情况"的页面。

文档格式说明：
- 每页有明确的边界标记：[PAGE_N_START] 和 [PAGE_N_END]
- N 是页码，从 1 开始

你的任务：
1. 仔细阅读文档内容
2. 找出包含租赁期限、租金金额、支付方式等关键信息的页面
3. 只返回页码列表，格式为 JSON 数组，例如：[1, 3, 5]

注意事项：
1. 只返回 JSON 数组，不要其他内容
2. 如果某页只有标题或无关内容，不要包含
3. 如果某页包含租赁期限、租金金额、支付方式等关键信息，请包含
4. 按页码从小到大排序"""

LOCATE_PAGES_USER_PROMPT = """请分析以下租赁合同文档，找出包含"租赁期限和租金情况"的页面页码。

{marked_text}

请返回页码列表（JSON 数组格式）："""


# 提取 Prompt
EXTRACT_INFO_SYSTEM_PROMPT = """你是一个租赁合同信息提取助手。请从图片中提取以下信息：

1. 租赁期限（起始日期、终止日期、总期限）
2. 租金情况（月租金、年租金、支付方式、支付周期）
3. 双方当事人（房东、租户）
4. 物业地址

请返回 JSON 格式的结果：
{
    "lease_term": {
        "start_date": "YYYY-MM-DD 或 null",
        "end_date": "YYYY-MM-DD 或 null",
        "duration": "X年X个月 或 null"
    },
    "rent": {
        "monthly_rent": 数字 或 null,
        "yearly_rent": 数字 或 null,
        "currency": "货币单位",
        "payment_method": "支付方式 或 null",
        "payment_cycle": "支付周期 或 null"
    },
    "parties": {
        "landlord": "房东名称 或 null",
        "tenant": "租户名称 或 null"
    },
    "property_address": "租赁地址 或 null",
    "confidence": 0.0-1.0
}

注意：
1. 如果某些信息在图片中找不到，对应字段设为 null
2. confidence 表示对提取结果的置信度
3. 只返回 JSON，不要其他内容"""

EXTRACT_INFO_USER_PROMPT = "请从以上租赁合同图片中提取租赁期限和租金信息。"


class RentContractSubagent(BaseSubagent):
    """房租合同处理子代理"""

    # 滑动窗口大小（定位后前后扩展页数）
    WINDOW_SIZE = 1

    def __init__(self):
        self._llm_client: Optional[LLMClient] = None
        self._ocr_engine = None

    @property
    def category(self) -> str:
        return "房租合同"

    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        """
        处理房租合同 PDF，提取结构化信息。

        Args:
            pdf_path: PDF 文件路径
            pdf_type: PDF 类型 ("native" 或 "scanned")
            config: 配置字典 (API_KEY, BASE_URL, MODEL_NAME)

        Returns:
            处理结果字典
        """
        try:
            # 初始化 LLM 客户端
            self._init_llm_client(config)

            # Step 1: OCR 所有页面
            logger.info(f"开始 OCR 处理: {pdf_path}")
            page_texts = self._ocr_pages(pdf_path)
            logger.info(f"OCR 完成，共 {len(page_texts)} 页")

            # Step 2: 定位相关页面
            logger.info("正在定位包含租赁信息的页面...")
            located_pages = self._locate_pages(page_texts, config)
            logger.info(f"定位到页面: {located_pages}")

            if not located_pages:
                return self._create_error_result("未能定位到包含租赁信息的页面", config)

            # Step 3: 转换为图片
            logger.info(f"正在转换页面为图片: {located_pages}")
            images = pdf_to_images(pdf_path, located_pages)
            logger.info(f"已转换 {len(images)} 页为图片")

            # Step 4: 提取信息
            logger.info("正在调用 LLM 提取信息...")
            data = self._extract_info(images, config)

            return {
                "success": True,
                "data": data,
                "error": None,
                "model": config.get("MODEL_NAME", ""),
                "token_usage": self._llm_client.get_token_summary()
            }

        except Exception as e:
            logger.error(f"处理房租合同失败: {e}")
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
        定位包含租赁信息的页面。

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

        # 应用滑动窗口
        expanded_pages = self._apply_sliding_window(pages, len(page_texts))

        return sorted(expanded_pages)

    def _parse_pages_response(self, response: str) -> list[int]:
        """解析 LLM 返回的页码列表"""
        import json
        import re

        try:
            # 尝试直接解析 JSON
            return json.loads(response)
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
            for offset in range(1, self.WINDOW_SIZE + 1):
                if page - offset >= 1:
                    expanded.add(page - offset)
                if page + offset <= total_pages:
                    expanded.add(page + offset)

        return expanded

    def _extract_info(self, images: list[str], config: dict) -> dict:
        """
        提取租赁信息。

        Args:
            images: base64 图片列表
            config: 配置

        Returns:
            提取的结构化数据
        """
        # 构建多模态内容
        multimodal_content = build_multimodal_content(images, EXTRACT_INFO_USER_PROMPT)

        # 调用 LLM
        result, _ = self._llm_client.invoke_with_json_response(
            system_prompt=EXTRACT_INFO_SYSTEM_PROMPT,
            user_content=multimodal_content,
            call_name="extract_info"
        )

        if result is None:
            return {
                "lease_term": None,
                "rent": None,
                "parties": None,
                "property_address": None,
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
"""
天眼查信息处理子代理

处理流程：
1. 将 PDF 所有页面转为图片
2. 调用多模态 LLM 提取企业信息
"""
import logging
from typing import Optional

from ..base_subagent import BaseSubagent
from ..llm_utils import LLMClient, build_multimodal_content
from ..pdf_utils import pdf_to_images


logger = logging.getLogger(__name__)


# 提取 Prompt
EXTRACT_INFO_SYSTEM_PROMPT = """Role: 你是一位资深的金融合规审计专家，精通中国工商登记制度与天眼查报告格式。

Task:
请根据上传天眼查扫描件图片，提取如下企业信息：
"企业名称"，"法定代表人"，"成立日期"，"注册资本"，"登记机关"，"注册地址"，"通信地址"，"经营范围"，"股东信息及持股比例"
并且，在"变更记录"中检查2025年是否有注册资本、经营范围，股东信息的变更记录

Workflow:
视觉扫描：先识别页面布局，区分基本信息区、股东信息区与变更记录区。
数据提取：精确读取字段，若扫描件模糊，请结合上下文（如股东出资额与比例的关系）进行逻辑推算。
逻辑核查：对比"变更记录"中的日期，筛选出所有发生在 2025 年的条目。

Constraints:
对于金额，请统一输出为"XX万人民币"格式。
如果字段确实无法辨认，请返回 null，不要伪造数据。
必须返回严格的 JSON 格式。"""

EXTRACT_INFO_USER_PROMPT = "请分析以上天眼查报告图片，提取企业信息并返回 JSON 格式结果。"

# 期望的 JSON 输出格式（用于提示）
EXPECTED_JSON_FORMAT = """
{
    "企业名称": "string 或 null",
    "法定代表人": "string 或 null",
    "成立日期": "YYYY-MM-DD 或 null",
    "注册资本": "XX万人民币 或 null",
    "登记机关": "string 或 null",
    "注册地址": "string 或 null",
    "通信地址": "string 或 null",
    "经营范围": "string 或 null",
    "股东信息": [
        {
            "股东名称": "string 或 null",
            "持股比例": "百分比 或 null",
            "出资额": "金额 或 null"
        }
    ],
    "2025年变更记录": [
        {
            "变更日期": "YYYY-MM-DD 或 null",
            "变更事项": "注册资本/经营范围/股东信息 或 null",
            "变更前内容": "string 或 null",
            "变更后内容": "string 或 null"
        }
    ],
    "confidence": 0.0-1.0
}"""


class TianyanchaSubagent(BaseSubagent):
    """天眼查信息处理子代理"""

    def __init__(self):
        self._llm_client: Optional[LLMClient] = None

    @property
    def category(self) -> str:
        return "天眼查信息"

    def invoke(self, pdf_path: str, pdf_type: str, config: dict) -> dict:
        """
        处理天眼查 PDF，提取企业信息。

        Args:
            pdf_path: PDF 文件路径
            pdf_type: PDF 类型 ("native" 或 "scanned")
            config: 配置字典 (API_KEY, BASE_URL, MODEL_NAME)

        Returns:
            处理结果字典
        """
        # 检查必要配置
        if not config.get("API_KEY") or not config.get("BASE_URL"):
            logger.error("缺少必要配置: API_KEY 或 BASE_URL")
            return self._create_error_result("缺少必要配置: API_KEY 或 BASE_URL", config)

        try:
            # 初始化 LLM 客户端
            self._init_llm_client(config)

            # Step 1: 将 PDF 所有页面转为图片
            logger.info(f"正在转换 PDF 为图片: {pdf_path}")
            images = pdf_to_images(pdf_path)
            logger.info(f"已转换 {len(images)} 页为图片")

            if not images:
                return self._create_error_result("无法将 PDF 转换为图片", config)

            # Step 2: 调用多模态 LLM 提取信息
            logger.info("正在调用多模态 LLM 提取企业信息...")
            data = self._extract_info(images, config)

            return {
                "success": True,
                "data": data,
                "error": None,
                "model": config.get("MODEL_NAME", ""),
                "token_usage": self._llm_client.get_token_summary()
            }

        except Exception as e:
            logger.error(f"处理天眼查信息失败: {e}")
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

    def _extract_info(self, images: list[str], config: dict) -> dict:
        """
        提取企业信息。

        Args:
            images: base64 图片列表
            config: 配置

        Returns:
            提取的结构化数据
        """
        # 构建完整的系统提示（包含格式说明）
        full_system_prompt = EXTRACT_INFO_SYSTEM_PROMPT + "\n\n请按以下 JSON 格式返回结果：" + EXPECTED_JSON_FORMAT

        # 构建多模态内容
        multimodal_content = build_multimodal_content(images, EXTRACT_INFO_USER_PROMPT)

        # 调用 LLM
        result, _ = self._llm_client.invoke_with_json_response(
            system_prompt=full_system_prompt,
            user_content=multimodal_content,
            call_name="extract_tianyancha_info"
        )

        if result is None:
            logger.warning("LLM 未返回有效的 JSON 结果")
            return {
                "企业名称": None,
                "法定代表人": None,
                "成立日期": None,
                "注册资本": None,
                "登记机关": None,
                "注册地址": None,
                "通信地址": None,
                "经营范围": None,
                "股东信息": [],
                "2025年变更记录": [],
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
"""
LLM 客户端模块：封装 langchain_openai 调用
"""
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


# PDF 类别枚举
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


class LLMClient:
    """LLM 客户端：调用大模型进行 PDF 分类"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str
    ):
        """
        初始化 LLM 客户端

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model_name: 模型名称

        Raises:
            ValueError: 配置无效
        """
        if not api_key:
            raise ValueError("API_KEY 不能为空")

        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

        # 初始化 langchain 客户端
        self.client = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=0.1  # 低温度，更稳定的输出
        )

    def classify(self, content: str | list[str], pdf_type: str) -> dict:
        """
        分类 PDF 内容

        Args:
            content: 文本内容（原生PDF）或 base64 图片列表（扫描件）
            pdf_type: "native" 或 "scanned"

        Returns:
            {"category": str, "confidence": float}
        """
        system_prompt = self._build_system_prompt()

        if pdf_type == "native":
            # 文本分类
            user_message = HumanMessage(
                content=f"请分析以下 PDF 文档内容并分类：\n\n{content}"
            )
        else:
            # 多模态图片分类
            images_content = []
            for img_base64 in content:
                images_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}"
                    }
                })
            # 添加文字提示
            images_content.append({
                "type": "text",
                "text": "请分析以上 PDF 文档图片并分类。"
            })
            user_message = HumanMessage(content=images_content)

        messages = [
            SystemMessage(content=system_prompt),
            user_message
        ]

        response = self.client.invoke(messages)

        # 解析响应
        return self._parse_response(response.content)

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        categories_str = ", ".join(PDF_CATEGORIES)
        return f"""你是一个审计文档分类助手。请根据文档内容判断其类型。

可选的文档类型：
{categories_str}

请返回 JSON 格式的结果：
{{"category": "文档类型", "confidence": 0.0-1.0}}

注意：
1. category 必须是上述类型之一
2. confidence 是置信度，范围 0.0 到 1.0
3. 只返回 JSON，不要其他内容"""

    def _parse_response(self, response_text: str) -> dict:
        """解析 LLM 响应"""
        try:
            # 尝试直接解析 JSON
            result = json.loads(response_text)
            return {
                "category": result.get("category", "其他"),
                "confidence": float(result.get("confidence", 0.5))
            }
        except json.JSONDecodeError:
            # 尝试提取 JSON
            import re
            json_match = re.search(r'\{.*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "category": result.get("category", "其他"),
                    "confidence": float(result.get("confidence", 0.5))
                }
            # 默认返回
            return {"category": "其他", "confidence": 0.0}
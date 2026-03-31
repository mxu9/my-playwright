#!/usr/bin/env python
"""
租赁合同信息提取脚本

从指定的PDF页面中提取租赁期限和租金信息。
"""

import os
import sys
import json
import argparse
import base64
import re
from pathlib import Path
from typing import List, Tuple

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import dotenv_values
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import pypdfium2  # type: ignore
from PIL import Image
from io import BytesIO


class TokenUsageTracker:
    """Token 使用跟踪器"""

    def __init__(self):
        self.calls: List[dict] = []  # 每次 LLM 调用的统计
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0

    def add_call(self, call_name: str, response) -> dict:
        """
        记录一次 LLM 调用的 token 使用

        Args:
            call_name: 调用名称（用于标识）
            response: LLM 响应对象

        Returns:
            本次调用的 token 使用信息
        """
        # 从 response_metadata 中提取 token 使用信息
        token_usage = {}
        if hasattr(response, 'response_metadata') and response.response_metadata:
            usage = response.response_metadata.get('token_usage', {})
            token_usage = {
                "prompt_tokens": usage.get('prompt_tokens', 0),
                "completion_tokens": usage.get('completion_tokens', 0),
                "total_tokens": usage.get('total_tokens', 0)
            }
            # 累加到总计
            self.total_prompt_tokens += token_usage["prompt_tokens"]
            self.total_completion_tokens += token_usage["completion_tokens"]
            self.total_tokens += token_usage["total_tokens"]

        call_info = {
            "call_name": call_name,
            "token_usage": token_usage
        }
        self.calls.append(call_info)
        return call_info

    def get_summary(self) -> dict:
        """获取 token 使用汇总"""
        return {
            "total_calls": len(self.calls),
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "calls_detail": self.calls
        }


def parse_pages(pages_str: str) -> list[int]:
    """
    解析页码字符串

    支持格式：
    - "1,3,5" -> [1, 3, 5]
    - "1-5" -> [1, 2, 3, 4, 5]
    - "1,3-5,7" -> [1, 3, 4, 5, 7]

    Args:
        pages_str: 页码字符串

    Returns:
        页码列表（1-indexed）
    """
    pages = []
    parts = pages_str.split(",")

    for part in parts:
        part = part.strip()
        if "-" in part:
            # 范围，如 "1-5"
            start, end = part.split("-")
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))

    return sorted(set(pages))  # 去重并排序


def pdf_pages_to_images(pdf_path: str, pages: list[int]) -> list[str]:
    """
    将PDF指定页转为base64图片

    Args:
        pdf_path: PDF文件路径
        pages: 页码列表（1-indexed）

    Returns:
        base64编码的图片列表
    """
    pdf = pypdfium2.PdfDocument(pdf_path)
    base64_images = []

    try:
        for page_num in pages:
            # pypdfium2 使用 0-indexed
            page_index = page_num - 1

            if page_index < 0 or page_index >= len(pdf):
                print(f"警告: 页码 {page_num} 超出范围，跳过")
                continue

            page = pdf[page_index]
            # 渲染为图片
            bitmap = page.render(scale=2)  # scale=2 提高清晰度
            pil_image = bitmap.to_pil()

            # 转为base64
            buffered = BytesIO()
            pil_image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
            base64_images.append(img_base64)

    finally:
        pdf.close()

    return base64_images


def extract_lease_info(
    images: list[str],
    api_key: str,
    base_url: str,
    model_name: str,
    token_tracker: TokenUsageTracker = None
) -> Tuple[dict, dict]:
    """
    使用多模态大模型提取租赁信息

    Args:
        images: base64图片列表
        api_key: API密钥
        base_url: API基础URL
        model_name: 模型名称
        token_tracker: Token使用跟踪器（可选）

    Returns:
        (提取的结构化信息, 本次调用的token使用信息)
    """
    client = ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
        temperature=0.1
    )

    # 构建系统提示
    system_prompt = """你是一个租赁合同信息提取助手。请从图片中提取以下信息：

1. 租赁期限（起始日期、终止日期、总期限）
2. 租金情况（月租金、年租金、支付方式、支付周期）

请返回 JSON 格式的结果：
{
    "lease_term": {
        "start_date": "起始日期（YYYY-MM-DD格式，如无法确定则为null）",
        "end_date": "终止日期（YYYY-MM-DD格式，如无法确定则为null）",
        "duration": "总期限描述（如'1年'、'6个月'等）"
    },
    "rent": {
        "monthly_rent": "月租金金额（数字，如无法确定则为null）",
        "yearly_rent": "年租金金额（数字，如无法确定则为null）",
        "currency": "货币单位（如'人民币'、'元'等）",
        "payment_method": "支付方式（如'银行转账'、'现金'等，如无法确定则为null）",
        "payment_cycle": "支付周期（如'月付'、'季付'、'年付'等）"
    },
    "other_terms": "其他重要条款摘要",
    "confidence": "置信度（0.0-1.0）"
}

注意：
1. 如果某些信息在图片中找不到，对应字段设为null
2. 只返回JSON，不要其他内容
3. 置信度表示对提取结果的确定程度"""

    # 构建用户消息（多张图片）
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
        "text": "请从以上租赁合同图片中提取租赁期限和租金信息。"
    })

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=content)
    ]

    token_usage_info = {}

    try:
        response = client.invoke(messages)
        result_text = response.content

        # 记录 token 使用
        if token_tracker:
            call_info = token_tracker.add_call("extract_lease_info", response)
            token_usage_info = call_info['token_usage']

        # 尝试解析JSON
        json_match = re.search(r"\{[\s\S]*\}", result_text)
        if json_match:
            return json.loads(json_match.group()), token_usage_info
        else:
            return {"error": "无法解析模型响应", "raw_response": result_text}, token_usage_info

    except Exception as e:
        return {"error": str(e)}, token_usage_info


def load_config() -> dict:
    """加载配置"""
    config_path = Path(__file__).parent / ".env"
    config = dotenv_values(config_path)

    required_keys = ["API_KEY", "BASE_URL", "MODEL_NAME"]
    for key in required_keys:
        if key not in config:
            raise ValueError(f"配置缺少必填项: {key}")

    return dict(config)


def main():
    parser = argparse.ArgumentParser(description="从租赁合同PDF中提取信息")
    parser.add_argument("pdf_path", help="PDF文件路径")
    parser.add_argument("-p", "--pages", required=True, help="页码，如 '1,3,5' 或 '1-5' 或 '1,3-5,7'")
    parser.add_argument("-o", "--output", help="输出JSON文件路径（可选）")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细信息")

    args = parser.parse_args()

    # 检查文件是否存在
    if not os.path.exists(args.pdf_path):
        print(f"错误: 文件不存在: {args.pdf_path}")
        sys.exit(1)

    # 加载配置
    try:
        config = load_config()
    except Exception as e:
        print(f"错误: 加载配置失败: {e}")
        sys.exit(1)

    # 解析页码
    pages = parse_pages(args.pages)
    if args.verbose:
        print(f"将处理第 {pages} 页")

    # 转换PDF页面为图片
    print(f"正在转换PDF页面...")
    images = pdf_pages_to_images(args.pdf_path, pages)
    print(f"已转换 {len(images)} 页为图片")

    if not images:
        print("错误: 没有成功转换任何页面")
        sys.exit(1)

    # 初始化 token 跟踪器
    token_tracker = TokenUsageTracker()

    # 提取租赁信息
    print(f"正在调用大模型提取信息（模型: {config['MODEL_NAME']}）...")
    result, call_token_usage = extract_lease_info(
        images=images,
        api_key=config["API_KEY"],
        base_url=config["BASE_URL"],
        model_name=config["MODEL_NAME"],
        token_tracker=token_tracker
    )

    # 显示本次调用 token 使用
    if call_token_usage:
        print(f"本次调用 Token: 输入={call_token_usage.get('prompt_tokens', 0):,}, "
              f"输出={call_token_usage.get('completion_tokens', 0):,}, "
              f"总计={call_token_usage.get('total_tokens', 0):,}")

    # 获取 token 统计汇总
    token_summary = token_tracker.get_summary()

    # 添加元数据
    output = {
        "source_file": os.path.basename(args.pdf_path),
        "pages_processed": pages,
        "model": config["MODEL_NAME"],
        "extraction_result": result,
        "token_usage": token_summary
    }

    # 输出结果
    output_json = json.dumps(output, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"结果已保存到: {args.output}")
    else:
        print("\n" + "=" * 50)
        print("提取结果:")
        print("=" * 50)
        print(output_json)

    # 显示 Token 使用统计汇总
    print("\n" + "=" * 50)
    print("Token 使用统计:")
    print("=" * 50)
    print(f"LLM 调用次数: {token_summary.get('total_calls', 0)}")
    print(f"总输入 Token: {token_summary.get('total_prompt_tokens', 0):,}")
    print(f"总输出 Token: {token_summary.get('total_completion_tokens', 0):,}")
    print(f"总 Token 数: {token_summary.get('total_tokens', 0):,}")


if __name__ == "__main__":
    main()
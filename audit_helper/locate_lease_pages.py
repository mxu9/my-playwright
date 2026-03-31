#!/usr/bin/env python
"""
租赁合同页面定位脚本

使用 PaddleOCR 处理 PDF，通过大模型判断哪些页面包含租赁信息和租金信息。
"""

import os
import sys
import json
import argparse
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

# PaddleOCR 导入
try:
    from paddleocr import PaddleOCR
except ImportError:
    print("错误: 未安装 PaddleOCR，请运行: pip install paddleocr")
    sys.exit(1)


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


class PDFPageLocator:
    """PDF 页面定位器：使用 OCR 和 LLM 定位包含特定信息的页面"""

    def __init__(self, config_path: str = ".env"):
        """
        初始化定位器

        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        config_file = Path(__file__).parent / config_path
        self.config = dict(dotenv_values(config_file))

        required_keys = ["API_KEY", "BASE_URL", "MODEL_NAME"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"配置缺少必填项: {key}")

        # 初始化 PaddleOCR
        print("正在初始化 PaddleOCR...")
        self.ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)

        # 初始化 LLM 客户端
        self.llm = ChatOpenAI(
            api_key=self.config["API_KEY"],
            base_url=self.config["BASE_URL"],
            model=self.config["MODEL_NAME"],
            temperature=0.1
        )

        # 初始化 token 使用跟踪器
        self.token_tracker = TokenUsageTracker()

    def pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """
        将 PDF 所有页转为 PIL 图片列表

        Args:
            pdf_path: PDF 文件路径

        Returns:
            PIL 图片列表
        """
        pdf = pypdfium2.PdfDocument(pdf_path)
        images = []

        try:
            for page_index in range(len(pdf)):
                page = pdf[page_index]
                bitmap = page.render(scale=2)
                pil_image = bitmap.to_pil()
                images.append(pil_image)
        finally:
            pdf.close()

        return images

    def ocr_image(self, image: Image.Image) -> str:
        """
        使用 PaddleOCR 识别图片中的文字

        Args:
            image: PIL 图片

        Returns:
            识别的文本
        """
        # PaddleOCR 需要 numpy 数组或文件路径
        import numpy as np
        img_array = np.array(image)

        result = self.ocr.ocr(img_array, cls=True)

        # 提取文本
        text_lines = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    text = line[1][0]  # (坐标, (文本, 置信度))
                    text_lines.append(text)

        return "\n".join(text_lines)

    def process_pdf(self, pdf_path: str) -> List[str]:
        """
        处理 PDF，返回每页的 OCR 文本

        Args:
            pdf_path: PDF 文件路径

        Returns:
            每页文本列表
        """
        print(f"正在处理 PDF: {pdf_path}")

        # 转为图片
        images = self.pdf_to_images(pdf_path)
        print(f"共 {len(images)} 页")

        # OCR 每页
        page_texts = []
        for i, image in enumerate(images):
            print(f"  OCR 处理第 {i + 1} 页...")
            text = self.ocr_image(image)
            page_texts.append(text)

        return page_texts

    def build_marked_text(self, page_texts: List[str]) -> str:
        """
        构建带页码标记的长文本

        Args:
            page_texts: 每页文本列表

        Returns:
            带标记的长文本
        """
        sections = []
        for i, text in enumerate(page_texts):
            page_num = i + 1
            section = f"[PAGE_{page_num}_START]\n{text}\n[PAGE_{page_num}_END]"
            sections.append(section)

        return "\n\n".join(sections)

    def locate_pages(
        self,
        marked_text: str,
        target_info: str = "租赁期限和租金情况",
        window_size: int = 1
    ) -> Tuple[List[int], str]:
        """
        使用 LLM 定位包含目标信息的页面

        Args:
            marked_text: 带标记的文本
            target_info: 目标信息描述
            window_size: 滑动窗口大小（前后各扩展几页）

        Returns:
            (页码列表, LLM 原始响应)
        """
        system_prompt = f"""你是一个文档分析助手。你需要从一份租赁合同文档中找出包含"{target_info}"的页面。

文档格式说明：
- 每页有明确的边界标记：[PAGE_N_START] 和 [PAGE_N_END]
- N 是页码，从 1 开始

你的任务：
1. 仔细阅读文档内容
2. 找出包含"{target_info}"相关信息的页面
3. 只返回页码列表，格式为 JSON 数组，例如：[1, 3, 5]

注意事项：
1. 只返回 JSON 数组，不要其他内容
2. 如果某页只有标题或无关内容，不要包含
3. 如果某页包含租赁期限、租金金额、支付方式等关键信息，请包含
4. 按页码从小到大排序"""

        user_message = f"""请分析以下租赁合同文档，找出包含"{target_info}"的页面页码。

{marked_text}

请返回页码列表（JSON 数组格式）："""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]

        print(f"正在调用大模型分析文档...")
        response = self.llm.invoke(messages)
        response_text = response.content

        # 记录 token 使用
        call_info = self.token_tracker.add_call("locate_pages", response)
        print(f"本次调用 Token: 输入={call_info['token_usage']['prompt_tokens']}, "
              f"输出={call_info['token_usage']['completion_tokens']}, "
              f"总计={call_info['token_usage']['total_tokens']}")

        # 解析响应
        try:
            # 尝试提取 JSON 数组
            json_match = re.search(r'\[[\d\s,]+\]', response_text)
            if json_match:
                pages = json.loads(json_match.group())
            else:
                # 尝试解析整个响应
                pages = json.loads(response_text)

            # 确保是整数列表
            pages = [int(p) for p in pages]

        except (json.JSONDecodeError, ValueError):
            # 尝试提取数字
            pages = [int(n) for n in re.findall(r'\d+', response_text)]

        # 应用滑动窗口
        total_pages = marked_text.count("[PAGE_") // 2
        expanded_pages = set()

        for page in pages:
            # 添加当前页
            expanded_pages.add(page)
            # 添加窗口内的相邻页
            for offset in range(1, window_size + 1):
                if page - offset >= 1:
                    expanded_pages.add(page - offset)
                if page + offset <= total_pages:
                    expanded_pages.add(page + offset)

        return sorted(expanded_pages), response_text

    def run(
        self,
        pdf_path: str,
        target_info: str = "租赁期限和租金情况",
        window_size: int = 1,
        verbose: bool = False
    ) -> dict:
        """
        执行完整的定位流程

        Args:
            pdf_path: PDF 文件路径
            target_info: 目标信息描述
            window_size: 滑动窗口大小
            verbose: 是否显示详细信息

        Returns:
            结果字典
        """
        # 处理 PDF
        page_texts = self.process_pdf(pdf_path)

        # 构建带标记的文本
        marked_text = self.build_marked_text(page_texts)

        if verbose:
            print("\n" + "=" * 50)
            print("带标记的文本预览（前2000字符）:")
            print("=" * 50)
            print(marked_text[:2000])
            print("...")
            print("=" * 50)

        # 定位页面
        pages, llm_response = self.locate_pages(marked_text, target_info, window_size)

        # 构建结果
        token_summary = self.token_tracker.get_summary()
        result = {
            "source_file": os.path.basename(pdf_path),
            "total_pages": len(page_texts),
            "target_info": target_info,
            "window_size": window_size,
            "core_pages": [p for p in pages if p in json.loads(re.search(r'\[[\d\s,]+\]', llm_response).group() or '[]')
                          if re.search(r'\[[\d\s,]+\]', llm_response)] if re.search(r'\[[\d\s,]+\]', llm_response) else pages,
            "located_pages": pages,
            "page_texts": {i + 1: text for i, text in enumerate(page_texts)},
            "token_usage": token_summary
        }

        return result


def main():
    parser = argparse.ArgumentParser(description="租赁合同页面定位工具")
    parser.add_argument("pdf_path", help="PDF文件路径")
    parser.add_argument(
        "-t", "--target",
        default="租赁期限和租金情况",
        help="目标信息描述（默认：租赁期限和租金情况）"
    )
    parser.add_argument(
        "-w", "--window",
        type=int,
        default=1,
        help="滑动窗口大小，前后各扩展几页（默认：1）"
    )
    parser.add_argument(
        "-o", "--output",
        help="输出JSON文件路径（可选）"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细信息"
    )

    args = parser.parse_args()

    # 检查文件是否存在
    if not os.path.exists(args.pdf_path):
        print(f"错误: 文件不存在: {args.pdf_path}")
        sys.exit(1)

    # 创建定位器并执行
    try:
        locator = PDFPageLocator()
        result = locator.run(
            pdf_path=args.pdf_path,
            target_info=args.target,
            window_size=args.window,
            verbose=args.verbose
        )

        # 输出结果
        print("\n" + "=" * 50)
        print("定位结果:")
        print("=" * 50)
        print(f"文件: {result['source_file']}")
        print(f"总页数: {result['total_pages']}")
        print(f"目标信息: {result['target_info']}")
        print(f"滑动窗口大小: {result['window_size']}")
        print(f"\n定位到的页面: {result['located_pages']}")

        # 显示 Token 使用统计
        token_usage = result.get('token_usage', {})
        if token_usage:
            print("\n" + "=" * 50)
            print("Token 使用统计:")
            print("=" * 50)
            print(f"LLM 调用次数: {token_usage.get('total_calls', 0)}")
            print(f"总输入 Token: {token_usage.get('total_prompt_tokens', 0):,}")
            print(f"总输出 Token: {token_usage.get('total_completion_tokens', 0):,}")
            print(f"总 Token 数: {token_usage.get('total_tokens', 0):,}")
            if token_usage.get('calls_detail'):
                print("\n每次调用详情:")
                for i, call in enumerate(token_usage['calls_detail'], 1):
                    usage = call['token_usage']
                    print(f"  [{i}] {call['call_name']}: "
                          f"输入={usage['prompt_tokens']:,}, "
                          f"输出={usage['completion_tokens']:,}, "
                          f"总计={usage['total_tokens']:,}")

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n结果已保存到: {args.output}")

        # 显示每页的文本摘要
        if args.verbose:
            print("\n" + "=" * 50)
            print("各页文本摘要:")
            print("=" * 50)
            for page_num, text in result["page_texts"].items():
                preview = text[:100] + "..." if len(text) > 100 else text
                marker = " [目标页]" if page_num in result["located_pages"] else ""
                print(f"第 {page_num} 页{marker}: {preview}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
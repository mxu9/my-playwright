"""
PDF 工具模块：PDF 转图片、OCR 等工具函数

注意：PDF 旋转纠偏已移至 pdf_preprocessor.py，调用此模块前应先进行预处理。
"""
import base64
import logging
from io import BytesIO
from pathlib import Path
from typing import List, Optional

import pypdfium2  # type: ignore
from PIL import Image

logger = logging.getLogger(__name__)


def pdf_to_images(pdf_path: str, pages: Optional[List[int]] = None) -> List[str]:
    """
    将 PDF 指定页转为 base64 图片列表。

    注意：调用此函数前，PDF 应已通过预处理纠偏。

    Args:
        pdf_path: PDF 文件路径（预处理后的）
        pages: 页码列表（1-indexed），为 None 时转换所有页

    Returns:
        base64 编码的图片列表

    Raises:
        FileNotFoundError: PDF 文件不存在
        ValueError: 页码超出范围
    """
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    pdf = pypdfium2.PdfDocument(pdf_path)
    base64_images = []

    try:
        # 确定要转换的页码
        if pages is None:
            page_indices = range(len(pdf))
        else:
            # 转换为 0-indexed
            page_indices = [p - 1 for p in pages]

        for page_index in page_indices:
            if page_index < 0 or page_index >= len(pdf):
                logger.warning(f"页码 {page_index + 1} 超出范围，跳过")
                continue

            page = pdf[page_index]
            # 渲染为图片 (scale=2 提高清晰度)
            bitmap = page.render(scale=2)
            pil_image = bitmap.to_pil()

            # 转为 base64
            buffered = BytesIO()
            pil_image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
            base64_images.append(img_base64)

    finally:
        pdf.close()

    return base64_images


def pdf_page_count(pdf_path: str) -> int:
    """
    获取 PDF 页数。

    Args:
        pdf_path: PDF 文件路径

    Returns:
        页数
    """
    pdf = pypdfium2.PdfDocument(pdf_path)
    try:
        return len(pdf)
    finally:
        pdf.close()


def pdf_page_to_image(pdf_path: str, page_number: int) -> str:
    """
    将 PDF 单页转为 base64 图片。

    Args:
        pdf_path: PDF 文件路径
        page_number: 页码（1-indexed）

    Returns:
        base64 编码的图片
    """
    images = pdf_to_images(pdf_path, [page_number])
    if not images:
        raise ValueError(f"无法转换第 {page_number} 页")
    return images[0]


def ocr_pdf_pages(pdf_path: str, ocr_engine=None) -> List[str]:
    """
    使用 OCR 处理 PDF 所有页面，返回每页文本列表。

    Args:
        pdf_path: PDF 文件路径
        ocr_engine: OCR 引擎实例（PaddleOCR），为 None 时自动创建

    Returns:
        每页文本列表
    """
    # 延迟导入 PaddleOCR
    if ocr_engine is None:
        try:
            from paddleocr import PaddleOCR
            logger.info("正在初始化 PaddleOCR...")
            ocr_engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        except ImportError:
            raise ImportError("未安装 PaddleOCR，请运行: pip install paddleocr")

    import numpy as np

    pdf = pypdfium2.PdfDocument(pdf_path)
    page_texts = []

    try:
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            # 渲染为图片
            bitmap = page.render(scale=2)
            pil_image = bitmap.to_pil()
            img_array = np.array(pil_image)

            # OCR 识别
            result = ocr_engine.ocr(img_array, cls=True)

            # 提取文本
            text_lines = []
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) >= 2:
                        text = line[1][0]  # (坐标, (文本, 置信度))
                        text_lines.append(text)

            page_texts.append("\n".join(text_lines))

    finally:
        pdf.close()

    return page_texts


def build_marked_text(page_texts: List[str]) -> str:
    """
    构建带页码标记的长文本。

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


def detect_pdf_type(pdf_path: str, text_density_threshold: float = 0.0001, pages_to_check: int = 2) -> str:
    """
    检测 PDF 类型：native（原生可提取文本）或 scanned（扫描件需 OCR）。

    使用 pdfplumber 提取文本，计算文本密度判断类型。

    Args:
        pdf_path: PDF 文件路径
        text_density_threshold: 文本密度阈值，默认 0.0001
            (总字符数 / 总页面面积)
        pages_to_check: 检查的前 N 页，默认 2

    Returns:
        "native" 或 "scanned"
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("未安装 pdfplumber，请运行: pip install pdfplumber")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_chars = 0
            total_area = 0

            # 检查前 N 页
            pages = min(pages_to_check, len(pdf.pages))

            for i in range(pages):
                page = pdf.pages[i]
                text = page.extract_text() or ""
                total_chars += len(text)

                # 页面面积
                width = page.width
                height = page.height
                total_area += width * height

            if total_area == 0:
                return "scanned"

            # 文本密度计算
            density = total_chars / total_area
            logger.debug(f"PDF 文本密度: {density:.6f}, 阈值: {text_density_threshold}")

            return "native" if density >= text_density_threshold else "scanned"

    except Exception as e:
        logger.warning(f"处理 PDF 时出错 ({pdf_path}): {e}")
        return "scanned"
"""
PDF 工具模块：PDF 转图片、OCR 等工具函数
"""
import base64
import logging
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple, Dict

import numpy as np
import pypdfium2  # type: ignore
from PIL import Image

logger = logging.getLogger(__name__)

# 低字符数阈值（低于此值时参考相邻页面角度）
LOW_CHAR_THRESHOLD = 200

# 测试的旋转角度
TEST_ANGLES = [0, 90, 180, 270]


# 全局 OCR 实例（延迟初始化）
_ocr_instance = None


def _get_ocr_instance():
    """获取 OCR 实例（延迟初始化，关闭自动角度纠正）"""
    global _ocr_instance
    if _ocr_instance is None:
        try:
            from paddleocr import PaddleOCR
            logger.info("正在初始化 PaddleOCR（关闭自动角度纠正）...")
            _ocr_instance = PaddleOCR(use_angle_cls=False, lang="ch", show_log=False)
        except ImportError:
            raise ImportError("未安装 PaddleOCR，请运行: pip install paddleocr")
    return _ocr_instance


def _detect_rotation_by_ocr(img: Image.Image) -> Tuple[int, int, Dict]:
    """
    通过 OCR 识别效果检测最佳旋转角度。

    Args:
        img: PIL Image

    Returns:
        (最佳角度, 识别字符数, 各角度详细结果)
    """
    ocr = _get_ocr_instance()

    img_array = np.array(img)
    results = {}

    for angle in TEST_ANGLES:
        rotated = img.rotate(angle, expand=True)
        arr = np.array(rotated)

        # OCR 识别
        ocr_result = ocr.ocr(arr, cls=False)

        if ocr_result and ocr_result[0]:
            total_chars = sum(len(line[1][0]) for line in ocr_result[0])
            region_count = len(ocr_result[0])
        else:
            total_chars = 0
            region_count = 0

        results[angle] = {
            "total_chars": total_chars,
            "region_count": region_count
        }

    # 选择识别字符最多的角度
    best_angle = max(results.keys(), key=lambda a: results[a]["total_chars"])
    best_chars = results[best_angle]["total_chars"]

    return best_angle, best_chars, results


def _correct_rotation(img: Image.Image, angle: int) -> Image.Image:
    """
    纠正图片旋转角度。

    Args:
        img: PIL Image
        angle: 需要旋转的角度

    Returns:
        纠正后的 PIL Image
    """
    if angle == 0:
        return img
    return img.rotate(angle, expand=True)


def pdf_to_images(pdf_path: str, pages: Optional[List[int]] = None, auto_rotate: bool = True) -> List[str]:
    """
    将 PDF 指定页转为 base64 图片列表。

    Args:
        pdf_path: PDF 文件路径
        pages: 页码列表（1-indexed），为 None 时转换所有页
        auto_rotate: 是否自动检测并纠正旋转角度，默认 True

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

        # 收集所有页面图片和检测结果
        page_data = []

        for page_index in page_indices:
            if page_index < 0 or page_index >= len(pdf):
                logger.warning(f"页码 {page_index + 1} 超出范围，跳过")
                continue

            page = pdf[page_index]
            # 渲染为图片 (scale=2 提高清晰度)
            bitmap = page.render(scale=2)
            pil_image = bitmap.to_pil()

            page_data.append({
                "index": page_index,
                "image": pil_image
            })

        # 如果需要自动旋转检测
        if auto_rotate and page_data:
            logger.info("正在检测并纠正旋转角度...")

            # 第一轮：检测每页角度
            detections = []
            for item in page_data:
                img = item["image"]
                best_angle, best_chars, ocr_results = _detect_rotation_by_ocr(img)
                detections.append({
                    "index": item["index"],
                    "image": img,
                    "best_angle": best_angle,
                    "best_chars": best_chars,
                    "ocr_results": ocr_results
                })
                logger.debug(f"第 {item['index'] + 1} 页: 检测角度={best_angle}°, 字符数={best_chars}")

            # 第二轮：确定最终角度（低字符数页面参考相邻页面）
            for i, d in enumerate(detections):
                img = d["image"]
                best_angle = d["best_angle"]
                best_chars = d["best_chars"]
                ocr_results = d["ocr_results"]

                final_angle = best_angle

                # 低字符数页面：参考相邻高字符数页面
                if best_chars < LOW_CHAR_THRESHOLD:
                    neighbor_angles = []
                    neighbor_chars_list = []

                    # 向前查找
                    for j in range(i - 1, -1, -1):
                        if detections[j]["best_chars"] >= LOW_CHAR_THRESHOLD:
                            neighbor_angles.append(detections[j]["best_angle"])
                            neighbor_chars_list.append(detections[j]["best_chars"])
                            break

                    # 向后查找
                    for j in range(i + 1, len(detections)):
                        if detections[j]["best_chars"] >= LOW_CHAR_THRESHOLD:
                            neighbor_angles.append(detections[j]["best_angle"])
                            neighbor_chars_list.append(detections[j]["best_chars"])
                            break

                    if neighbor_angles:
                        # 使用相邻页面中字符数更多的那个作为参考
                        if len(neighbor_angles) == 1:
                            neighbor_angle = neighbor_angles[0]
                        else:
                            max_idx = neighbor_chars_list.index(max(neighbor_chars_list))
                            neighbor_angle = neighbor_angles[max_idx]

                        # 检查相邻角度的 OCR 效果是否接近最佳
                        neighbor_chars = ocr_results.get(neighbor_angle, {}).get("total_chars", 0)
                        if neighbor_chars >= best_chars * 0.9:
                            if neighbor_angle != best_angle:
                                final_angle = neighbor_angle
                                logger.debug(f"第 {d['index'] + 1} 页: 低字符数({best_chars})，参考相邻页面角度 {neighbor_angle}°")

                # 纠正旋转
                if final_angle != 0:
                    img = _correct_rotation(img, final_angle)
                    logger.info(f"第 {d['index'] + 1} 页: 旋转纠正 {final_angle}°")

                # 转为 base64
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                base64_images.append(img_base64)
        else:
            # 不需要旋转检测，直接转换
            for item in page_data:
                img = item["image"]
                buffered = BytesIO()
                img.save(buffered, format="PNG")
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
"""
PDF 处理模块：类型判断与内容提取
"""
import base64
import logging
from io import BytesIO

import pdfplumber
import pypdfium2 as pdfium


logger = logging.getLogger(__name__)


class PDFProcessor:
    """PDF 处理器：判断类型并提取内容"""

    def __init__(
        self,
        text_density_threshold: float = 0.0001,
        pages_for_classification: int = 2
    ):
        """
        初始化 PDF 处理器

        Args:
            text_density_threshold: 文本密度阈值，低于此值判定为扫描件
            pages_for_classification: 用于分类的前 N 页
        """
        self.text_density_threshold = text_density_threshold
        self.pages_for_classification = pages_for_classification

    def process(self, pdf_path: str) -> dict:
        """
        处理 PDF 文件，判断类型并提取内容

        Args:
            pdf_path: PDF 文件路径

        Returns:
            {
                "pdf_type": "native" | "scanned",
                "content": str | list[str],
                "pages_processed": int
            }
        """
        is_native = self._is_native_pdf(pdf_path)

        if is_native:
            content = self._extract_text(pdf_path, self.pages_for_classification)
            pdf_type = "native"
        else:
            content = self._extract_images(pdf_path, self.pages_for_classification)
            pdf_type = "scanned"

        return {
            "pdf_type": pdf_type,
            "content": content,
            "pages_processed": self.pages_for_classification
        }

    def _is_native_pdf(self, pdf_path: str) -> bool:
        """
        判断是否为原生 PDF

        Args:
            pdf_path: PDF 文件路径

        Returns:
            True 表示原生 PDF，False 表示扫描件
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_chars = 0
                total_area = 0

                # 检查前 N 页
                pages_to_check = min(self.pages_for_classification, len(pdf.pages))

                for i in range(pages_to_check):
                    page = pdf.pages[i]
                    text = page.extract_text() or ""
                    total_chars += len(text)

                    # 页面面积（像素单位）
                    width = page.width
                    height = page.height
                    total_area += width * height

                if total_area == 0:
                    return False

                # 文本密度计算
                density = total_chars / total_area

                return density >= self.text_density_threshold

        except Exception as e:
            # 无法打开或处理，记录警告并默认视为扫描件
            logger.warning(f"处理 PDF 时出错 ({pdf_path}): {e}")
            return False

    def _extract_text(self, pdf_path: str, pages: int) -> str:
        """
        从原生 PDF 提取文本内容

        Args:
            pdf_path: PDF 文件路径
            pages: 提取的页数

        Returns:
            提取的文本内容
        """
        text_content = []

        with pdfplumber.open(pdf_path) as pdf:
            pages_to_extract = min(pages, len(pdf.pages))

            for i in range(pages_to_extract):
                page = pdf.pages[i]
                text = page.extract_text() or ""
                text_content.append(text)

        return "\n\n".join(text_content)

    def _extract_images(self, pdf_path: str, pages: int) -> list[str]:
        """
        将扫描件 PDF 转为图片并返回 base64 编码列表

        Args:
            pdf_path: PDF 文件路径
            pages: 转换的页数

        Returns:
            base64 编码的图片列表
        """
        pdf = pdfium.PdfDocument(pdf_path)
        try:
            pages_to_extract = min(pages, len(pdf))

            base64_images = []
            for i in range(pages_to_extract):
                page = pdf.get_page(i)
                # 渲染页面为图片，scale=200/72 约等于 200 DPI
                bitmap = page.render(scale=200 / 72)
                pil_image = bitmap.to_pil()

                # 转为 base64
                buffered = BytesIO()
                pil_image.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                base64_images.append(img_base64)

            return base64_images
        finally:
            pdf.close()
"""
测试 PDF 工具模块
"""
import pytest
import base64
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock
from PIL import Image

from audit_helper_poc.pdf_utils import (
    pdf_to_images,
    pdf_page_count,
    pdf_page_to_image,
    build_marked_text,
    detect_pdf_type
)


class TestPdfToImages:
    """测试 pdf_to_images"""

    def test_file_not_found(self):
        """测试文件不存在"""
        with pytest.raises(FileNotFoundError):
            pdf_to_images("/nonexistent/path.pdf")

    def test_pdf_to_images_all_pages(self, tmp_path):
        """测试转换所有页"""
        # 创建一个简单的测试 PDF（需要 pypdfium2）
        # 由于无法直接创建 PDF，使用 mock
        with patch('audit_helper_poc.pdf_utils.pypdfium2.PdfDocument') as mock_pdf:
            # 设置 mock
            mock_page = MagicMock()
            mock_bitmap = MagicMock()
            mock_pil_image = Image.new('RGB', (100, 100), color='white')
            mock_bitmap.to_pil.return_value = mock_pil_image
            mock_page.render.return_value = mock_bitmap

            mock_instance = MagicMock()
            mock_instance.__len__ = Mock(return_value=2)
            mock_instance.__getitem__ = Mock(side_effect=[mock_page, mock_page])
            mock_instance.close = Mock()
            mock_pdf.return_value = mock_instance

            # 创建临时文件
            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf content")

            images = pdf_to_images(str(pdf_file))

            assert len(images) == 2
            assert all(isinstance(img, str) for img in images)
            # 验证是有效的 base64
            for img in images:
                decoded = base64.b64decode(img)
                assert len(decoded) > 0

    def test_pdf_to_images_specific_pages(self, tmp_path):
        """测试转换指定页"""
        with patch('audit_helper_poc.pdf_utils.pypdfium2.PdfDocument') as mock_pdf:
            mock_page = MagicMock()
            mock_bitmap = MagicMock()
            mock_pil_image = Image.new('RGB', (100, 100), color='white')
            mock_bitmap.to_pil.return_value = mock_pil_image
            mock_page.render.return_value = mock_bitmap

            mock_instance = MagicMock()
            mock_instance.__len__ = Mock(return_value=5)
            mock_instance.__getitem__ = Mock(return_value=mock_page)
            mock_instance.close = Mock()
            mock_pdf.return_value = mock_instance

            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf content")

            images = pdf_to_images(str(pdf_file), pages=[1, 3])

            assert len(images) == 2


class TestPdfPageCount:
    """测试 pdf_page_count"""

    def test_page_count(self, tmp_path):
        """测试获取页数"""
        with patch('audit_helper_poc.pdf_utils.pypdfium2.PdfDocument') as mock_pdf:
            mock_instance = MagicMock()
            mock_instance.__len__ = Mock(return_value=10)
            mock_instance.close = Mock()
            mock_pdf.return_value = mock_instance

            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf content")

            count = pdf_page_count(str(pdf_file))

            assert count == 10


class TestPdfPageToImage:
    """测试 pdf_page_to_image"""

    def test_single_page(self, tmp_path):
        """测试转换单页"""
        with patch('audit_helper_poc.pdf_utils.pypdfium2.PdfDocument') as mock_pdf:
            mock_page = MagicMock()
            mock_bitmap = MagicMock()
            mock_pil_image = Image.new('RGB', (100, 100), color='white')
            mock_bitmap.to_pil.return_value = mock_pil_image
            mock_page.render.return_value = mock_bitmap

            mock_instance = MagicMock()
            mock_instance.__len__ = Mock(return_value=5)
            mock_instance.__getitem__ = Mock(return_value=mock_page)
            mock_instance.close = Mock()
            mock_pdf.return_value = mock_instance

            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf content")

            img = pdf_page_to_image(str(pdf_file), 1)

            assert isinstance(img, str)
            # 验证是有效的 base64
            decoded = base64.b64decode(img)
            assert len(decoded) > 0


class TestBuildMarkedText:
    """测试 build_marked_text"""

    def test_build_marked_text(self):
        """测试构建带标记文本"""
        page_texts = ["第一页内容", "第二页内容", "第三页内容"]

        result = build_marked_text(page_texts)

        assert "[PAGE_1_START]" in result
        assert "[PAGE_1_END]" in result
        assert "第一页内容" in result
        assert "[PAGE_2_START]" in result
        assert "第二页内容" in result
        assert "[PAGE_3_START]" in result
        assert "第三页内容" in result

    def test_build_marked_text_empty(self):
        """测试空列表"""
        result = build_marked_text([])

        assert result == ""

    def test_build_marked_text_single_page(self):
        """测试单页"""
        result = build_marked_text(["内容"])

        assert result == "[PAGE_1_START]\n内容\n[PAGE_1_END]"


class TestDetectPdfType:
    """测试 detect_pdf_type"""

    def test_detect_native_pdf(self, tmp_path):
        """测试检测原生 PDF"""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "这是一段测试文本内容用于检测PDF类型和验证文本密度计算" * 10
        mock_page.width = 500
        mock_page.height = 700

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page, mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)

        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf

        with patch.dict('sys.modules', {'pdfplumber': mock_pdfplumber}):
            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf content")

            # 重新导入以使用 mock
            import importlib
            import audit_helper_poc.pdf_utils as pdf_utils
            importlib.reload(pdf_utils)

            result = pdf_utils.detect_pdf_type(str(pdf_file))

            assert result == "native"

    def test_detect_scanned_pdf(self, tmp_path):
        """测试检测扫描件 PDF"""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_page.width = 500
        mock_page.height = 700

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)

        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf

        with patch.dict('sys.modules', {'pdfplumber': mock_pdfplumber}):
            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf content")

            import importlib
            import audit_helper_poc.pdf_utils as pdf_utils
            importlib.reload(pdf_utils)

            result = pdf_utils.detect_pdf_type(str(pdf_file))

            assert result == "scanned"

    def test_detect_with_custom_threshold(self, tmp_path):
        """测试自定义阈值"""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "少量文本"
        mock_page.width = 500
        mock_page.height = 700

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=False)

        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf

        with patch.dict('sys.modules', {'pdfplumber': mock_pdfplumber}):
            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf content")

            import importlib
            import audit_helper_poc.pdf_utils as pdf_utils
            importlib.reload(pdf_utils)

            result_high = pdf_utils.detect_pdf_type(str(pdf_file), text_density_threshold=1.0)
            assert result_high == "scanned"

            result_low = pdf_utils.detect_pdf_type(str(pdf_file), text_density_threshold=0.000001)
            assert result_low == "native"

    def test_detect_exception_returns_scanned(self, tmp_path):
        """测试异常情况返回 scanned"""
        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.side_effect = Exception("无法打开文件")

        with patch.dict('sys.modules', {'pdfplumber': mock_pdfplumber}):
            pdf_file = tmp_path / "test.pdf"
            pdf_file.write_bytes(b"fake pdf content")

            import importlib
            import audit_helper_poc.pdf_utils as pdf_utils
            importlib.reload(pdf_utils)

            result = pdf_utils.detect_pdf_type(str(pdf_file))

            assert result == "scanned"
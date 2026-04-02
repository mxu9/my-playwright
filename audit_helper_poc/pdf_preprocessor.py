"""
PDF 预处理模块：检测 PDF 类型 + 旋转纠偏

功能：
1. 检测 PDF 类型（native/scanned）
2. 原生 PDF：检测并纠正 /Rotate 元数据，输出 /Rotate=0 的新 PDF
3. 扫描件 PDF：OCR 检测旋转角度，旋转后重新组装成 PDF
4. 输出纠偏后的 PDF 文件到指定目录
"""
import fitz  # PyMuPDF
import logging
import shutil
from pathlib import Path
from typing import Tuple, List, Dict, Optional
import numpy as np
from PIL import Image

from .pdf_utils import detect_pdf_type

logger = logging.getLogger(__name__)

# 低字符数阈值（低于此值时参考相邻页面角度）
LOW_CHAR_THRESHOLD = 200

# 测试的旋转角度
TEST_ANGLES = [0, 90, 180, 270]


class PDFPreprocessor:
    """PDF 预处理器：检测类型 + 旋转纠偏"""

    def __init__(self, output_dir: str = "output/preprocessed"):
        """
        初始化预处理器。

        Args:
            output_dir: 预处理后 PDF 输出目录
        """
        self.output_dir = Path(output_dir)
        self._ocr_instance = None

    def preprocess_pdf(self, pdf_path: str) -> str:
        """
        预处理单个 PDF 文件。

        Args:
            pdf_path: 原 PDF 文件路径

        Returns:
            预处理后的 PDF 文件路径
        """
        # 1. 检测 PDF 类型
        pdf_type = detect_pdf_type(pdf_path)
        logger.info(f"PDF 类型: {pdf_type}")

        # 2. 根据类型选择纠偏策略
        if pdf_type == "native":
            output_path = self._correct_native_pdf_rotation(pdf_path)
        else:
            output_path = self._correct_scanned_pdf_rotation(pdf_path)

        return output_path

    def preprocess_directory(self, input_dir: str) -> Dict:
        """
        预处理目录下所有 PDF 文件。

        Args:
            input_dir: 输入目录

        Returns:
            预处理报告
        """
        from .utils import scan_pdf_files

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

        pdf_files = scan_pdf_files(input_dir)
        report = {
            "input_dir": input_dir,
            "output_dir": str(self.output_dir),
            "total_files": len(pdf_files),
            "files": []
        }

        logger.info(f"开始预处理 {len(pdf_files)} 个 PDF 文件...")

        for i, pdf_path in enumerate(pdf_files):
            logger.info(f"预处理 {i + 1}/{len(pdf_files)}: {Path(pdf_path).name}")
            try:
                output_path = self.preprocess_pdf(pdf_path)
                report["files"].append({
                    "input": pdf_path,
                    "output": output_path,
                    "status": "success"
                })
            except Exception as e:
                logger.error(f"预处理失败: {pdf_path}, 错误: {e}")
                report["files"].append({
                    "input": pdf_path,
                    "output": None,
                    "status": "failed",
                    "error": str(e)
                })

        # 统计成功/失败数量
        success_count = sum(1 for f in report["files"] if f["status"] == "success")
        failed_count = sum(1 for f in report["files"] if f["status"] == "failed")
        report["success_count"] = success_count
        report["failed_count"] = failed_count

        logger.info(f"预处理完成: 成功 {success_count}, 失败 {failed_count}")

        return report

    def _correct_native_pdf_rotation(self, pdf_path: str) -> str:
        """
        原生 PDF 旋转纠正：检测 /Rotate 元数据，设置为 0。

        使用 PyMuPDF 打开 PDF，检测每页的 /Rotate 属性，
        如果不为 0，则渲染页面为图片后重新插入，使 /Rotate=0。

        Args:
            pdf_path: 原 PDF 文件路径

        Returns:
            纠正后的 PDF 文件路径
        """
        doc = fitz.open(pdf_path)
        needs_correction = False
        rotation_info = []

        # 检查是否有需要纠正的页面
        for page_index, page in enumerate(doc):
            rotation = page.rotation
            rotation_info.append(rotation)
            if rotation != 0:
                needs_correction = True
                logger.debug(f"第 {page_index + 1} 页: /Rotate = {rotation}°")

        if not needs_correction:
            # 无需纠正，直接复制到输出目录
            output_path = self._get_output_path(pdf_path)
            doc.close()
            shutil.copy2(pdf_path, output_path)
            logger.info(f"原生 PDF 无需旋转纠正，直接复制: {Path(pdf_path).name}")
            return output_path

        # 需要纠正：创建新文档
        output_path = self._get_output_path(pdf_path)
        new_doc = fitz.open()

        for page_index, page in enumerate(doc):
            rotation = rotation_info[page_index]

            if rotation != 0:
                # 渲染页面为图片（自动应用旋转）
                mat = fitz.Matrix(2, 2)  # scale=2 提高清晰度
                pix = page.get_pixmap(matrix=mat)

                # 创建新页面，插入图片
                new_page = new_doc.new_page(width=pix.width / 2, height=pix.height / 2)
                new_page.insert_image(new_page.rect, pixmap=pix)

                logger.info(f"第 {page_index + 1} 页: 纠正旋转 {rotation}°")
            else:
                # 直接复制页面（保持原样）
                new_doc.insert_pdf(doc, from_page=page_index, to_page=page_index)

        new_doc.save(output_path)
        new_doc.close()
        doc.close()

        logger.info(f"原生 PDF 旋转纠正完成: {Path(output_path).name}")
        return output_path

    def _correct_scanned_pdf_rotation(self, pdf_path: str) -> str:
        """
        扫描件 PDF 旋转纠正：OCR 检测最佳角度，重新组装成 PDF。

        Args:
            pdf_path: 原 PDF 文件路径

        Returns:
            纠正后的 PDF 文件路径
        """
        import pypdfium2

        # 1. 渲染所有页面为图片
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

        logger.info(f"渲染完成，共 {len(images)} 页")

        # 2. OCR 检测每页最佳角度
        detections = []
        for page_index, img in enumerate(images):
            best_angle, best_chars, results = self._detect_rotation_by_ocr(img)
            detections.append({
                "index": page_index,
                "image": img,
                "best_angle": best_angle,
                "best_chars": best_chars,
                "ocr_results": results
            })
            logger.debug(f"第 {page_index + 1} 页: 检测角度={best_angle}°, 字符数={best_chars}")

        # 3. 确定最终角度（低字符数页面参考相邻页面）
        final_images = []
        for i, d in enumerate(detections):
            img = d["image"]
            best_angle = d["best_angle"]
            best_chars = d["best_chars"]
            ocr_results = d["ocr_results"]

            final_angle = best_angle

            # 低字符数页面：参考相邻高字符数页面
            if best_chars < LOW_CHAR_THRESHOLD:
                neighbor_angle = self._find_neighbor_angle(detections, i)
                if neighbor_angle is not None:
                    neighbor_chars = ocr_results.get(neighbor_angle, {}).get("total_chars", 0)
                    if neighbor_chars >= best_chars * 0.9:
                        final_angle = neighbor_angle
                        logger.debug(
                            f"第 {i + 1} 页: 低字符数({best_chars})，"
                            f"参考相邻页面角度 {neighbor_angle}°"
                        )

            # 纠正旋转
            if final_angle != 0:
                img = img.rotate(final_angle, expand=True)
                logger.info(f"第 {i + 1} 页: 旋转纠正 {final_angle}°")

            final_images.append(img)

        # 4. 重新组装成 PDF
        output_path = self._get_output_path(pdf_path)
        self._images_to_pdf(final_images, output_path)

        logger.info(f"扫描件 PDF 旋转纠正完成: {Path(output_path).name}")
        return output_path

    def _detect_rotation_by_ocr(self, img: Image.Image) -> Tuple[int, int, Dict]:
        """
        通过 OCR 识别效果检测最佳旋转角度。

        Args:
            img: PIL Image

        Returns:
            (最佳角度, 识别字符数, 各角度详细结果)
        """
        ocr = self._get_ocr_instance()

        results = {}
        for angle in TEST_ANGLES:
            rotated = img.rotate(angle, expand=True)
            arr = np.array(rotated)

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

        best_angle = max(results.keys(), key=lambda a: results[a]["total_chars"])
        best_chars = results[best_angle]["total_chars"]

        return best_angle, best_chars, results

    def _find_neighbor_angle(self, detections: List[Dict], current_index: int) -> Optional[int]:
        """
        查找相邻高字符数页面的角度。

        Args:
            detections: 所有页面的检测结果
            current_index: 当前页面索引

        Returns:
            相邻页面角度，如果没有则返回 None
        """
        neighbor_angles = []
        neighbor_chars = []

        # 向前查找
        for j in range(current_index - 1, -1, -1):
            if detections[j]["best_chars"] >= LOW_CHAR_THRESHOLD:
                neighbor_angles.append(detections[j]["best_angle"])
                neighbor_chars.append(detections[j]["best_chars"])
                break

        # 向后查找
        for j in range(current_index + 1, len(detections)):
            if detections[j]["best_chars"] >= LOW_CHAR_THRESHOLD:
                neighbor_angles.append(detections[j]["best_angle"])
                neighbor_chars.append(detections[j]["best_chars"])
                break

        if not neighbor_angles:
            return None

        # 使用字符数最多的相邻页面
        max_idx = neighbor_chars.index(max(neighbor_chars))
        return neighbor_angles[max_idx]

    def _get_ocr_instance(self):
        """获取 OCR 实例（延迟初始化）"""
        if self._ocr_instance is None:
            from paddleocr import PaddleOCR
            logger.info("正在初始化 PaddleOCR（关闭自动角度纠正）...")
            self._ocr_instance = PaddleOCR(use_angle_cls=False, lang="ch", show_log=False)
        return self._ocr_instance

    def _get_output_path(self, pdf_path: str) -> str:
        """
        获取输出文件路径。

        Args:
            pdf_path: 原 PDF 文件路径

        Returns:
            输出文件路径
        """
        filename = Path(pdf_path).name
        return str(self.output_dir / filename)

    def _images_to_pdf(self, images: List[Image.Image], output_path: str) -> None:
        """
        将图片列表转换为 PDF。

        Args:
            images: PIL Image 列表
            output_path: 输出 PDF 路径
        """
        if not images:
            logger.warning("没有图片可转换为 PDF")
            return

        # 转换 RGBA 为 RGB（PDF 不支持 RGBA）
        rgb_images = []
        for img in images:
            if img.mode == 'RGBA':
                rgb_images.append(img.convert('RGB'))
            else:
                rgb_images.append(img)

        # 使用 PIL 保存为 PDF
        first_img = rgb_images[0]
        remaining_imgs = rgb_images[1:] if len(rgb_images) > 1 else []

        first_img.save(
            output_path,
            "PDF",
            save_all=True,
            append_images=remaining_imgs
        )

        logger.debug(f"PDF 保存成功: {output_path}")
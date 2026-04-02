"""
PDF 旋转检测与纠偏 POC

功能：
1. 将 PDF 每页渲染为图片（使用 pypdfium2 scale=4）
2. 通过 OCR 识别效果判断最佳旋转角度
3. 物理旋转纠正
4. 输出纠正后的图片文件和检测报告

使用：
    python pdf_rotation_corrector.py -i data/天眼查信息.pdf -o output
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np
import pypdfium2
from PIL import Image

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PDFRotationCorrector:
    """PDF 旋转检测与纠偏器"""

    # 渲染 scale（scale=4 约等于 288 DPI）
    RENDER_SCALE = 4

    # 测试的旋转角度
    TEST_ANGLES = [0, 90, 180, 270]

    # 低字符数阈值（低于此值时，参考主流角度）
    LOW_CHAR_THRESHOLD = 200

    def __init__(self):
        self._ocr = None  # 延迟初始化 PaddleOCR（关闭自动角度纠正）

    def _init_ocr(self):
        """延迟初始化 PaddleOCR（关闭 cls 自动纠正）"""
        if self._ocr is None:
            from paddleocr import PaddleOCR
            logger.info("正在初始化 PaddleOCR...")
            # 关闭 angle_cls，我们自己检测角度
            self._ocr = PaddleOCR(use_angle_cls=False, lang="ch", show_log=False)

    def pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """
        将 PDF 每页渲染为 PIL Image。

        Args:
            pdf_path: PDF 文件路径

        Returns:
            PIL Image 列表
        """
        pdf = pypdfium2.PdfDocument(pdf_path)
        images = []

        try:
            for page_index in range(len(pdf)):
                page = pdf[page_index]
                bitmap = page.render(scale=self.RENDER_SCALE)
                pil_image = bitmap.to_pil()
                images.append(pil_image)
                logger.info(f"渲染第 {page_index + 1} 页: {pil_image.size}")
        finally:
            pdf.close()

        return images

    def detect_rotation_by_ocr(self, img: Image.Image) -> Tuple[int, int, dict]:
        """
        通过 OCR 识别效果检测最佳旋转角度。

        测试四个角度的 OCR 效果，选择识别字符最多的角度。

        Args:
            img: PIL Image

        Returns:
            (最佳角度, 识别字符数, 详细结果字典)
        """
        self._init_ocr()

        results = {}

        for angle in self.TEST_ANGLES:
            rotated = img.rotate(angle, expand=True)
            img_array = np.array(rotated)

            # OCR 识别（关闭自动角度纠正）
            ocr_result = self._ocr.ocr(img_array, cls=False)

            if ocr_result and ocr_result[0]:
                total_chars = sum(len(line[1][0]) for line in ocr_result[0])
                region_count = len(ocr_result[0])
            else:
                total_chars = 0
                region_count = 0

            results[angle] = {
                "total_chars": total_chars,
                "region_count": region_count,
                "size": list(rotated.size)
            }

            logger.debug(f"  旋转 {angle}°: {region_count} 区域, {total_chars} 字符")

        # 选择识别字符最多的角度
        best_angle = max(results.keys(), key=lambda a: results[a]["total_chars"])
        best_chars = results[best_angle]["total_chars"]

        logger.info(f"最佳角度: {best_angle}° (识别 {best_chars} 字符)")

        return best_angle, best_chars, results

    def correct_rotation(self, img: Image.Image, angle: int) -> Image.Image:
        """
        纠正图片旋转。

        Args:
            img: PIL Image
            angle: 需要旋转的角度（0/90/180/270）

        Returns:
            纠正后的 PIL Image
        """
        if angle == 0:
            return img

        corrected = img.rotate(angle, expand=True)
        logger.info(f"旋转纠正: {angle}°, 尺寸: {img.size} -> {corrected.size}")
        return corrected

    def process_pdf(self, pdf_path: str, output_dir: str) -> dict:
        """
        处理 PDF 文件，检测并纠正每页旋转。

        Args:
            pdf_path: PDF 文件路径
            output_dir: 输出目录

        Returns:
            处理报告字典
        """
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        # 创建输出目录
        output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化报告
        report = {
            "input_file": pdf_path.name,
            "input_path": str(pdf_path),
            "total_pages": 0,
            "render_scale": self.RENDER_SCALE,
            "low_char_threshold": self.LOW_CHAR_THRESHOLD,
            "processed_at": datetime.now().isoformat(),
            "pages": [],
            "output_dir": str(output_dir)
        }

        logger.info(f"开始处理: {pdf_path}")

        # Step 1: 渲染 PDF 为图片
        images = self.pdf_to_images(str(pdf_path))
        report["total_pages"] = len(images)

        # Step 2: 第一轮 - 检测所有页面的角度
        page_detections = []
        for page_index, img in enumerate(images):
            page_number = page_index + 1
            logger.info(f"检测第 {page_number} 页...")
            best_angle, best_chars, ocr_results = self.detect_rotation_by_ocr(img)
            page_detections.append({
                "page_number": page_number,
                "img": img,
                "best_angle": best_angle,
                "best_chars": best_chars,
                "ocr_results": ocr_results
            })

        # Step 3: 确定最终角度并纠正（使用相邻页面参考）
        for i, detection in enumerate(page_detections):
            page_number = detection["page_number"]
            img = detection["img"]
            best_angle = detection["best_angle"]
            best_chars = detection["best_chars"]
            ocr_results = detection["ocr_results"]

            # 低字符数页面：参考相邻页面的角度
            final_angle = best_angle
            adjustment_reason = None

            if best_chars < self.LOW_CHAR_THRESHOLD:
                # 查找相邻的高字符数页面
                neighbor_angles = []
                neighbor_chars = []

                # 向前查找
                for j in range(i - 1, -1, -1):
                    if page_detections[j]["best_chars"] >= self.LOW_CHAR_THRESHOLD:
                        neighbor_angles.append(page_detections[j]["best_angle"])
                        neighbor_chars.append(page_detections[j]["best_chars"])
                        break

                # 向后查找
                for j in range(i + 1, len(page_detections)):
                    if page_detections[j]["best_chars"] >= self.LOW_CHAR_THRESHOLD:
                        neighbor_angles.append(page_detections[j]["best_angle"])
                        neighbor_chars.append(page_detections[j]["best_chars"])
                        break

                if neighbor_angles:
                    # 使用相邻页面中字符数更多的那个作为参考
                    if len(neighbor_angles) == 1:
                        neighbor_angle = neighbor_angles[0]
                    else:
                        # 取字符数更多的相邻页面
                        max_idx = neighbor_chars.index(max(neighbor_chars))
                        neighbor_angle = neighbor_angles[max_idx]

                    # 检查相邻角度的 OCR 效果是否接近最佳
                    neighbor_chars_for_this_page = ocr_results.get(neighbor_angle, {}).get("total_chars", 0)

                    # 如果相邻角度的字符数不低于最佳角度的 90%，使用相邻角度
                    if neighbor_chars_for_this_page >= best_chars * 0.9:
                        if neighbor_angle != best_angle:
                            final_angle = neighbor_angle
                            adjustment_reason = f"低字符数({best_chars})，参考相邻页面角度"

            # 纠正旋转
            corrected_img = self.correct_rotation(img, final_angle)

            # 保存图片
            output_filename = f"{pdf_path.stem}_page{page_number}_corrected.png"
            output_path = output_dir / output_filename
            corrected_img.save(output_path, "PNG")
            logger.info(f"保存: {output_path}")

            # 记录页面信息
            page_info = {
                "page_number": page_number,
                "original_size": list(img.size),
                "detected_angle": best_angle,
                "ocr_char_count": best_chars,
                "final_angle": final_angle,
                "adjusted": final_angle != best_angle,
                "adjustment_reason": adjustment_reason,
                "ocr_results_by_angle": ocr_results,
                "corrected": final_angle != 0,
                "corrected_size": list(corrected_img.size),
                "output_file": output_filename
            }
            report["pages"].append(page_info)

        # 统计摘要
        corrected_count = sum(1 for p in report["pages"] if p["corrected"])
        adjusted_count = sum(1 for p in report["pages"] if p["adjusted"])
        report["summary"] = {
            "total_pages": len(images),
            "corrected_pages": corrected_count,
            "adjusted_pages": adjusted_count,
            "uncorrected_pages": len(images) - corrected_count
        }

        # 保存报告
        report_path = output_dir / "rotation_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"报告已保存: {report_path}")

        return report


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        description="PDF 旋转检测与纠偏（通过 OCR 效果判断最佳角度）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python pdf_rotation_corrector.py -i data/天眼查信息.pdf -o output
        """
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="输入 PDF 文件路径"
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="输出目录（默认: output）"
    )

    args = parser.parse_args()

    # 处理 PDF
    corrector = PDFRotationCorrector()
    report = corrector.process_pdf(
        pdf_path=args.input,
        output_dir=args.output
    )

    # 打印摘要
    print("\n" + "=" * 60)
    print("处理完成!")
    print("=" * 60)
    print(f"输入文件: {report['input_file']}")
    print(f"总页数: {report['summary']['total_pages']}")
    print(f"纠正页数: {report['summary']['corrected_pages']}")
    if report['summary']['adjusted_pages'] > 0:
        print(f"参考主流角度调整: {report['summary']['adjusted_pages']} 页")
    print(f"输出目录: {report['output_dir']}")
    print("\n各页详情:")
    for page in report["pages"]:
        status = "已纠正" if page["corrected"] else "无需纠正"
        angle_info = f"{page['detected_angle']}°"
        if page["adjusted"]:
            angle_info = f"{page['detected_angle']}° -> {page['final_angle']}° (调整)"
        print(f"  第 {page['page_number']} 页: {angle_info}, OCR={page['ocr_char_count']} 字符 -> {status}")


if __name__ == "__main__":
    main()
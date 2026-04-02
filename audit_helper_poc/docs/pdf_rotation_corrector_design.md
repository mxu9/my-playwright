# PDF 旋转检测与纠偏 POC 设计文档

## 背景

部分 PDF 文件排版为旋转 90°/180°/270°，不利于大模型理解。需要自动检测并纠正。

## 目标

实现 POC 脚本，对 PDF 每页进行：
1. 渲染为高分辨率图片（300 DPI）
2. 检测旋转角度（0°/90°/180°/270°）
3. 物理旋转纠正
4. 输出纠正后的图片文件

## 技术方案

### 1. PDF 转图像

**方案对比：**

| 方案 | 优点 | 缺点 |
|------|------|------|
| pypdfium2（现有） | 已集成、轻量 | DPI 控制有限 |
| pdf2image | 支持 300 DPI、质量好 | 需额外依赖 poppler |

**选择：pdf2image**
- 需要高 DPI（300）保证 OCR 准确度
- Windows 需安装 poppler（或使用 conda）

### 2. 方向检测

**PaddleOCR 方向分类器：**

PaddleOCR 内置 `angle_cls` 模块，可单独调用：

```python
from paddleocr import PaddleOCR

ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)

# 方向分类（单独调用）
angle_result = ocr.cls(img_array)  # 返回 (angle, confidence)
# angle: 0, 90, 180, 270
```

**注意：** `ocr.ocr(img, cls=True)` 的结果中也包含角度，但需解析：
```python
result = ocr.ocr(img, cls=True)
# result[0][i] = [box, (text, confidence), (angle, angle_conf)]
# 第三元素是角度信息（如果 cls=True）
```

**选择：单独调用 `cls` 方法**
- 更简洁，只获取角度，不触发完整 OCR
- 性能更好

### 3. 物理旋转

使用 Pillow `Image.rotate()`：

```python
from PIL import Image

# PaddleOCR 返回的角度是"文字相对于图片的旋转"
# 纠正需要反向旋转
corrected_img = img.rotate(-angle, expand=True)
```

**角度对应：**
- 检测结果 0° → 无需旋转
- 检测结果 90° → 图片需要逆时针转 90°（即 -90°）
- 检测结果 180° → 图片需要转 -180°
- 检测结果 270° → 图片需要转 -270°（等同于顺时针 90°）

## 文件结构

```
audit_helper_poc/
├── pdf_rotation_corrector.py    # POC 主脚本（新建）
├── pdf_utils.py                 # 现有 PDF 工具
└── data/
    └── 天眼查信息.pdf            # 测试文件
```

## 输出

```
audit_helper_poc/output/
├── 天眼查信息_page1_corrected.png
├── 天眼查信息_page2_corrected.png
├── ...
└── rotation_report.json         # 检测报告
```

## 核心代码结构

```python
# pdf_rotation_corrector.py

class PDFRotationCorrector:
    def __init__(self, dpi=300):
        self.dpi = dpi
        self.ocr = None  # 延迟初始化

    def pdf_to_images(self, pdf_path) -> List[Image]:
        """使用 pdf2image 渲染 PDF 每页"""
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=self.dpi)
        return images

    def detect_rotation(self, img: Image) -> Tuple[int, float]:
        """检测图片旋转角度"""
        import numpy as np
        if self.ocr is None:
            from paddleocr import PaddleOCR
            self.ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)

        img_array = np.array(img)
        # 调用方向分类
        result = self.ocr.cls(img_array)
        angle = result[0][0]  # 0, 90, 180, 270
        confidence = result[0][1]
        return angle, confidence

    def correct_rotation(self, img: Image, angle: int) -> Image:
        """纠正图片旋转"""
        if angle == 0:
            return img
        # 反向旋转
        return img.rotate(-angle, expand=True)

    def process_pdf(self, pdf_path, output_dir) -> dict:
        """处理 PDF，返回报告"""
        # 1. 渲染图片
        # 2. 检测每页角度
        # 3. 纠正并保存
        # 4. 生成报告
        ...

def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True, help="PDF 文件路径")
    parser.add_argument("-o", "--output", default="output", help="输出目录")
    args = parser.parse_args()

    corrector = PDFRotationCorrector()
    report = corrector.process_pdf(args.input, args.output)
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

## 依赖变更

需要添加到 requirements.txt：

```txt
pdf2image>=1.16.0
```

**Windows poppler 安装：**
- 方案 A：下载 poppler-windows.zip，解压后设置环境变量
- 方案 B：使用 conda `conda install -c conda-forge poppler`
- 方案 C：检测失败时 fallback 到 pypdfium2

## 测试计划

```bash
# 运行 POC
python audit_helper_poc/pdf_rotation_corrector.py \
    -i audit_helper_poc/data/天眼查信息.pdf \
    -o audit_helper_poc/output

# 查看输出
ls audit_helper_poc/output/
# 天眼查信息_page1_corrected.png
# 天眼查信息_page2_corrected.png
# rotation_report.json
```

## 报告格式（rotation_report.json）

```json
{
  "input_file": "天眼查信息.pdf",
  "total_pages": 3,
  "dpi": 300,
  "pages": [
    {
      "page_number": 1,
      "detected_angle": 0,
      "confidence": 0.95,
      "corrected": false,
      "output_file": "天眼查信息_page1_corrected.png"
    },
    {
      "page_number": 2,
      "detected_angle": 90,
      "confidence": 0.92,
      "corrected": true,
      "output_file": "天眼查信息_page2_corrected.png"
    }
  ],
  "output_dir": "audit_helper_poc/output"
}
```

## 待确认事项

1. **pdf2image vs pypdfium2**：是否接受额外依赖 pdf2image + poppler？
   - 若不接受，可用 pypdfium2 的 `scale` 参数模拟高 DPI（scale=4 约等于 300 DPI）

2. **阈值设置**：角度置信度低于多少时跳过纠正？（建议 0.7）

3. **输出格式**：PNG 还是 JPEG？PNG 无损但文件大，JPEG 有损但小。

---

**请审核以上设计，确认后我将实现。**
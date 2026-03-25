# -*- coding: utf-8 -*-
"""
检测图片中的文字位置
使用 AntiCAP 的 Detection_Text 功能
"""

import base64
import json
import os
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

# 导入 AntiCAP
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "AntiCAP"))

import AntiCAP


def image_to_base64(image_path: str) -> str:
    """将图片文件转为 base64 字符串"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def detect_text_positions(image_path: str, y1: int = 0, y2: int = None):
    """
    检测图片中指定Y轴范围内的文字位置
    返回每个文字的边界框坐标 [x1, y1, x2, y2]（原图坐标系）
    """
    # 打开图片并裁剪到指定区域
    img = Image.open(image_path)
    img_width, img_height = img.size

    # 确定裁剪区域
    if y2 is None:
        y2 = img_height

    # 裁剪图片 (left, upper, right, lower)
    cropped_img = img.crop((0, y1, img_width, y2))

    # 将裁剪后的图片转为 base64
    import io
    buffer = io.BytesIO()
    cropped_img.save(buffer, format=img.format or 'PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # 初始化 AntiCAP Handler
    print("正在初始化 AntiCAP...")
    atc = AntiCAP.Handler(show_banner=True)

    # 检测文字位置
    print(f"正在检测图片中的文字位置 (Y轴范围: {y1}-{y2})...")
    results = atc.Detection_Text(img_base64=img_base64)

    # 将坐标从裁剪区域转换回原图坐标系
    for item in results:
        box = item["box"]  # [x1, y1, x2, y2]
        # Y坐标加上裁剪的偏移量
        box[1] = box[1] + y1
        box[3] = box[3] + y1

    return results


def print_results(results):
    """打印检测结果"""
    print("\n" + "=" * 50)
    print("检测结果:")
    print("=" * 50)

    if not results:
        print("未检测到任何文字")
        return

    for i, item in enumerate(results, 1):
        box = item["box"]
        class_name = item.get("class", "Text")
        print(f"\n文字 {i}:")
        print(f"  类别: {class_name}")
        print(f"  边界框: [{box[0]:.2f}, {box[1]:.2f}, {box[2]:.2f}, {box[3]:.2f}]")
        print(f"  中心点: ({(box[0] + box[2]) / 2:.2f}, {(box[1] + box[3]) / 2:.2f})")


def annotate_image(image_path: str, results: list, output_path: str):
    """
    在图片上标注检测到的文字位置
    用红色矩形框出文字位置，线条宽度2像素
    并标注序号（对应JSON中的索引）
    """
    # 打开原始图片
    img = Image.open(image_path)

    # 复制一份新图片
    img_copy = img.copy()

    # 创建绘图对象
    draw = ImageDraw.Draw(img_copy)

    # 在每个文字位置画红色矩形框并标注序号
    for i, item in enumerate(results, 1):
        box = item["box"]  # [x1, y1, x2, y2]
        # 画红色矩形框，线条宽度2像素
        draw.rectangle(box, outline="red", width=2)
        # 在框的左上角绘制序号
        draw.text((box[0], box[1] - 15), str(i), fill="red")

    # 保存标注后的图片
    img_copy.save(output_path)
    print(f"标注图片已保存到: {output_path}")


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="检测图片中的文字位置")
    parser.add_argument(
        "-i", "--image",
        type=str,
        help="要检测的图片文件名（位于脚本同级目录下）"
    )
    parser.add_argument(
        "-y1", "--y1",
        type=int,
        default=48,
        help="检测区域起始Y坐标（默认48）"
    )
    parser.add_argument(
        "-y2", "--y2",
        type=int,
        default=230,
        help="检测区域结束Y坐标（默认230）"
    )
    args = parser.parse_args()

    # 确定图片路径
    script_dir = Path(__file__).parent
    if args.image:
        image_path = script_dir / args.image
    else:
        image_path = script_dir.parent / "data" / "zhutu.png"

    if not image_path.exists():
        print(f"错误: 图片不存在 - {image_path}")
        return

    print(f"图片路径: {image_path}")

    # 检测指定Y轴范围内的文字位置
    results = detect_text_positions(str(image_path), args.y1, args.y2)

    # 打印结果
    print_results(results)

    # 保存结果为 JSON（文件名与输入图片相关）
    stem = image_path.stem  # 文件名（不含扩展名）
    json_path = script_dir / f"{stem}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {json_path}")

    # 在图片上标注文字位置
    if results:
        # 生成输出文件名：input_filename.png -> input_filename_annotated.png
        stem = image_path.stem  # 文件名（不含扩展名）
        annotated_path = script_dir / f"{stem}_annotated.png"
        annotate_image(str(image_path), results, str(annotated_path))


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
验证码识别完整流程脚本
整合文字检测 + 大模型识别功能

输入: 图片路径 (如 data/1.png)
输出: 标注了点击顺序的结果图片 (*_clicked.png)
"""

import warnings
warnings.filterwarnings("ignore", message="urllib3.*doesn't match a supported version")

import base64
import json
import os
import re
import sys
import time
import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

# 导入 AntiCAP
sys.path.insert(0, str(Path(__file__).parent.parent / "AntiCAP"))
import AntiCAP

load_dotenv()


# ============== Step 1: 文字检测 (来自 detect_text.py) ==============

def is_white_pixel(r: int, g: int, b: int, threshold: int = 240) -> bool:
    """判断像素是否为白色（接近白色）"""
    return r >= threshold and g >= threshold and b >= threshold


def is_orange_pixel(r: int, g: int, b: int) -> bool:
    """判断像素是否为橘色"""
    return r > 200 and 100 < g < 200 and b < 150


def analyze_row_color(img_array: np.ndarray, y: int) -> tuple:
    """分析某一行的主色调"""
    row = img_array[y, :, :3]
    white_count = 0
    orange_count = 0

    for pixel in row:
        r, g, b = pixel
        if is_white_pixel(r, g, b):
            white_count += 1
        elif is_orange_pixel(r, g, b):
            orange_count += 1

    total = len(row)
    is_white_dominated = white_count > total * 0.7
    is_orange_dominated = orange_count > total * 0.3

    avg_color = np.mean(row, axis=0)
    return is_white_dominated, is_orange_dominated, avg_color


def detect_main_block(image_path: str, white_threshold: int = 240) -> tuple:
    """
    检测图片中主要大块的区域（排除白色背景和橘色区域）
    返回 (x1, y1, x2, y2) 边界框坐标
    """
    img = Image.open(image_path)
    img_array = np.array(img)

    # 转换为 RGB
    if len(img_array.shape) == 2:
        img_array = np.stack([img_array] * 3, axis=-1)
    elif img_array.shape[2] == 4:
        img_array = img_array[:, :, :3]

    height, width = img_array.shape[:2]

    # 分析每行的颜色特征
    row_types = []
    for y in range(height):
        is_white, is_orange, _ = analyze_row_color(img_array, y)
        if is_white:
            row_types.append('white')
        elif is_orange:
            row_types.append('orange')
        else:
            row_types.append('block')

    # 找到连续的 'block' 区域
    y1, y2 = None, None
    in_block = False
    block_start = 0

    for y, row_type in enumerate(row_types):
        if row_type == 'block' and not in_block:
            in_block = True
            block_start = y
        elif row_type != 'block' and in_block:
            in_block = False
            if y1 is None or (y - block_start) > (y2 - y1):
                y1 = block_start
                y2 = y

    if in_block and (y1 is None or (height - block_start) > (y2 - y1)):
        y1 = block_start
        y2 = height

    if y1 is None:
        print(f"警告: 未检测到明显的大块区域，使用全图")
        return (0, 0, width, height)

    # X 方向边界
    x1, x2 = 0, width
    block_region = img_array[y1:y2, :, :3]

    for x in range(width):
        col = block_region[:, x, :]
        white_count = sum(1 for pixel in col if is_white_pixel(*pixel))
        if white_count < len(col) * 0.8:
            x1 = x
            break

    for x in range(width - 1, -1, -1):
        col = block_region[:, x, :]
        white_count = sum(1 for pixel in col if is_white_pixel(*pixel))
        if white_count < len(col) * 0.8:
            x2 = x + 1
            break

    print(f"[检测到大块区域]: ({x1}, {y1}, {x2}, {y2})")
    return (x1, y1, x2, y2)


def detect_text_positions(image_path: str):
    """
    检测图片中文字位置
    返回每个文字的边界框坐标列表
    """
    img = Image.open(image_path)
    img_width, img_height = img.size

    # 自动检测大块区域
    block_box = detect_main_block(image_path)
    y1, y2 = block_box[1], block_box[3]

    # 裁剪图片
    cropped_img = img.crop((0, y1, img_width, y2))

    # 转为 base64
    import io
    buffer = io.BytesIO()
    cropped_img.save(buffer, format=img.format or 'PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # 初始化 AntiCAP
    print("[正在初始化 AntiCAP...]")
    atc = AntiCAP.Handler(show_banner=False)

    # 检测文字位置
    print(f"[正在检测文字位置] (Y轴范围: {y1}-{y2})...")
    results = atc.Detection_Text(img_base64=img_base64)

    # 坐标转换回原图
    for item in results:
        box = item["box"]
        box[1] = box[1] + y1
        box[3] = box[3] + y1

    return results, block_box


# ============== Step 2: 预处理图片 (来自 new_click_txt.py) ==============

def preprocess_image_with_boxes(image_path, boxes_list, output_image_path, output_json_path):
    """
    预处理图片和 boxes：
    1. 取原图 y 轴 0-48 像素区域（提示栏）
    2. 提取所有 box 区域，排成一排，间隔40像素
    3. 在每个 box 左上角外侧绘制序号
    4. 重新计算 boxes 坐标
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"无法读取图片: {image_path}")

    # 取提示栏区域
    prompt_bar = img[0:48, :]

    # 提取所有 box 区域
    box_images = []
    max_height = 0
    max_width = 0

    for box in boxes_list:
        x1, y1, x2, y2 = [int(v) for v in box['box']]
        # 往外扩展 2 个像素
        x1 = max(0, x1 - 2)
        y1 = max(0, y1 - 2)
        x2 = min(img.shape[1], x2 + 2)
        y2 = min(img.shape[0], y2 + 2)

        box_img = img[y1:y2, x1:x2]
        box_images.append(box_img)

        h, w = box_img.shape[:2]
        if h > max_height:
            max_height = h
        if w > max_width:
            max_width = w

    # 排成 1 排
    gap = 40  # 水平间隔 40 像素
    row_gap = 40  # 与提示栏间隔 40 像素
    left_padding = 10  # 左边留 10 像素
    top_padding = 20   # 上边留 20 像素（给序号留空间）
    bottom_padding = 20  # 下边留 20 像素

    total_count = len(box_images)

    # 计算总宽度
    total_width = left_padding
    for i, box_img in enumerate(box_images):
        total_width += box_img.shape[1]
        if i < total_count - 1:
            total_width += gap
    total_width += left_padding  # 右边也留 padding

    # 创建白色画布
    canvas_height = max_height + top_padding + bottom_padding
    canvas = np.ones((canvas_height, total_width, 3), dtype=np.uint8) * 255

    new_boxes = []

    # 放置 box
    current_x = left_padding
    current_y = top_padding
    for i in range(total_count):
        box_img = box_images[i]
        h, w = box_img.shape[:2]
        canvas[current_y:current_y + h, current_x:current_x + w] = box_img

        # 在左上角外侧绘制序号（红色），在 box 上方
        cv2.putText(canvas, str(i), (current_x + 2, current_y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)

        new_box = {
            'class': boxes_list[i].get('class', 'Text'),
            'index': i,
            'box': [current_x, 48 + row_gap + current_y, current_x + w, 48 + row_gap + current_y + h]
        }
        new_boxes.append(new_box)

        current_x += w + gap

    # 对齐宽度
    prompt_width = prompt_bar.shape[1]
    concat_width = canvas.shape[1]

    if prompt_width > concat_width:
        padding = np.ones((canvas_height, prompt_width - concat_width, 3), dtype=np.uint8) * 255
        canvas = np.hstack([canvas, padding])
    elif concat_width > prompt_width:
        padding = np.ones((48, concat_width - prompt_width, 3), dtype=np.uint8) * 255
        prompt_bar = np.hstack([prompt_bar, padding])

    # 提示栏和 box 区域之间加 row_gap 间隔
    gap_bar = np.ones((row_gap, canvas.shape[1], 3), dtype=np.uint8) * 255
    result = np.vstack([prompt_bar, gap_bar, canvas])

    # 保存
    cv2.imwrite(output_image_path, result)
    print(f"[预处理图片已保存]: {output_image_path}")

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(new_boxes, f, ensure_ascii=False, indent=2)
    print(f"[预处理 JSON 已保存]: {output_json_path}")

    return output_image_path, output_json_path


# ============== Step 3: 大模型调用 ==============

def encode_image(image_path):
    """将图片转换为 Base64 编码"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def parse_click_sequence(response_content):
    """从模型响应中解析 click_sequence"""
    try:
        result = json.loads(response_content)
        if "click_sequence" in result:
            return result["click_sequence"]
    except json.JSONDecodeError:
        pass

    try:
        json_match = re.search(r'```json\s*(.*?)\s*```', response_content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(1))
            if "click_sequence" in result:
                return result["click_sequence"]

        json_match = re.search(r'\{[^{}]*"click_sequence"[^{}]*\}', response_content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            if "click_sequence" in result:
                return result["click_sequence"]
    except (json.JSONDecodeError, AttributeError):
        pass

    return None


def call_llm_for_captcha(image_path, boxes_data):
    """调用大模型识别验证码"""
    llm = ChatOpenAI(
        model=os.getenv("MODEL_NAME"),
        api_key=os.getenv("API_KEY"),
        base_url=os.getenv("BASE_URL"),
        temperature=0.5,
    )

    base64_image = encode_image(image_path)


    system_prompt_template = """### 角色定位
你是一个高精度的验证码识别与逻辑推理助手。

### 图片布局说明
1. **指令区（顶部）**：包含“请依次点击：XXX”字样的任务指令。
2. **候选区（主体）**：分布着若干个汉字，且每个汉字左上角均已人工标注了红色的数字序号（0, 1, 2, 3...）。

### 任务步骤（请按此逻辑执行）
1. **指令解析 (Target Extraction)**：识别图片顶部指令要求“依次点击”的汉字序列，记为 `Target_Chars`。
2. **定点识别 (Visual Scanning)**：按照数字序号从 0 到 5 的顺序，观察每一个 `boxes` 坐标区域：
   - 识别该区域内的单个汉字。
   - 确保识别结果 `details[i].text` 对应图片中标记为数字 `i` 的位置。
3. **逻辑映射 (Index Mapping)**：
   - 遍历 `Target_Chars` 中的每一个汉字。
   - 在识别结果 `details` 中查找该字对应的 `index`。
   - 按 `Target_Chars` 的先后顺序排列这些 `index`，生成 `click_sequence`。

### 强制输出约束
- **严禁重排**：`details` 数组必须严格按 `index` 从 0 到 5 的升序排列，禁止根据汉字在图中的物理位置或点击顺序重排。
- **元素对齐**：`details[n]` 必须对应输入数组中的 `boxes[n]`。
- **坐标回显**：在 `details` 的每个对象中回传原始 `box` 坐标，以确保注意力锚定。

### 返回 JSON 格式
{
  "target_characters": "顶部识别出的目标字符（如：龙凤）",
  "click_sequence": [按点击顺序排列的索引数字],
  "details": [
    {"index": 0, "text": "序号0位置的字", "box": [2, 48, 50, 96]},
    {"index": 1, "text": "序号1位置的字", "box": [52, 48, 100, 96]},
    {"index": 2, "text": "序号2位置的字", "box": [102, 48, 149, 96]},
    {"index": 3, "text": "序号3位置的字", "box": [151, 48, 194, 96]},
    {"index": 4, "text": "序号4位置的字", "box": [196, 48, 243, 96]},
    {"index": 5, "text": "序号5位置的字", "box": [245, 48, 294, 96]}
  ]
}

### 待检测位置 JSON (输入数组):
{boxes}
"""

    system_prompt = system_prompt_template.replace("{boxes}", boxes_data)

    message = HumanMessage(
        content=[
            {"type": "text", "text": system_prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
            },
        ]
    )

    print("[正在调用大模型识别...]")
    start_time = time.time()
    response = llm.invoke([message])
    elapsed_time = time.time() - start_time

    print(f"\n[识别结果]:")
    print(response.content)
    print(f"\n[执行时间]: {elapsed_time:.2f} 秒")

    return response.content


# ============== Step 4: 绘制结果 ==============

def draw_sequence_on_image(image_path, boxes_data, click_sequence, output_path):
    """在图片上按照 click_sequence 顺序绘制序号"""
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    boxes = json.loads(boxes_data)

    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        except:
            font = ImageFont.load_default()

    for idx, box_index in enumerate(click_sequence):
        if box_index < len(boxes):
            box = boxes[box_index]
            x1, y1, x2, y2 = box["box"]
            text = str(idx)
            draw.text((x1, y1), text, fill="red", font=font)

    img.save(output_path)
    print(f"[结果图片已保存]: {output_path}")


# ============== 主函数 ==============

def solve_captcha(image_path: str, output_dir: str = None):
    """
    完整的验证码识别流程

    Args:
        image_path: 输入图片路径
        output_dir: 输出目录（默认与输入图片同目录）
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"图片不存在: {image_path}")

    # 设置输出目录
    if output_dir is None:
        output_dir = image_path.parent
    else:
        output_dir = Path(output_dir)

    # 创建 temp 目录
    script_dir = Path(__file__).parent
    temp_dir = script_dir / "temp"
    temp_dir.mkdir(exist_ok=True)

    print("=" * 50)
    print(f"[输入图片]: {image_path}")
    print("=" * 50)

    # Step 1: 检测文字位置
    print("\n>>> Step 1: 检测文字位置")
    results, block_box = detect_text_positions(str(image_path))

    if not results:
        print("错误: 未检测到任何文字")
        return

    print(f"[检测到 {len(results)} 个文字]")

    # 保存检测结果
    detected_json_path = temp_dir / f"{image_path.stem}_detected.json"
    img = Image.open(str(image_path))
    img_width, img_height = img.size

    detected_data = {
        "top_region": {
            "x1": 0, "y1": 0,
            "x2": img_width, "y2": block_box[1]
        },
        "block_region": {
            "x1": block_box[0], "y1": block_box[1],
            "x2": block_box[2], "y2": block_box[3]
        },
        "texts": []
    }

    for i, item in enumerate(results):
        box = item["box"]
        detected_data["texts"].append({
            "index": i,
            "box": [round(box[0], 2), round(box[1], 2), round(box[2], 2), round(box[3], 2)]
        })

    with open(detected_json_path, 'w', encoding='utf-8') as f:
        json.dump(detected_data, f, ensure_ascii=False, indent=2)
    print(f"[检测结果已保存]: {detected_json_path}")

    # Step 2: 格式转换
    print("\n>>> Step 2: 格式转换")
    boxes_list = []
    for item in results:
        boxes_list.append({
            "class": item.get("class", "Text"),
            "index": item.get("index", 0),
            "box": item["box"]
        })

    # Step 3: 预处理图片
    print("\n>>> Step 3: 预处理图片")
    preprocessed_image_path = temp_dir / f"{image_path.stem}_preprocessed.png"
    preprocessed_json_path = temp_dir / f"{image_path.stem}_preprocessed.json"

    preprocess_image_with_boxes(
        str(image_path),
        boxes_list,
        str(preprocessed_image_path),
        str(preprocessed_json_path)
    )

    # Step 4: 调用大模型
    print("\n>>> Step 4: 调用大模型识别")
    with open(preprocessed_json_path, 'r', encoding='utf-8') as f:
        boxes_data = f.read()

    response_content = call_llm_for_captcha(str(preprocessed_image_path), boxes_data)

    # Step 5: 解析并绘制结果
    print("\n>>> Step 5: 绘制结果图片")
    click_sequence = parse_click_sequence(response_content)

    if click_sequence:
        print(f"[点击顺序]: {click_sequence}")

        output_path = output_dir / f"{image_path.stem}_clicked.png"
        draw_sequence_on_image(str(preprocessed_image_path), boxes_data, click_sequence, str(output_path))

        print("\n" + "=" * 50)
        print(f"[完成] 输出图片: {output_path}")
        print("=" * 50)
    else:
        print("\n[警告]: 未能从响应中解析 click_sequence")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="验证码识别完整流程")
    parser.add_argument("--image", "-i", required=True, help="输入图片路径")
    parser.add_argument("--output", "-o", help="输出目录（默认与输入图片同目录）")

    args = parser.parse_args()
    solve_captcha(args.image, args.output)
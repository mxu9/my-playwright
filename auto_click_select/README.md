# 验证码识别模块

基于文字检测 + 大模型的验证码识别方案，专门处理汉字点选验证码。

## 功能特性

- 自动检测验证码图片中的文字位置
- 图片预处理，提取文字区域并标注序号
- 调用大模型识别点击顺序
- 支持批量处理

## 目录结构

```
auto_click_select/
├── main.py           # 主程序入口
├── data/             # 测试数据目录
├── runs/             # 运行结果输出
├── temp/             # 临时文件（预处理图片等）
├── .env              # 环境变量配置
└── .env.example      # 环境变量示例
```

## 安装依赖

```bash
pip install opencv-python numpy pillow python-dotenv langchain-openai
```

确保已安装 AntiCAP 子模块：

```bash
git submodule update --init --recursive
```

## 配置

复制 `.env.example` 为 `.env`，填写以下配置：

```
MODEL_NAME=your_model_name
API_KEY=your_api_key
BASE_URL=your_api_base_url
```

## 使用方法

### 单张图片识别

```bash
python main.py -i data/1.png
```

### 指定输出目录

```bash
python main.py -i data/1.png -o output/
```

## 输出说明

- `temp/{文件名}_detected.json` - 文字检测结果
- `temp/{文件名}_preprocessed.png` - 预处理后的图片
- `temp/{文件名}_preprocessed.json` - 预处理后的坐标信息
- `{输出目录}/{文件名}_clicked.png` - 标注点击顺序的结果图片

## 处理流程

1. **文字检测**：使用 AntiCAP 检测验证码图片中的文字位置
2. **图片预处理**：提取文字区域，排成一排，标注序号
3. **大模型识别**：识别提示栏目标文字，匹配点击顺序
4. **结果绘制**：在图片上标注正确的点击顺序

## 依赖

- [AntiCAP](../AntiCAP/) - 验证码识别库（Git 子模块）
- OpenCV - 图像处理
- LangChain OpenAI - 大模型调用
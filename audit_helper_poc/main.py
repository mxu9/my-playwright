#!/usr/bin/env python
"""
audit_helper_poc 主入口

用法:
    python -m audit_helper_poc.main <input_dir> [options]
    或
    cd audit_helper_poc && python main.py <input_dir> [options]

示例:
    python -m audit_helper_poc.main data/
    python -m audit_helper_poc.main data/ -o output/result.json
    python -m audit_helper_poc.main data/ -l DEBUG
"""

import argparse
import os
import sys
from pathlib import Path

# 支持两种运行方式：
# 1. python -m audit_helper_poc.main (推荐)
# 2. cd audit_helper_poc && python main.py
if __name__ == "__main__" and __package__ is None:
    # 直接运行 main.py 时，添加父目录到路径
    sys.path.insert(0, str(Path(__file__).parent))

from audit_helper_poc.planner import Planner


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="PDF 处理框架 - 分类并提取 PDF 文件信息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python main.py data/                        # 处理 data 目录下的 PDF
    python main.py data/ -o result.json         # 指定输出文件
    python main.py data/ -l DEBUG               # 开启调试日志
    python main.py data/ -c /path/to/.env       # 指定配置文件
        """
    )

    parser.add_argument(
        "input_dir",
        help="PDF 文件所在目录"
    )

    parser.add_argument(
        "-o", "--output",
        default="process_result.json",
        help="输出结果文件名 (默认: process_result.json)"
    )

    parser.add_argument(
        "-c", "--config",
        default=".env",
        help="配置文件路径 (默认: .env)"
    )

    parser.add_argument(
        "-l", "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别 (默认: INFO)"
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 获取模块目录
    module_dir = Path(__file__).parent

    # 检查输入目录
    input_dir = args.input_dir
    if not os.path.isabs(input_dir):
        input_dir = str(module_dir / input_dir)

    if not os.path.isdir(input_dir):
        print(f"错误: 目录不存在: {input_dir}")
        sys.exit(1)

    # 检查配置文件
    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = str(module_dir / config_path)

    if not os.path.isfile(config_path):
        print(f"错误: 配置文件不存在: {config_path}")
        print("请创建 .env 文件，参考 .env.example")
        sys.exit(1)

    # 输出文件路径
    output_file = args.output
    if not os.path.isabs(output_file):
        output_file = str(module_dir / output_file)

    print("=" * 60)
    print("audit_helper_poc - PDF 处理框架")
    print("=" * 60)
    print(f"输入目录: {input_dir}")
    print(f"配置文件: {config_path}")
    print(f"输出文件: {output_file}")
    print(f"日志级别: {args.log_level}")
    print("=" * 60)

    try:
        # 初始化 Planner
        print("\n正在初始化...")
        planner = Planner(config_path=config_path, log_level=args.log_level)

        # 执行处理
        print("\n开始处理 PDF 文件...")
        result = planner.process(input_dir=input_dir, output_file=output_file)

        # 输出汇总
        print("\n" + "=" * 60)
        print("处理完成")
        print("=" * 60)
        print(f"总文件数: {result.get('total_files', 0)}")

        # 状态统计
        files = result.get("files", [])
        completed = sum(1 for f in files if f.get("status") == "completed")
        errors = sum(1 for f in files if f.get("status") == "error")
        print(f"成功: {completed}")
        print(f"失败: {errors}")

        # 分类分布
        summary = result.get("summary", {})
        category_dist = summary.get("category_distribution", {})
        if category_dist:
            print("\n分类分布:")
            for cat, count in category_dist.items():
                print(f"  - {cat}: {count}")

        # Token 使用
        token_usage = summary.get("total_token_usage", {})
        if token_usage:
            print(f"\nToken 使用:")
            print(f"  - 总输入: {token_usage.get('total_prompt_tokens', 0):,}")
            print(f"  - 总输出: {token_usage.get('total_completion_tokens', 0):,}")
            print(f"  - 总计: {token_usage.get('total_tokens', 0):,}")

        print(f"\n结果已保存到: {output_file}")

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
'''
按比例拆分文件内容的，适合用来拆分数据集txt文件（目前第一次尝试命令行的方式运行，有点小问题）
'''
import os
import random
import argparse
from typing import Tuple


def validate_file_path(file_path: str, is_input: bool = True) -> bool:
    """
    验证文件路径有效性

    参数:
        file_path: 待验证的文件路径
        is_input: True=验证输入文件（需存在），False=验证输出文件（需确认覆盖）
    返回:
        验证通过返回True，失败返回False
    """
    if is_input:
        if not os.path.exists(file_path):
            print(f"❌ 错误：输入文件不存在 → {file_path}")
            return False
        if not os.path.isfile(file_path):
            print(f"❌ 错误：路径不是有效文件 → {file_path}")
            return False
    else:
        if os.path.exists(file_path):
            while True:
                choice = input(f"⚠️  输出文件已存在 → {file_path}\n是否覆盖？(y=是/n=否)：").strip().lower()
                if choice in ["y", "n"]:
                    return choice == "y"
                print("请输入 'y' 或 'n'！")
    return True


def read_file_content(file_path: str) -> Tuple[list, int]:
    """读取文件内容并返回内容列表和总行数"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.readlines()
        total_lines = len(content)
        non_empty_lines = len([line for line in content if line.strip()])

        print(f"✅ 成功读取文件：{file_path}")
        print(f"   - 总行数：{total_lines}（含空行）")
        print(f"   - 非空行：{non_empty_lines}（实际数据行）")

        if total_lines == 0:
            print("❌ 错误：文件为空，无内容可划分！")
            return [], 0
        return content, total_lines
    except Exception as e:
        print(f"❌ 读取文件失败：{str(e)}")
        return [], 0


def split_content(all_content: list, split_ratio: float, seed: int = None) -> Tuple[list, list]:
    """
    按比例随机拆分内容

    参数:
        all_content: 待拆分的完整内容列表
        split_ratio: 拆分到新文件的比例（0 < ratio < 1）
        seed: 随机种子（None=每次随机，int=固定种子可复现）
    返回:
        (原文件保留内容, 新文件内容)
    """
    if not (0 < split_ratio < 1):
        print(f"❌ 错误：拆分比例需在0-1之间（当前输入：{split_ratio}）")
        return [], []

    if seed is not None:
        random.seed(seed)
        print(f"🔧 使用固定随机种子：{seed}（拆分结果可复现）")
    else:
        print(f"🔧 未使用固定种子（每次拆分结果随机）")

    total = len(all_content)
    # 计算新文件应包含的行数（至少1行）
    new_file_count = max(1, round(total * split_ratio))
    if new_file_count >= total:
        print(f"⚠️  拆分比例过大，新文件行数调整为：{total - 1}（保留1行在原文件）")
        new_file_count = total - 1

    # 随机选择新文件内容
    new_file_content = random.sample(all_content, new_file_count)
    # 筛选原文件保留内容
    new_file_set = set(new_file_content)
    original_remaining = [line for line in all_content if line not in new_file_set]

    return original_remaining, new_file_content


def write_file_content(file_path: str, content: list) -> bool:
    """写入内容到文件，自动创建目录"""
    try:
        # 确保输出目录存在
        output_dir = os.path.dirname(file_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            print(f"📂 自动创建输出目录：{output_dir}")

        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(content)
        print(f"✅ 成功写入文件：{file_path}")
        print(f"   - 写入行数：{len(content)}")
        return True
    except Exception as e:
        print(f"❌ 写入文件失败：{str(e)}")
        return False


def split_file_cli():
    """命令行交互入口"""
    parser = argparse.ArgumentParser(description="通用文件内容拆分工具（按比例随机拆分）")
    parser.add_argument("--source", type=str, help="源文件路径（要拆分的文件）")
    parser.add_argument("--dest", type=str, help="目标文件路径（拆分出的新文件）")
    parser.add_argument("--ratio", type=float, default=0.2, help="拆分到目标文件的比例（默认0.2，即20%）")
    parser.add_argument("--seed", type=int, default=1234, help="随机种子（可选，用于复现拆分结果，默认1234）")
    args = parser.parse_args()

    # 补充缺失的参数
    while not args.source:
        args.source = input("请输入源文件路径（要拆分的文件）：").strip()
        if not args.source:
            print("路径不能为空，请重新输入！")

    if not args.dest:
        source_dir = os.path.dirname(args.source)
        source_name = os.path.splitext(os.path.basename(args.source))[0]
        default_dest = os.path.join(source_dir, f"{source_name}_split.txt")
        args.dest = input(f"请输入目标文件路径（拆分出的新文件，默认：{default_dest}）：").strip() or default_dest

    # 验证比例（限制在0.05-0.5之间）
    while not (0.05 <= args.ratio <= 0.5):
        ratio_input = input("请输入拆分比例（建议0.05-0.5，默认0.2）：").strip()
        if not ratio_input:
            args.ratio = 0.2
            break
        try:
            args.ratio = float(ratio_input)
        except:
            print("请输入合法数字（如0.2）！")

    # 显示配置信息
    print("\n" + "=" * 50)
    print("📋 拆分配置确认")
    print(f"   源文件路径：{args.source}")
    print(f"   目标文件路径：{args.dest}")
    print(f"   拆分比例：{args.ratio:.1%}（目标文件占比）")
    print(f"   随机种子：{args.seed if args.seed else '无'}")
    print("=" * 50 + "\n")

    # 执行拆分流程
    if not validate_file_path(args.source, is_input=True):
        return
    if not validate_file_path(args.dest, is_input=False):
        print("🚫 取消覆盖，程序退出")
        return

    all_content, total_lines = read_file_content(args.source)
    if total_lines == 0:
        return

    original_remaining, new_file_content = split_content(all_content, args.ratio, args.seed)
    if not original_remaining or not new_file_content:
        return

    print("\n📝 开始写入文件...")
    write_success1 = write_file_content(args.source, original_remaining)  # 更新源文件
    write_success2 = write_file_content(args.dest, new_file_content)  # 生成目标文件

    # 输出结果
    print("\n" + "=" * 50)
    if write_success1 and write_success2:
        print("🎉 拆分完成！最终结果：")
        print(
            f"   - 原始文件：{total_lines} 条 → 更新后：{len(original_remaining)} 条（{len(original_remaining) / total_lines:.1%}）")
        print(f"   - 目标文件：{len(new_file_content)} 条（{len(new_file_content) / total_lines:.1%}）")
        print(f"   - 目标文件位置：{args.dest}")
    else:
        print("❌ 拆分失败：部分文件写入出错，请检查路径权限！")
    print("=" * 50)


if __name__ == "__main__":
    split_file_cli()

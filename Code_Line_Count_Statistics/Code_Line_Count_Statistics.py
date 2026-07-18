'''
代码行数统计器（支持Excel输出+优化饼图）
'''

import os
import sys
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd
from typing import Dict, Tuple, List
from tkinter import Tk, filedialog, messagebox

# ---------------------- 高DPI适配配置（解决窗口模糊）----------------------
def setup_high_dpi(root):
    """在已创建的Tk实例上配置高DPI，避免窗口冲突"""
    if sys.platform == "win32":
        try:
            import ctypes
            # Windows 高DPI感知设置
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            dpi = ctypes.windll.user32.GetDpiForWindow(root.winfo_id())
            scaling_factor = dpi / 96  # 标准DPI=96
            root.tk.call('tk', 'scaling', scaling_factor)
        except Exception:
            root.tk.call('tk', 'scaling', 1.0)
    elif sys.platform == "darwin":
        # macOS 视网膜屏优化
        root.tk.call('tk', 'scaling', 2.0)
    else:
        # Linux 自动适配
        try:
            scaling_factor = root.winfo_fpixels('1i') / 96
            root.tk.call('tk', 'scaling', scaling_factor)
        except Exception:
            root.tk.call('tk', 'scaling', 1.0)

# ---------------------- 文件夹选择功能 ----------------------
def select_target_folder() -> Tuple[str, Tk]:
    """交互式选择要分析的文件夹（高DPI适配，仅支持文件夹选择）"""
    root = Tk()
    root.withdraw()  # 隐藏主窗口
    setup_high_dpi(root)  # 配置高DPI

    # 设置初始目录（用户主目录，Windows优先文档文件夹）
    initial_dir = os.path.expanduser("~")
    if os.name == 'nt':
        docs_dir = os.path.join(os.environ.get('USERPROFILE', initial_dir), 'Documents')
        if os.path.exists(docs_dir):
            initial_dir = docs_dir

    folder_path = filedialog.askdirectory(
        title="选择要分析的代码文件夹",
        initialdir=initial_dir
    )

    # 验证文件夹有效性
    if not folder_path:
        print("❌ 未选择任何文件夹，程序退出")
        root.destroy()
        exit(1)
    if not os.path.exists(folder_path):
        print(f"❌ 错误：文件夹 {folder_path} 不存在")
        root.destroy()
        exit(1)

    # 提前检查是否有支持的代码文件（避免空分析）
    supported_exts = set(LANG_CONFIG.keys())
    has_supported_files = False
    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            if os.path.splitext(file)[1].lower() in supported_exts:
                has_supported_files = True
                break
        if has_supported_files:
            break
    if not has_supported_files:
        messagebox.showwarning("无有效文件", "所选文件夹中未找到任何支持的代码文件（如.py/.c/.java等），请重新选择！")
        root.destroy()
        exit(1)

    return folder_path, root

# ---------------------- 核心配置与工具函数 ----------------------
# 支持的编程语言及注释规则（可扩展）
LANG_CONFIG = {
    '.py': {'name': 'Python', 'single': '#', 'multi_start': ('"""', "'''"), 'multi_end': ('"""', "'''")},
    '.c': {'name': 'C', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.cpp': {'name': 'C++', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.h': {'name': 'C/C++ Header', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.java': {'name': 'Java', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.js': {'name': 'JavaScript', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.go': {'name': 'Go', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.html': {'name': 'HTML', 'single': None, 'multi_start': ('<!--',), 'multi_end': ('-->',)},
    '.css': {'name': 'CSS', 'single': None, 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.php': {'name': 'PHP', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.rb': {'name': 'Ruby', 'single': '#', 'multi_start': ('=begin',), 'multi_end': ('=end',)},
    '.rs': {'name': 'Rust', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.swift': {'name': 'Swift', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.ts': {'name': 'TypeScript', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.sql': {'name': 'SQL', 'single': '--', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.cs': {'name': 'C#', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.vb': {'name': 'Visual Basic', 'single': "'", 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.scala': {'name': 'Scala', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.kotlin': {'name': 'Kotlin', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.m': {'name': 'Objective-C', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.jsx': {'name': 'JSX', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.tsx': {'name': 'TSX', 'single': '//', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.lua': {'name': 'Lua', 'single': '--', 'multi_start': ('--[[',), 'multi_end': ('--]]',)},
    '.perl': {'name': 'Perl', 'single': '#', 'multi_start': ('=pod',), 'multi_end': ('=cut',)},
    '.sh': {'name': 'Shell', 'single': '#', 'multi_start': None, 'multi_end': None},
    '.r': {'name': 'R', 'single': '#', 'multi_start': ('/*',), 'multi_end': ('*/',)},
    '.matlab': {'name': 'MATLAB', 'single': '%', 'multi_start': ('%{',), 'multi_end': ('%}',)}
}

# 默认排除目录（可修改）
EXCLUDE_DIRS = [
    ".git", ".svn", ".hg",  # 版本控制
    "venv", "env", ".env", "virtualenv",  # 虚拟环境
    "node_modules", "bower_components",  # 前端依赖
    "dist", "build", "out", "target",  # 构建输出
    "__pycache__", ".pytest_cache", ".idea", ".vscode"  # 工具缓存/配置
]

def setup_matplotlib_font() -> str:
    """强制锁定中文字体，优化字体检测逻辑"""
    chinese_fonts = [
        'Microsoft YaHei', 'SimHei', 'Microsoft YaHei UI',  # Windows
        'PingFang SC', 'Heiti SC', 'Songti SC',              # macOS
        'WenQuanYi Zen Hei', 'Noto Sans CJK SC'              # Linux
    ]

    available_fonts = {font.name.lower(): font for font in fm.fontManager.ttflist}
    target_font = None
    for font_name in chinese_fonts:
        if font_name.lower() in available_fonts:
            target_font = available_fonts[font_name.lower()]
            break

    if not target_font:
        print("⚠️ 未找到任何中文字体，中文将显示异常！")
        print("   建议安装：微软雅黑（Windows）/ 苹方（macOS）/ 文泉驿正黑（Linux）")
        return 'DejaVu Sans'

    # 优化字体配置，避免冲突
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': [target_font.name, 'DejaVu Sans'],
        'axes.unicode_minus': False,
        'font.size': 11,
        'axes.titlesize': 14,
        'figure.titlesize': 16,
    })

    print(f"✅ 已锁定中文字体：{target_font.name}")
    return target_font.name

def count_code_lines(file_path: str, lang_config: dict) -> Tuple[int, int, int, int]:
    """统计单个文件行数，优化编码容错"""
    total = 0
    code = 0
    comment = 0
    blank = 0
    in_multi_comment = False

    # 优化编码处理：优先utf-8，失败则尝试gbk（Windows常见编码）
    encodings = ['utf-8', 'gbk', 'gb2312']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                for line in f:
                    total += 1
                    stripped_line = line.strip()

                    if not stripped_line:
                        blank += 1
                        continue

                    if in_multi_comment:
                        comment += 1
                        if lang_config['multi_end'] and any(end in stripped_line for end in lang_config['multi_end']):
                            in_multi_comment = False
                        continue

                    line_is_comment = False
                    # 处理单行注释
                    if lang_config['single'] and stripped_line.startswith(lang_config['single']):
                        comment += 1
                        line_is_comment = True
                    # 处理多行注释
                    elif lang_config['multi_start'] and any(start in stripped_line for start in lang_config['multi_start']):
                        comment += 1
                        line_is_comment = True
                        if lang_config['multi_end'] and not any(end in stripped_line for end in lang_config['multi_end']):
                            in_multi_comment = True

                    if not line_is_comment:
                        code += 1
            break  # 编码成功则退出循环
        except Exception:
            continue
    else:
        print(f"⚠️ 跳过无法解码的文件：{file_path}（尝试utf-8/gbk/gb2312均失败）")
        return (0, 0, 0, 0)

    return total, code, comment, blank

def scan_directory(root_dir: str) -> Tuple[Dict[str, Dict[str, Tuple[int, int, int, int]]], List[str]]:
    """递归扫描目录，优化排除逻辑和性能"""
    lang_stats = {}
    excluded_paths = []
    normalized_root = os.path.normpath(root_dir)
    supported_exts = set(LANG_CONFIG.keys())  # 提前缓存，避免重复查找

    for dirpath, dirnames, filenames in os.walk(normalized_root):
        # 优化排除逻辑：只检查当前目录名，不递归判断路径
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        excluded_paths.extend([os.path.join(dirpath, d) for d in EXCLUDE_DIRS if d in dirnames])

        # 只处理支持的文件类型
        for filename in filenames:
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext not in supported_exts:
                continue
            lang_name = LANG_CONFIG[file_ext]['name']
            if lang_name not in lang_stats:
                lang_stats[lang_name] = {}
            file_path = os.path.join(dirpath, filename)
            lang_stats[lang_name][file_path] = count_code_lines(file_path, LANG_CONFIG[file_ext])

    return lang_stats, excluded_paths

def calculate_total(lang_stats: Dict[str, Dict[str, Tuple[int, int, int, int]]]) -> Tuple[int, int, int, int]:
    """计算汇总统计，过滤无效文件（行数全为0）"""
    total_all = 0
    code_all = 0
    comment_all = 0
    blank_all = 0

    for file_stats in lang_stats.values():
        for (t, c, co, b) in file_stats.values():
            if t == 0:
                continue  # 跳过解码失败的文件
            total_all += t
            code_all += c
            comment_all += co
            blank_all += b

    return total_all, code_all, comment_all, blank_all

# ---------------------- 输出功能（Excel+饼图，固定生成）----------------------
def export_to_excel(lang_stats: Dict[str, Dict[str, Tuple[int, int, int, int]]], output_excel_path: str):
    """导出Excel报告，优化列宽和数据过滤"""
    # 过滤无效文件（行数全为0）
    detail_data = []
    for lang_name, file_stats in lang_stats.items():
        for file_path, (total, code, comment, blank) in file_stats.items():
            if total == 0:
                continue
            detail_data.append({
                '编程语言': lang_name,
                '文件路径': os.path.relpath(file_path),
                '总行数': total,
                '有效代码行数': code,
                '注释行数': comment,
                '空行数': blank
            })

    # 语言小计
    lang_summary_data = []
    for lang_name, file_stats in lang_stats.items():
        valid_files = [(t, c, co, b) for (t, c, co, b) in file_stats.values() if t > 0]
        if not valid_files:
            continue
        lang_total = sum(t for t, _, _, _ in valid_files)
        lang_code = sum(c for _, c, _, _ in valid_files)
        lang_comment = sum(co for _, _, co, _ in valid_files)
        lang_blank = sum(b for _, _, _, b in valid_files)
        lang_summary_data.append({
            '编程语言': lang_name,
            '文件数量': len(valid_files),
            '总行数': lang_total,
            '有效代码行数': lang_code,
            '注释行数': lang_comment,
            '空行数': lang_blank,
            '有效代码占比(%)': round((lang_code / lang_total) * 100, 2) if lang_total != 0 else 0
        })

    # 综合统计
    total_all, code_all, comment_all, blank_all = calculate_total(lang_stats)
    total_files = sum(len([f for f in file_stats.values() if f[0] > 0]) for file_stats in lang_stats.values())
    total_langs = len([l for l in lang_stats.values() if any(f[0] > 0 for f in l.values())])
    summary_data = [{
        '统计项': '综合统计',
        '涉及语言数': total_langs,
        '总文件数': total_files,
        '总行数': total_all,
        '有效代码行数': code_all,
        '注释行数': comment_all,
        '空行数': blank_all,
        '有效代码占比(%)': round((code_all / total_all) * 100, 2) if total_all != 0 else 0,
        '注释占比(%)': round((comment_all / total_all) * 100, 2) if total_all != 0 else 0,
        '空行占比(%)': round((blank_all / total_all) * 100, 2) if total_all != 0 else 0
    }]

    # 写入Excel并优化格式
    with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
        pd.DataFrame(detail_data).to_excel(writer, sheet_name='文件明细', index=False)
        pd.DataFrame(lang_summary_data).to_excel(writer, sheet_name='语言小计', index=False)
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='综合统计', index=False)

        # 自动调整列宽
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for col in worksheet.columns:
                col_letter = col[0].column_letter
                worksheet.column_dimensions[col_letter].auto_size = True
                # 路径列特殊处理
                if col[0].value == "文件路径" and worksheet.column_dimensions[col_letter].width < 50:
                    worksheet.column_dimensions[col_letter].width = 50

    print(f"\n✅ Excel报告已保存：{os.path.abspath(output_excel_path)}")

def generate_optimized_pie(lang_stats: Dict[str, Dict[str, Tuple[int, int, int, int]]], output_pie_path: str):
    """生成优化饼图，固定高分辨率"""
    used_font = setup_matplotlib_font()
    import seaborn as sns
    sns.set_style("whitegrid", {'grid.color': '.9'})

    # 计算统计数据（过滤无效文件）
    total_all, code_all, comment_all, blank_all = calculate_total(lang_stats)
    lang_totals = {}
    for lang, files in lang_stats.items():
        lang_total = sum(t for t, _, _, _ in files.values() if t > 0)
        if lang_total > 0:
            lang_totals[lang] = lang_total

    if not lang_totals:
        print("⚠️ 无有效数据，跳过饼图生成")
        return

    # 配色与画布设置
    lang_palette = sns.color_palette("pastel", len(lang_totals))
    comp_palette = sns.color_palette("muted", 3)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7), dpi=200)  # 提高分辨率

    # 总标题
    fig.suptitle(
        f'代码统计可视化报告（总行数：{total_all} 行 | 涉及 {len(lang_totals)} 种语言）',
        fontsize=16, fontweight='bold', fontfamily=used_font,
        y=1.05
    )

    # 左图：语言占比
    text_props = {'fontfamily': used_font, 'fontsize': 11, 'color': 'black', 'fontweight': 'bold'}
    wedges1, texts1, autotexts1 = ax1.pie(
        lang_totals.values(),
        labels=lang_totals.keys(),
        colors=lang_palette,
        autopct=lambda pct: f'{pct:.1f}%\n({int(pct / 100 * sum(lang_totals.values()))}行)',
        shadow=True,
        startangle=90,
        textprops=text_props,
        wedgeprops={'linewidth': 2, 'edgecolor': 'white'}
    )
    ax1.set_title('各语言代码量占比', fontsize=14, fontweight='bold', fontfamily=used_font, pad=20)
    ax1.axis('equal')

    # 右图：内容构成
    comp_labels = ['有效代码', '注释', '空行']
    comp_sizes = [code_all, comment_all, blank_all]
    wedges2, texts2, autotexts2 = ax2.pie(
        comp_sizes,
        labels=comp_labels,
        colors=comp_palette,
        explode=(0.1, 0, 0),
        autopct=lambda pct: f'{pct:.1f}%\n({int(pct / 100 * sum(comp_sizes))}行)',
        shadow=True,
        startangle=90,
        textprops=text_props,
        wedgeprops={'linewidth': 2, 'edgecolor': 'white'}
    )
    ax2.set_title('代码内容构成', fontsize=14, fontweight='bold', fontfamily=used_font, pad=20)
    ax2.axis('equal')

    # 布局优化
    plt.tight_layout()
    plt.subplots_adjust(top=0.9)

    # 保存饼图
    os.makedirs(os.path.dirname(output_pie_path), exist_ok=True)
    plt.savefig(
        output_pie_path,
        bbox_inches='tight',
        transparent=False,
        dpi=200
    )
    print(f"✅ 饼图已保存：{os.path.abspath(output_pie_path)}")

def generate_report(lang_stats: Dict[str, Dict[str, Tuple[int, int, int, int]]], output_excel_path: str, output_pie_path: str):
    """生成完整报告（Excel+饼图）"""
    if not lang_stats or calculate_total(lang_stats)[0] == 0:
        print("❌ 无有效统计数据，无法生成报告")
        return

    # 新增：创建输出目录（确保Excel和饼图的父目录存在）
    excel_dir = os.path.dirname(output_excel_path)
    if not os.path.exists(excel_dir):
        os.makedirs(excel_dir, exist_ok=True)
        print(f"📁 自动创建输出目录：{os.path.abspath(excel_dir)}")

    export_to_excel(lang_stats, output_excel_path)
    generate_optimized_pie(lang_stats, output_pie_path)

    # 控制台简要信息
    total_all, code_all, comment_all, blank_all = calculate_total(lang_stats)
    total_files = sum(len([f for f in file_stats.values() if f[0] > 0]) for file_stats in lang_stats.values())
    total_langs = len([l for l in lang_stats.values() if any(f[0] > 0 for f in l.values())])

    print("\n" + "=" * 80)
    print("📊 统计摘要")
    print("=" * 80)
    print(f"涉及语言：{total_langs}种（{', '.join([l for l in lang_stats.keys() if any(f[0] > 0 for f in lang_stats[l].values())])}）")
    print(f"有效文件：{total_files}个")
    print(f"总行数：{total_all}行")
    print(f"有效代码：{code_all}行（{round((code_all/total_all)*100,2)}%）")
    print(f"注释行数：{comment_all}行（{round((comment_all/total_all)*100,2)}%）")
    print(f"空行数：{blank_all}行（{round((blank_all/total_all)*100,2)}%）")
    print("=" * 80)

# ---------------------- 主函数 ----------------------
def main():
    print("=== 代码行数统计器（自动生成Excel+饼图）===")

    # 1. 选择目标文件夹
    try:
        TARGET_FOLDER, root = select_target_folder()
    except Exception as e:
        print(f"❌ 文件夹选择失败：{str(e)}")
        exit(1)

    # 2. 自动生成保存路径
    # 程序所在目录
    program_dir = os.path.dirname(os.path.abspath(__file__))
    # 选择的文件夹名称（过滤非法字符）
    folder_name = os.path.basename(TARGET_FOLDER)
    valid_folder_name = folder_name.replace('/', '').replace('\\', '').replace(':', '').replace('*', '').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '')
    # 结果目录：程序同目录/result/文件夹名
    result_dir = os.path.join(program_dir, "result", valid_folder_name)
    # 文件路径
    OUTPUT_EXCEL_PATH = os.path.join(result_dir, "代码分析报告.xlsx")
    OUTPUT_PIE_PATH = os.path.join(result_dir, f"代码分析饼图.png")

    # 3. 检查文件是否已存在
    existing_files = []
    if os.path.exists(OUTPUT_EXCEL_PATH):
        existing_files.append("Excel报告")
    if os.path.exists(OUTPUT_PIE_PATH):
        existing_files.append("饼图")
    if existing_files:
        try:
            root.deiconify()
            overwrite = messagebox.askyesno(
                title="文件已存在",
                message=f"以下文件已存在：\n{', '.join(existing_files)}\n是否覆盖？",
                parent=root
            )
            root.withdraw()
            if not overwrite:
                print("❌ 用户取消覆盖，程序退出")
                root.destroy()
                exit(0)
        except Exception as e:
            print(f"❌ 覆盖提示失败：{str(e)}")
            root.destroy()
            exit(1)

    # 4. 扫描目录
    print(f"\n📁 正在扫描目录：{TARGET_FOLDER}")
    print(f"🚫 排除目录：{', '.join(EXCLUDE_DIRS)}")
    lang_statistics, excluded_paths = scan_directory(TARGET_FOLDER)

    # 显示排除的目录（相对路径）
    if excluded_paths:
        print(f"\n已排除的目录（共{len(excluded_paths)}个）：")
        for path in excluded_paths[:10]:  # 最多显示10个，避免输出过长
            print(f"  - {os.path.relpath(path, TARGET_FOLDER)}")
        if len(excluded_paths) > 10:
            print(f"  - （还有{len(excluded_paths)-10}个目录已排除）")

    # 5. 生成报告
    generate_report(lang_statistics, OUTPUT_EXCEL_PATH, OUTPUT_PIE_PATH)

    # 释放资源
    root.destroy()
    print("\n✅ 分析完成！结果已保存至：")
    print(f"   📄 Excel报告：{os.path.abspath(OUTPUT_EXCEL_PATH)}")
    print(f"   📊 饼图文件：{os.path.abspath(OUTPUT_PIE_PATH)}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 程序运行失败：{str(e)}")
        exit(1)
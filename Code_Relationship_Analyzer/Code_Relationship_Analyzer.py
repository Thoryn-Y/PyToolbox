'''
Python代码关系分析器
'''

import ast
import networkx as nx
import matplotlib.pyplot as plt
import os
import sys
from typing import Dict, List, Set, Tuple, Optional
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
        title="选择要分析的Python项目文件夹",
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

    # 提前检查是否有Python文件（避免空分析）
    has_py_files = False
    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.py'):
                has_py_files = True
                break
        if has_py_files:
            break
    if not has_py_files:
        messagebox.showwarning("无有效文件", "所选文件夹中未找到任何.py文件，请重新选择！")
        root.destroy()
        exit(1)

    return folder_path, root

# 【可按需增删】默认排除目录（虚拟环境、缓存、版本控制等）
EXCLUDE_DIRS = [
    ".git", ".svn", ".hg",  # 版本控制
    "venv", "env", ".env", "virtualenv",  # 虚拟环境
    "node_modules", "bower_components",  # 前端依赖
    "dist", "build", "out", "target",  # 构建输出
    "__pycache__", ".pytest_cache", ".idea", ".vscode"  # 工具缓存/配置
]


class CodeRelationAnalyzer:
    def __init__(self):
        # 初始化数据结构存储分析结果
        self.function_calls: Dict[str, Set[str]] = {}  # 函数调用关系: {调用者: {被调用者集合}}
        self.class_inheritance: Dict[str, List[str]] = {}  # 类继承关系: {子类: [父类列表]}
        self.class_functions: Dict[str, List[str]] = {}  # 类中的函数: {类名: [函数名列表]}
        self.imports: Dict[str, List[str]] = {}  # 导入关系: {模块: [导入的内容]}
        self.all_functions: Set[str] = set()  # 所有函数名
        self.all_classes: Set[str] = set()    # 所有类名

        # 可视化配置、
        plt.rcParams.update({
            "figure.figsize": (14, 10),
            "font.family": ["SimHei", "Microsoft YaHei", "PingFang SC", "WenQuanYi Zen Hei", "Arial"],
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.unicode_minus": False
        })

    def _ensure_dir(self, file_path: str) -> None:
        """确保输出文件所在的目录存在，如果不存在则创建"""
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def analyze_file(self, file_path: str) -> None:
        """分析单个Python文件"""
        if not os.path.exists(file_path):
            print(f"⚠️ 文件不存在: {file_path}")
            return

        try:
            # 优化编码容错：尝试utf-8和gbk
            encodings = ['utf-8', 'gbk']
            code = None
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        code = f.read()
                    break
                except Exception:
                    continue
            if code is None:
                print(f"❌ 无法解码文件: {os.path.basename(file_path)}（尝试utf-8/gbk均失败）")
                return

            tree = ast.parse(code)
            self._analyze_ast(tree, os.path.basename(file_path))
            print(f"✅ 成功分析: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"❌ 分析 {os.path.basename(file_path)} 出错: {str(e)}")

    def analyze_directory(self, dir_path: str) -> None:
        """递归分析目录下所有子目录的Python文件（支持排除指定目录）"""
        if not os.path.isdir(dir_path):
            print(f"⚠️ 目录不存在: {dir_path}")
            return

        print(f"📂 开始分析目录: {dir_path}（含子目录）")
        print(f"🚫 正在排除目录: {', '.join(EXCLUDE_DIRS)}")
        total_python_files = 0  # 统计总文件数
        excluded_dir_count = 0  # 统计排除的目录数

        # 使用os.walk递归遍历所有子目录
        for root, dirnames, files in os.walk(dir_path):
            # 排除指定目录（直接匹配目录名，提升扫描速度）
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            excluded_dir_count += len([d for d in dirnames if d in EXCLUDE_DIRS])

            # 筛选当前子目录下的Python文件
            python_files = [f for f in files if f.endswith('.py')]
            total_python_files += len(python_files)

            # 分析当前子目录的Python文件
            for file in python_files:
                file_path = os.path.join(root, file)
                self.analyze_file(file_path)

        print(f"📊 目录分析完成：")
        print(f"   - 共发现 {total_python_files} 个Python文件")
        print(f"   - 共排除 {excluded_dir_count} 个无需分析的目录")

    def _analyze_ast(self, tree: ast.AST, file_name: str) -> None:
        """分析抽象语法树"""
        current_class = None

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._analyze_import(node, file_name)
            elif isinstance(node, ast.ClassDef):
                current_class = node.name
                self.all_classes.add(current_class)
                self._analyze_class(node, current_class)
            elif isinstance(node, ast.FunctionDef):
                self._analyze_function(node, current_class, file_name)


    def _analyze_import(self, node: ast.AST, file_name: str) -> None:
        """分析导入语句"""
        if file_name not in self.imports:
            self.imports[file_name] = []

        if isinstance(node, ast.Import):
            for alias in node.names:
                self.imports[file_name].append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module if node.module else ''
            for alias in node.names:
                self.imports[file_name].append(f"from {module} import {alias.name}")

    def _analyze_class(self, node: ast.ClassDef, class_name: str) -> None:
        """分析类定义和继承关系"""
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
                self.all_classes.add(base.id)

        self.class_inheritance[class_name] = bases
        self.class_functions[class_name] = []

    def _analyze_function(self, node: ast.FunctionDef, class_name: Optional[str], file_name: str) -> None:
        """分析函数定义和函数调用"""
        func_name = f"{class_name}.{node.name}" if class_name else node.name
        self.all_functions.add(func_name)

        if class_name:
            self.class_functions[class_name].append(node.name)

        if func_name not in self.function_calls:
            self.function_calls[func_name] = set()

        for sub_node in ast.walk(node):
            if isinstance(sub_node, ast.Call) and isinstance(sub_node.func, ast.Name):
                called_func = sub_node.func.id
                self.function_calls[func_name].add(called_func)
                self.all_functions.add(called_func)
            elif isinstance(sub_node, ast.Call) and isinstance(sub_node.func, ast.Attribute):
                if isinstance(sub_node.func.value, ast.Name):
                    called_method = f"{sub_node.func.value.id}.{sub_node.func.attr}"
                    self.function_calls[func_name].add(called_method)
                    self.all_functions.add(called_method)

    def visualize_function_calls(self, output_file: str = "function_calls.png") -> None:
        """可视化函数调用关系"""
        if not self.function_calls:
            print("ℹ️ 没有函数调用关系可可视化")
            return

        self._ensure_dir(output_file)
        G = nx.DiGraph()

        for caller, callees in self.function_calls.items():
            for callee in callees:
                G.add_edge(caller, callee)

        pos = nx.spring_layout(G, k=3, iterations=100)
        nx.draw_networkx_nodes(G, pos, node_size=2000, node_color='lightblue', alpha=0.8)
        nx.draw_networkx_edges(G, pos, arrowstyle='->', arrowsize=25, alpha=0.6)
        nx.draw_networkx_labels(G, pos, font_size=10)

        plt.title("函数调用关系图", fontsize=16, pad=20)
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"📊 函数调用关系图已保存至: {output_file}")

    def visualize_class_inheritance(self, output_file: str = "class_inheritance.png") -> None:
        """可视化类继承关系"""
        if not self.class_inheritance:
            print("ℹ️ 没有类继承关系可可视化")
            return

        self._ensure_dir(output_file)
        G = nx.DiGraph()

        for child, parents in self.class_inheritance.items():
            for parent in parents:
                G.add_edge(child, parent)

        pos = nx.spring_layout(G, k=4, iterations=100)
        nx.draw_networkx_nodes(G, pos, node_size=2500, node_color='lightgreen', alpha=0.8)
        nx.draw_networkx_edges(G, pos, arrowstyle='->', arrowsize=25, alpha=0.6)
        nx.draw_networkx_labels(G, pos, font_size=10)

        plt.title("类继承关系图", fontsize=16, pad=20)
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"📊 类继承关系图已保存至: {output_file}")

    def _generate_summary(self) -> str:
        """生成分析摘要文本（内部方法，不打印）"""
        summary_parts = []

        summary_parts.append("===== 代码关系分析摘要 =====")
        summary_parts.append(f"发现 {len(self.all_classes)} 个类")
        summary_parts.append(f"发现 {len(self.all_functions)} 个函数/方法")
        summary_parts.append(f"记录 {sum(len(calls) for calls in self.function_calls.values())} 个函数调用关系")
        summary_parts.append(f"记录 {sum(len(parents) for parents in self.class_inheritance.values())} 个类继承关系")

        summary_parts.append("\n===== 类继承关系 =====")
        for cls, parents in self.class_inheritance.items():
            if parents:
                summary_parts.append(f"{cls} 继承自: {', '.join(parents)}")
            else:
                summary_parts.append(f"{cls} 没有父类")

        summary_parts.append("\n===== 函数调用关系 =====")
        for caller, callees in self.function_calls.items():
            if callees:
                summary_parts.append(f"{caller} 调用了: {', '.join(callees)}")

        return "\n".join(summary_parts)

    def save_summary(self, output_file: str) -> None:
        """保存分析摘要到文本文件"""
        self._ensure_dir(output_file)
        summary = self._generate_summary()  # 只生成不打印
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(summary)
        print(f"📄 分析结果已保存至: {output_file}")

def main():
    print("🚀 Python代码关系分析器启动")

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
    # 输出文件路径
    summary_output_path = os.path.join(result_dir, "分析结果摘要.txt")
    function_call_image = os.path.join(result_dir, f"{valid_folder_name}_函数调用关系图.png")  # 饼图名=文件夹名
    class_inheritance_image = os.path.join(result_dir, f"{valid_folder_name}_类继承关系图.png")

    # 3. 检查文件是否已存在
    existing_files = []
    if os.path.exists(summary_output_path):
        existing_files.append("分析结果摘要.txt")
    if os.path.exists(function_call_image):
        existing_files.append("函数调用关系图.png")
    if os.path.exists(class_inheritance_image):
        existing_files.append("类继承关系图.png")
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

    # 4. 开始分析
    analyzer = CodeRelationAnalyzer()
    analyzer.analyze_directory(TARGET_FOLDER)  # 仅支持目录分析

    # 5. 保存分析结果
    analyzer.save_summary(summary_output_path)
    analyzer.visualize_function_calls(function_call_image)
    analyzer.visualize_class_inheritance(class_inheritance_image)

    # 释放资源
    root.destroy()
    print("\n✅ 分析完成！结果已保存至：")
    print(f"   📄 分析摘要：{os.path.abspath(summary_output_path)}")
    print(f"   📊 函数调用图：{os.path.abspath(function_call_image)}")
    print(f"   📊 类继承关系图：{os.path.abspath(class_inheritance_image)}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 程序运行失败：{str(e)}")
        exit(1)
'''
Python代码函数调用分析器
'''

import ast
import os
import sys
import networkx as nx
import matplotlib.pyplot as plt
from typing import Dict, List
from tkinter import Tk, filedialog, messagebox

# ---------------------- 高DPI适配配置（解决窗口模糊）----------------------
def setup_high_dpi(root):
    """在已创建的Tk实例上配置高DPI，避免重复创建实例冲突"""
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
def select_project_folder():
    """交互式选择要分析的项目文件夹（高DPI适配）"""
    root = Tk()
    root.withdraw()  # 隐藏主窗口
    setup_high_dpi(root)  # 配置高DPI

    # 设置初始目录（用户主目录）
    initial_dir = os.path.expanduser("~")
    if os.name == 'nt':
        # Windows优先尝试"文档"文件夹
        docs_dir = os.path.join(os.environ.get('USERPROFILE', initial_dir), 'Documents')
        if os.path.exists(docs_dir):
            initial_dir = docs_dir

    folder_path = filedialog.askdirectory(
        title="选择要分析的Python项目文件夹",
        initialdir=initial_dir
    )

    if not folder_path:
        print("❌ 未选择任何文件夹，程序退出")
        root.destroy()
        exit(1)

    # 验证文件夹是否存在且非空
    if not os.path.exists(folder_path):
        print(f"❌ 错误：文件夹 {folder_path} 不存在")
        root.destroy()
        exit(1)

    # 检查是否有.py文件（提前过滤无效文件夹）
    has_py_files = any(file.endswith('.py') for _, _, files in os.walk(folder_path) for file in files)
    if not has_py_files:
        messagebox.showwarning("无有效文件", "所选文件夹中未找到任何.py文件，请重新选择！")
        root.destroy()
        exit(1)

    return folder_path, root

# ---------------------- 分析逻辑----------------------
# 【可修改】：排除不需要分析的目录（可按需增删）
EXCLUDE_DIRS = [".idea", "venv", "__pycache__", "tests", ".git", "dist", "build"]

class FunctionCallAnalyzer(ast.NodeVisitor):
    """AST节点访问器，用于提取函数定义和函数调用关系"""

    def __init__(self):
        # 存储调用关系：key=调用者（函数/方法名），value=被调用者列表
        self.call_relations: Dict[str, List[str]] = {}
        # 记录当前正在分析的函数（用于关联“调用者”）
        self.current_function: str = ""
        # 记录当前所在的类（用于区分“类方法”，避免同名函数混淆）
        self.current_class: str = ""

    def _get_full_func_name(self, func_name: str) -> str:
        """生成完整的函数/方法名（类方法格式：类名.方法名，普通函数：函数名）"""
        if self.current_class:
            return f"{self.current_class}.{func_name}"
        return func_name

    # 处理类定义（记录当前类名，用于区分类方法）
    def visit_ClassDef(self, node: ast.ClassDef):
        self.current_class = node.name  # 进入类，记录类名
        self.generic_visit(node)  # 递归分析类内部的函数
        self.current_class = ""  # 离开类，清空类名

    # 处理普通函数定义（def xxx()）
    def visit_FunctionDef(self, node: ast.FunctionDef):
        # 生成当前函数的完整名称（区分普通函数/类方法）
        self.current_function = self._get_full_func_name(node.name)
        # 初始化该函数的调用关系（避免key不存在）
        if self.current_function not in self.call_relations:
            self.call_relations[self.current_function] = []

        # 递归分析函数内部的代码（提取调用关系）
        self.generic_visit(node)
        # 离开函数，清空当前函数名
        self.current_function = ""

    # 处理异步函数定义（async def xxx()）
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        # 逻辑和普通函数一致，只是处理异步函数
        self.current_function = self._get_full_func_name(node.name)
        if self.current_function not in self.call_relations:
            self.call_relations[self.current_function] = []

        self.generic_visit(node)
        self.current_function = ""

    # 处理函数调用（提取“被调用者”）
    def visit_Call(self, node: ast.Call):
        # 仅当当前在分析某个函数时（即有“调用者”），才记录调用关系
        if not self.current_function:
            self.generic_visit(node)
            return

        # 提取被调用的函数名（处理3种常见情况）
        called_func_name = ""
        if isinstance(node.func, ast.Name):
            # 情况1：直接调用普通函数（如 func_a()）
            called_func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # 情况2：调用类方法/对象方法（如 obj.method() 或 Class.method()）
            # 简化处理：取“对象/类名.方法名”（如 User.get_info）
            if isinstance(node.func.value, ast.Name):
                called_func_name = f"{node.func.value.id}.{node.func.attr}"
        elif isinstance(node.func, ast.Subscript):
            # 情况3：带下标的调用（如 func[0]()，暂不处理，避免误判）
            called_func_name = "unknown_subscript_call"

        # 过滤无效调用（如空名称、内置函数print/len等，可按需调整过滤规则）
        builtin_funcs = {"print", "len", "range", "dict", "list", "tuple", "set"}
        if called_func_name and called_func_name not in builtin_funcs:
            # 避免重复记录同一调用关系（如函数内多次调用同一函数，只记一次）
            if called_func_name not in self.call_relations[self.current_function]:
                self.call_relations[self.current_function].append(called_func_name)

        # 继续递归分析调用内部的节点（如函数参数中的嵌套调用）
        self.generic_visit(node)


def traverse_project_dir(project_root: str) -> List[str]:
    """遍历项目目录，收集所有需要分析的.py文件路径"""
    py_files = []
    for root, dirs, files in os.walk(project_root):
        # 排除不需要分析的目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        # 收集.py文件
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))
    return py_files

def generate_call_graph(call_relations: Dict[str, List[str]], save_path: str):
    """根据调用关系生成可视化有向图（箭头：调用者 → 被调用者）"""
    # 1. 构建有向图
    G = nx.DiGraph()
    # 添加所有节点（函数/方法）和边（调用关系）
    for caller, callees in call_relations.items():
        G.add_node(caller)  # 确保调用者作为节点存在
        for callee in callees:
            G.add_node(callee)  # 确保被调用者作为节点存在
            G.add_edge(caller, callee)  # 添加调用关系边

    # 2. 设置图表样式（可按需调整大小、布局）
    plt.figure(figsize=(20, 16))  # 图表大小（宽，高），越大越清晰
    # 布局算法：spring_layout（弹簧布局，避免节点重叠）
    pos = nx.spring_layout(G, k=4, iterations=50)  # k越大，节点间距越大

    # 3. 绘制节点和边
    nx.draw_networkx_nodes(G, pos, node_size=3000, node_color="#4CAF50", alpha=0.8)  # 节点样式
    nx.draw_networkx_edges(G, pos, arrowstyle="->", arrowsize=20, edge_color="#666666", alpha=0.6)  # 边样式
    nx.draw_networkx_labels(G, pos, font_size=10, font_family="SimHei")  # 节点标签（函数名）

    # 4. 隐藏坐标轴，保存图片
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches="tight")  # dpi越高，图片越清晰
    print(f"📊 调用关系图已保存到：{save_path}")

def main():
    print("=== Python代码函数调用分析器 ===")

    # 1. 选择项目文件夹（高DPI窗口）
    try:
        PROJECT_ROOT, root = select_project_folder()
    except Exception as e:
        print(f"❌ 文件夹选择失败：{str(e)}")
        exit(1)

    # 2. 自动生成保存路径（程序同目录/result/文件夹名.png）
    # 获取程序所在目录
    program_dir = os.path.dirname(os.path.abspath(__file__))
    # 结果文件夹路径（程序同目录下的result）
    result_dir = os.path.join(program_dir, "result")
    # 创建result文件夹（不存在则创建）
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
    # 文件夹名 = 选择的项目文件夹名称
    folder_name = os.path.basename(PROJECT_ROOT)
    # 完整保存路径（避免文件名非法字符）
    valid_folder_name = folder_name.replace('/', '').replace('\\', '').replace(':', '').replace('*', '').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '')
    SAVE_IMAGE_PATH = os.path.join(result_dir, f"{valid_folder_name}.png")

    # 检查文件是否已存在，提示覆盖
    if os.path.exists(SAVE_IMAGE_PATH):
        try:
            root.deiconify()  # 临时激活主窗口
            overwrite = messagebox.askyesno(
                title="文件已存在",
                message=f"图表文件\n{SAVE_IMAGE_PATH}\n已存在，是否覆盖？",
                parent=root
            )
            root.withdraw()
            if not overwrite:
                print("❌ 用户取消覆盖操作，程序退出")
                root.destroy()
                exit(0)
        except Exception as e:
            print(f"❌ 覆盖提示失败：{str(e)}")
            root.destroy()
            exit(1)

    # 3. 遍历项目，获取所有.py文件
    print(f"\n📁 正在遍历项目目录：{PROJECT_ROOT}")
    py_files = traverse_project_dir(PROJECT_ROOT)
    if not py_files:
        print("⚠️  警告：未找到任何.py文件（可能已被排除或无有效文件）")
        root.destroy()
        return
    print(f"✅ 共找到 {len(py_files)} 个.py文件，开始分析...")

    # 4. 初始化分析器，解析所有.py文件
    analyzer = FunctionCallAnalyzer()
    for file_path in py_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            # 将代码解析为AST，并交给分析器处理
            tree = ast.parse(code, filename=file_path)
            analyzer.visit(tree)
        except Exception as e:
            # 跳过解析失败的文件（如语法错误文件），避免整体流程中断
            print(f"⚠️  跳过解析失败的文件 {file_path}：{str(e)}")

    # 5. 生成并保存调用关系图
    if not analyzer.call_relations:
        print("⚠️  未提取到任何函数调用关系（可能是所有文件无有效函数调用，或解析异常）")
        root.destroy()
        return
    generate_call_graph(analyzer.call_relations, SAVE_IMAGE_PATH)

    # 6. 打印简要结果（可选，方便快速查看核心关系）
    print("\n=== 核心函数调用关系（前10条）===")
    count = 0
    for caller, callees in analyzer.call_relations.items():
        if callees:  # 只打印有调用关系的函数
            print(f"{caller} → {callees}")
            count += 1
            if count >= 10:
                break

    # 释放资源
    root.destroy()
    print("\n✅ 分析完成！")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 程序运行失败：{str(e)}")
        exit(1)
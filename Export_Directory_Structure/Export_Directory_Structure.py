'''
导出指定项目的目录结构（带GUI界面版本）
'''

from pathlib import Path
import sys
import os
from typing import Tuple, Optional, List
from tkinter import Tk, filedialog, messagebox, StringVar, BooleanVar, Text, Scrollbar, font
from tkinter import ttk


def setup_high_dpi(root: Tk) -> None:
    """在已创建的Tk实例上配置高DPI，避免窗口冲突"""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            dpi = ctypes.windll.user32.GetDpiForWindow(root.winfo_id())
            scaling_factor = dpi / 96
            root.tk.call('tk', 'scaling', scaling_factor)
        except Exception:
            root.tk.call('tk', 'scaling', 1.0)
    elif sys.platform == "darwin":
        root.tk.call('tk', 'scaling', 2.0)
    else:
        try:
            scaling_factor = root.winfo_fpixels('1i') / 96
            root.tk.call('tk', 'scaling', scaling_factor)
        except Exception:
            root.tk.call('tk', 'scaling', 1.0)


def select_folder_dialog(parent: Optional[Tk] = None, title: str = "选择文件夹") -> str:
    """弹出文件夹选择对话框，返回选择的路径"""
    initial_dir = os.path.expanduser("~")
    if os.name == 'nt':
        docs_dir = os.path.join(os.environ.get('USERPROFILE', initial_dir), 'Documents')
        if os.path.exists(docs_dir):
            initial_dir = docs_dir

    folder_path = filedialog.askdirectory(
        title=title,
        initialdir=initial_dir,
        parent=parent
    )
    return folder_path


IGNORE_PATTERNS = [
    ".git", "__pycache__", "*.pyc", "*.log", "venv", "*.env", ".idea",
    ".svn", ".hg", "node_modules", "dist", "build", "out", "target",
    ".pytest_cache", ".vscode", "*.tmp", "*.bak", "*.swp", "Synapse"
]

FILE_ICONS = {
    '.csv': '📊',
    '.html': '🌐',
    '.ini': '⚙️',
    '.log': '📋',
    '.md': '📝',
    '.markdown': '📝',
    '.rst': '📖',
    '.toml': '📋',
    '.tsv': '📊',
    '.txt': '📄',
    '.xml': '📰',
    '.yaml': '📋',
    '.yml': '📋',
    '.conf': '⚙️',
    '.cfg': '⚙️',
    '.tex': '📚',
    '.vtt': '📝',
    '.srt': '📝',
    '.c': '🔧',
    '.cpp': '🔧',
    '.cs': '🔷',
    '.dart': '🎯',
    '.go': '🐹',
    '.h': '🔧',
    '.ipynb': '📓',
    '.java': '☕',
    '.js': '📜',
    '.jsx': '⚛️',
    '.kt': '🅺',
    '.lua': '🌙',
    '.m': '🍎',
    '.php': '🐘',
    '.pl': '🐪',
    '.py': '🐍',
    '.pyc': '🐍',
    '.pyd': '🐍',
    '.r': '📊',
    '.rb': '💎',
    '.rs': '🦀',
    '.sh': '🐚',
    '.sql': '🗄️',
    '.swift': '🐦',
    '.ts': '📜',
    '.tsx': '⚛️',
    '.vue': '🖖',
    '.scala': '🔵',
    '.groovy': '🚀',
    '.hs': 'λ',
    '.f': '🔬',
    '.fs': '🔷',
    '.app': '📱',
    '.bat': '⚙️',
    '.bin': '🔧',
    '.cmd': '⚙️',
    '.dll': '🔗',
    '.exe': '⚙️',
    '.jar': '📦',
    '.so': '🔗',
    '.msi': '📦',
    '.deb': '📦',
    '.rpm': '📦',
    '.7z': '🗜️',
    '.bz2': '🗜️',
    '.gz': '🗜️',
    '.rar': '🗜️',
    '.tar': '🗜️',
    '.xz': '🗜️',
    '.zip': '🗜️',
    '.zst': '🗜️',
    '.lzma': '🗜️',
    '.cab': '🗜️',
    '.ai': '🎨',
    '.bmp': '🖼️',
    '.gif': '🖼️',
    '.ico': '🔣',
    '.jpeg': '🖼️',
    '.jpg': '🖼️',
    '.pdf': '📄',
    '.psd': '🖌️',
    '.svg': '🎨',
    '.tiff': '🖼️',
    '.webp': '🖼️',
    '.png': '🖼️',
    '.heic': '🖼️',
    '.raw': '📷',
    '.indd': '🎨',
    '.avi': '🎬',
    '.flac': '🎵',
    '.mkv': '🎬',
    '.mov': '🎬',
    '.mpeg': '🎬',
    '.mpg': '🎬',
    '.mp3': '🎵',
    '.mp4': '🎬',
    '.ogg': '🎵',
    '.wav': '🎵',
    '.wmv': '🎬',
    '.webm': '🎬',
    '.aac': '🎵',
    '.m4a': '🎵',
    '.flv': '🎬',
    '.3gp': '🎬',
    '.doc': '📄',
    '.docx': '📄',
    '.ppt': '🎤',
    '.pptx': '🎤',
    '.xls': '📊',
    '.xlsx': '📊',
    '.odt': '📄',
    '.ods': '📊',
    '.odp': '🎤',
    '.bak': '💾',
    '.gitignore': '🚫',
    '.img': '📀',
    '.iso': '📀',
    '.json': '🔑',
    '.lock': '🔒',
    '.patch': '🧩',
    '.tmp': '⏳',
    '.torrent': '📥',
    'LICENSE': '📜',
    'README.md': '📖',
    '.cer': '🔒',
    '.crt': '🔒',
    '.key': '🔑',
    '.pub': '🔑',
    '.db': '🗄️',
    '.sqlite': '🗄️',
    '.mdb': '🗄️',
    '.url': '🔗',
    '.lnk': '🔗'
}

DEFAULT_FILE_ICON = '📄'
DIRECTORY_ICON = '📂'


IGNORE_FILE_NAME = '.autosummaryignore'


def load_ignore_file(root_path: Path) -> tuple:
    """
    读取目标目录下的 .autosummaryignore 文件。
    返回 (ignore_deep, ignore_shallow)：
      - ignore_deep: 完全排除的名称列表（匹配文件名或目录名）
      - ignore_shallow: 浅排除的目录名列表（不含尾部斜杠）
    """
    ignore_file = root_path / IGNORE_FILE_NAME
    if not ignore_file.exists():
        return [], []
    ignore_deep = []
    ignore_shallow = []
    with open(ignore_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.endswith('/'):
                ignore_shallow.append(line.rstrip('/'))
            else:
                ignore_deep.append(line)
    return ignore_deep, ignore_shallow


def is_ignored(path: Path, patterns: list, ignore_deep: list = None) -> bool:
    """判断路径是否需要被忽略"""
    ignore_deep = ignore_deep or []
    # 检查 .autosummaryignore 中的完全排除规则
    if path.name in ignore_deep:
        return True
    # 原有逻辑：检查 GUI 中的全局 patterns（通配符规则）
    if path.name in patterns:
        return True
    for pattern in patterns:
        if '*' in pattern and path.match(pattern):
            return True
    return False


def get_file_icon(file_name: str) -> str:
    """根据文件名或扩展名获取对应的图标"""
    if file_name in FILE_ICONS:
        return FILE_ICONS[file_name]
    ext = Path(file_name).suffix.lower()
    return FILE_ICONS.get(ext, DEFAULT_FILE_ICON)


def generate_project_tree(start_path: str, ignore_patterns: list,
                          ignore_deep: list = None, ignore_shallow: list = None) -> str:
    """生成项目目录结构
    
    Args:
        start_path: 项目根目录路径
        ignore_patterns: 忽略规则列表
        ignore_deep: 完全排除的名称列表
        ignore_shallow: 浅排除的目录名列表
    """
    start_path = Path(start_path).resolve()

    # 读取目标目录下的 .autosummaryignore（与全局 patterns 叠加）
    file_deep, file_shallow = load_ignore_file(start_path)
    all_deep = list(set((ignore_deep or []) + file_deep))
    all_shallow = list(set((ignore_shallow or []) + file_shallow))

    if not start_path.exists():
        print(f"错误：路径不存在 - {start_path}", file=sys.stderr)
        return None

    tree = []
    tree.append(f"{DIRECTORY_ICON} {start_path.name} (完整路径: {start_path})")

    def traverse(current_path: Path, prefix: str = "", _deep=all_deep, _shallow=all_shallow):
        """递归遍历目录"""
        items = []
        for item in current_path.iterdir():
            if not is_ignored(item, ignore_patterns, _deep):
                items.append(item)

        items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            current_prefix = "└── " if is_last else "├── "

            if item.is_dir():
                # 浅排除：显示目录条目，但不递归子内容
                if item.name in _shallow:
                    tree.append(f"{prefix}{current_prefix}{DIRECTORY_ICON} {item.name}/  (... 内容已折叠)")
                    if is_last:
                        tree.append(f"{prefix}    ")
                    else:
                        tree.append(f"{prefix}│   ")
                    continue

                tree.append(f"{prefix}{current_prefix}{DIRECTORY_ICON} {item.name}")
                new_prefix = f"{prefix}    " if is_last else f"{prefix}│   "
                traverse(item, new_prefix, _deep, _shallow)
                if is_last:
                    tree.append(f"{prefix}    ")
                else:
                    tree.append(f"{prefix}│   ")
            else:
                icon = get_file_icon(item.name)
                tree.append(f"{prefix}{current_prefix}{icon} {item.name}")

    traverse(start_path)

    while tree and not tree[-1].strip():
        tree.pop()

    return "\n".join(tree)


def sanitize_folder_name(name: str) -> str:
    """过滤文件夹名中的非法字符"""
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    result = name
    for char in invalid_chars:
        result = result.replace(char, '')
    return result


class DirectoryStructureGenerator:
    """项目目录结构生成器GUI界面"""
    
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("项目目录结构生成器")
        self.root.geometry("1200x900")
        self.root.minsize(1000, 700)
        
        # 设置字体
        self.default_font = font.nametofont("TkDefaultFont")
        self.default_font.configure(size=14)
        
        # 获取脚本所在目录
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 变量
        self.project_path_var = StringVar()
        self.save_path_var = StringVar(value=os.path.join(self.script_dir, "result"))
        self.save_to_file_var = BooleanVar(value=False)
        
        self._setup_ui()
        
    def _setup_ui(self):
        """构建界面"""
        # 主框架，添加内边距
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        # ===== 顶部：项目路径选择区域 =====
        path_frame = ttk.LabelFrame(main_frame, text="项目路径", padding="10")
        path_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(path_frame, text="项目路径：").pack(side='left', padx=(0, 10))
        
        path_entry = ttk.Entry(path_frame, textvariable=self.project_path_var, width=60)
        path_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        browse_btn = ttk.Button(path_frame, text="浏览", command=self._browse_project_folder, width=12)
        browse_btn.pack(side='left')
        
        # ===== 中部：忽略规则区域 =====
        ignore_frame = ttk.LabelFrame(main_frame, text="忽略规则（每行一个，支持通配符）", padding="10")
        ignore_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        # 创建Text组件和滚动条
        text_frame = ttk.Frame(ignore_frame)
        text_frame.pack(fill='both', expand=True)
        
        # 设置文本组件字体
        text_font = font.Font(family="Consolas", size=12)
        
        self.ignore_text = Text(text_frame, wrap='none', height=12, font=text_font)
        scrollbar_y = Scrollbar(text_frame, orient='vertical', command=self.ignore_text.yview)
        scrollbar_x = Scrollbar(text_frame, orient='horizontal', command=self.ignore_text.xview)
        
        self.ignore_text.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # 布局
        self.ignore_text.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        
        # 初始化忽略规则内容
        self._init_ignore_patterns()
        
        # ===== 底部：保存设置区域 =====
        save_frame = ttk.LabelFrame(main_frame, text="保存设置", padding="10")
        save_frame.pack(fill='x', pady=(0, 15))
        
        # 第一行：复选框
        check_frame = ttk.Frame(save_frame)
        check_frame.pack(fill='x', pady=(0, 15))
        
        save_check = ttk.Checkbutton(
            check_frame, 
            text="保存到文件", 
            variable=self.save_to_file_var,
            command=self._on_save_checkbox_changed
        )
        save_check.pack(side='left')
        
        # 第二行：保存路径
        save_path_frame = ttk.Frame(save_frame)
        save_path_frame.pack(fill='x')
        
        ttk.Label(save_path_frame, text="保存路径：").pack(side='left', padx=(0, 10))
        
        save_entry = ttk.Entry(save_path_frame, textvariable=self.save_path_var, width=60)
        save_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        self.save_browse_btn = ttk.Button(
            save_path_frame, 
            text="浏览", 
            command=self._browse_save_folder, 
            width=12
        )
        self.save_browse_btn.pack(side='left')
        
        # 初始状态：根据复选框状态设置保存路径输入框的可用性
        self._on_save_checkbox_changed()
        
        # 最底部：操作按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(20, 0))
        
        # 设置按钮字体
        button_font = font.Font(size=14, weight="bold")
        
        generate_btn = ttk.Button(
            button_frame, 
            text="生成目录结构", 
            command=self._generate_structure,
            width=25
        )
        generate_btn.pack(side='left', padx=(0, 30))
        
        exit_btn = ttk.Button(
            button_frame, 
            text="退出", 
            command=self._on_exit,
            width=18
        )
        exit_btn.pack(side='left')
        
    def _init_ignore_patterns(self):
        """初始化忽略规则文本框内容"""
        self.ignore_text.delete('1.0', 'end')
        for pattern in IGNORE_PATTERNS:
            self.ignore_text.insert('end', pattern + '\n')
        # 移除最后一个多余的换行
        content = self.ignore_text.get('1.0', 'end-1c')
        if content.endswith('\n'):
            self.ignore_text.delete('end-2c', 'end-1c')
            
    def _browse_project_folder(self):
        """浏览选择项目文件夹"""
        folder = select_folder_dialog(self.root, "选择项目文件夹")
        if folder:
            self.project_path_var.set(folder)
            
    def _browse_save_folder(self):
        """浏览选择保存文件夹"""
        folder = select_folder_dialog(self.root, "选择保存文件夹")
        if folder:
            self.save_path_var.set(folder)
            
    def _on_save_checkbox_changed(self):
        """保存复选框状态改变时的处理"""
        # 可以在这里添加对保存路径输入框启用/禁用的逻辑
        pass
        
    def _get_ignore_patterns(self) -> List[str]:
        """从文本框获取忽略规则列表"""
        content = self.ignore_text.get('1.0', 'end-1c')
        patterns = []
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped:
                patterns.append(stripped)
        return patterns
    
    def _get_output_path(self, project_path: str) -> str:
        """获取输出文件路径
        
        智能判断保存路径是文件夹还是完整文件路径
        """
        save_path = self.save_path_var.get().strip()
        
        if not save_path:
            # 如果保存路径为空，使用默认的result目录
            save_path = os.path.join(self.script_dir, "result")
            
        save_path = os.path.abspath(save_path)
        
        # 判断是文件夹还是文件路径
        if save_path.endswith(os.sep) or os.path.isdir(save_path):
            # 是文件夹，自动拼接文件名
            folder_name = Path(project_path).name
            valid_name = sanitize_folder_name(folder_name)
            output_path = os.path.join(save_path, f"{valid_name}_目录结构.txt")
        else:
            # 视为完整文件路径
            output_path = save_path
            
        return output_path
    
    def _generate_structure(self):
        """生成目录结构"""
        # 获取项目路径
        project_path = self.project_path_var.get().strip()
        
        # 验证项目路径
        if not project_path:
            messagebox.showerror("错误", "请输入项目路径", parent=self.root)
            return
            
        if not os.path.exists(project_path):
            messagebox.showerror("错误", f"项目路径不存在：\n{project_path}", parent=self.root)
            return
            
        if not os.path.isdir(project_path):
            messagebox.showerror("错误", "项目路径必须是一个文件夹", parent=self.root)
            return
        
        # 获取忽略规则
        ignore_patterns = self._get_ignore_patterns()
        
        # 生成目录树
        print(f"\n📂 正在生成 {project_path} 的目录结构...")
        print(f"🚫 忽略的项目：{', '.join(ignore_patterns)}")
        
        tree = generate_project_tree(project_path, ignore_patterns, None, None)
        
        if not tree:
            messagebox.showerror("错误", "生成目录结构失败", parent=self.root)
            return
        
        # 打印到控制台
        print("\n" + "=" * 80)
        print(tree)
        print("=" * 80)
        
        # 根据复选框决定是否保存
        if self.save_to_file_var.get():
            output_path = self._get_output_path(project_path)
            
            # 检查文件是否已存在
            if os.path.exists(output_path):
                overwrite = messagebox.askyesno(
                    "文件已存在",
                    f"文件已存在：\n{output_path}\n\n是否覆盖？",
                    parent=self.root
                )
                if not overwrite:
                    print("❌ 用户取消覆盖，未保存文件")
                    messagebox.showinfo("提示", "目录结构已生成（未保存文件）\n请查看控制台输出", parent=self.root)
                    return
            
            # 保存文件
            try:
                output_dir = os.path.dirname(output_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                    
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(tree)
                    
                print(f"\n✅ 目录结构已保存到：{output_path}")
                messagebox.showinfo(
                    "成功", 
                    f"目录结构已生成并保存到：\n{output_path}", 
                    parent=self.root
                )
            except Exception as e:
                error_msg = f"保存文件失败：{str(e)}"
                print(f"\n❌ {error_msg}", file=sys.stderr)
                messagebox.showerror("错误", error_msg, parent=self.root)
        else:
            messagebox.showinfo("成功", "目录结构已生成\n请查看控制台输出", parent=self.root)
            
    def _on_exit(self):
        """退出程序"""
        self.root.destroy()


def main():
    """主函数"""
    print("🚀 项目目录结构生成器启动")
    
    root = Tk()
    setup_high_dpi(root)
    
    app = DirectoryStructureGenerator(root)
    
    root.mainloop()
    
    print("\n🎉 程序已退出")


def watch_and_regenerate(start_path: str, ignore_patterns: list,
                         ignore_deep: list = None, ignore_shallow: list = None,
                         output_path: str = None):
    """
    监控目录变化，自动重新生成目录树。
    output_path: 若提供，每次重新生成后自动写入该文件
    """
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    import signal
    import time

    class RegenerateHandler(FileSystemEventHandler):
        def __init__(self):
            self._last_trigger = 0

        def on_any_event(self, event):
            now = time.time()
            # 防抖：1秒内不重复触发
            if now - self._last_trigger < 1.0:
                return
            # 忽略输出文件本身的修改事件
            if output_path and event.src_path == str(Path(output_path).resolve()):
                return
            self._last_trigger = now
            print(f"\n🔄 检测到变动: {event.src_path}，重新生成...")
            new_tree = generate_project_tree(start_path, ignore_patterns,
                                             ignore_deep, ignore_shallow)
            if output_path and new_tree:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(new_tree)
                print(f"✅ 已自动更新：{output_path}")

    handler = RegenerateHandler()
    observer = Observer()
    observer.schedule(handler, start_path, recursive=True)
    observer.start()

    def shutdown(signum, frame):
        """系统关机或终止信号处理：停止 observer 后退出"""
        print("\n🛑 收到系统关闭信号，正在停止监控...")
        observer.stop()
        observer.join()
        sys.exit(0)

    # 注册信号处理：Ctrl+C、SIGTERM、Windows 关机/控制台关闭
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    if sys.platform == 'win32':
        signal.signal(signal.SIGBREAK, shutdown)

    print("👁️ 已开始监控目录变动... (Ctrl+C 停止)")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="项目目录结构生成器")
    parser.add_argument('-r', '--root', type=str, default=None,
                        help='要扫描的目标目录路径（不指定则启动 GUI 模式）')
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='输出文件路径（可选，默认输出到目标目录下的 目录结构.txt）')
    parser.add_argument('-w', '--watch', action='store_true',
                        help='启用 watchdog 监控，文件变动时自动重新生成')
    args = parser.parse_args()

    if args.root is None:
        # 无参数：启动 GUI 模式
        try:
            main()
        except Exception as e:
            print(f"❌ 程序运行失败：{str(e)}", file=sys.stderr)
            exit(1)
    else:
        # 有参数：命令行模式
        root_path = Path(args.root).resolve()
        if not root_path.is_dir():
            print(f"错误：路径不存在或不是目录 - {root_path}", file=sys.stderr)
            exit(1)

        # 确定输出路径
        if args.output:
            output_path = Path(args.output).resolve()
        else:
            output_path = root_path / f"{root_path.name}_目录结构.txt"

        # 读取忽略文件
        ignore_deep, ignore_shallow = load_ignore_file(root_path)

        print(f"📂 正在生成 {root_path} 的目录结构...")
        tree = generate_project_tree(str(root_path), IGNORE_PATTERNS,
                                     ignore_deep, ignore_shallow)
        if tree:
            output_dir = output_path.parent
            if output_dir and not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(tree)
            print(f"✅ 已保存到：{output_path}")

            if args.watch:
                print("👁️ 启动监控模式...")
                watch_and_regenerate(str(root_path), IGNORE_PATTERNS,
                                     ignore_deep, ignore_shallow,
                                     output_path=str(output_path))
        else:
            print("生成失败", file=sys.stderr)
            exit(1)

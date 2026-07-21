'''
GUI 界面：项目目录结构生成器的图形界面
'''

import os
import sys
from pathlib import Path
from typing import List, Optional

from tkinter import Tk, filedialog, messagebox, StringVar, BooleanVar, Text, Scrollbar, font, PanedWindow
from tkinter import ttk

from tree import IGNORE_PATTERNS, generate_project_tree, sanitize_folder_name


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


class DirectoryStructureGenerator:
    """项目目录结构生成器GUI界面"""
    
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("项目目录结构生成器")
        self.root.geometry("1200x1200")
        self.root.minsize(1000, 700)
        
        # 设置字体
        self.default_font = font.nametofont("TkDefaultFont")
        self.default_font.configure(size=14)
        
        # 获取脚本所在目录
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 变量
        self.project_path_var = StringVar()
        self.save_path_var = StringVar(
            value=os.path.abspath(os.path.join(self.script_dir, "result"))
        )
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
        
        # ===== 中部：可调整区域（忽略规则 + 生成结果）=====
        paned = PanedWindow(main_frame, orient='vertical', sashrelief='ridge', sashwidth=5)
        paned.pack(fill='both', expand=True, pady=(0, 15))

        # 上半部分：忽略规则
        ignore_frame = ttk.LabelFrame(paned, text="忽略规则（每行一个，支持通配符）", padding="10")
        paned.add(ignore_frame, stretch='always')

        # 创建Text组件和滚动条
        text_frame = ttk.Frame(ignore_frame)
        text_frame.pack(fill='both', expand=True)

        # 设置文本组件字体
        text_font = font.Font(family="Consolas", size=12)

        self.ignore_text = Text(text_frame, wrap='none', height=8, font=text_font)
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

        # 下半部分：生成结果
        result_frame = ttk.LabelFrame(paned, text="生成结果", padding="10")
        paned.add(result_frame, stretch='always')

        result_text_frame = ttk.Frame(result_frame)
        result_text_frame.pack(fill='both', expand=True)

        self.result_text = Text(result_text_frame, wrap='none', height=12, font=text_font, state='disabled')
        result_scrollbar_y = Scrollbar(result_text_frame, orient='vertical', command=self.result_text.yview)
        result_scrollbar_x = Scrollbar(result_text_frame, orient='horizontal', command=self.result_text.xview)

        self.result_text.configure(yscrollcommand=result_scrollbar_y.set, xscrollcommand=result_scrollbar_x.set)

        self.result_text.grid(row=0, column=0, sticky='nsew')
        result_scrollbar_y.grid(row=0, column=1, sticky='ns')
        result_scrollbar_x.grid(row=1, column=0, sticky='ew')

        result_text_frame.grid_rowconfigure(0, weight=1)
        result_text_frame.grid_columnconfigure(0, weight=1)
        
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
        
        self.save_entry = ttk.Entry(save_path_frame, textvariable=self.save_path_var, width=60)
        self.save_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
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
        # 根据复选框状态启用/禁用保存路径输入框和浏览按钮
        state = 'normal' if self.save_to_file_var.get() else 'disabled'
        self.save_entry.configure(state=state)
        self.save_browse_btn.configure(state=state)
        
    def _set_result_text(self, text: str) -> None:
        """在生成结果文本框中显示内容"""
        self.result_text.config(state='normal')
        self.result_text.delete('1.0', 'end')
        self.result_text.insert('1.0', text)
        self.result_text.config(state='disabled')
        self.result_text.see('1.0')

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
            self._set_result_text("")
            messagebox.showerror("错误", "生成目录结构失败", parent=self.root)
            return
        
        # 在GUI中显示结果
        self._set_result_text(tree)

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

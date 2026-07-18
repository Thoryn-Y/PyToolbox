import re
import os
import sys
from tkinter import Tk, filedialog, messagebox


# ---------------------- 优化后的 DPI 适配代码（解决窗口冲突+模糊）----------------------
def setup_high_dpi(root):
    """在已创建的Tk实例上配置高DPI，避免重复创建实例冲突"""
    if sys.platform == "win32":
        # Windows 系统：使用 ctypes 调用系统 API 开启 DPI 感知
        try:
            import ctypes
            # 设置进程 DPI 感知（Windows 8.1+ 支持，兼容绝大多数现代 Windows 系统）
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 1 = 系统 DPI 感知
            # 获取系统 DPI 缩放比例，设置给 Tkinter
            dpi = ctypes.windll.user32.GetDpiForWindow(root.winfo_id())
            scaling_factor = dpi / 96  # 96 是标准 DPI
            root.tk.call('tk', 'scaling', scaling_factor)
        except Exception:
            # 兼容旧版 Windows 或调用失败时，使用 Tkinter 自带缩放
            root.tk.call('tk', 'scaling', 1.0)
    elif sys.platform == "darwin":
        # macOS 系统：默认支持高 DPI，只需开启 Tkinter 缩放
        root.tk.call('tk', 'scaling', 2.0)  # macOS 视网膜屏优化
    else:
        # Linux 系统：根据系统 DPI 自动适配
        try:
            scaling_factor = root.winfo_fpixels('1i') / 96  # 获取实际 DPI 比例
            root.tk.call('tk', 'scaling', scaling_factor)
        except Exception:
            root.tk.call('tk', 'scaling', 1.0)


# --------------------------------------------------------------------------------

def select_python_file():
    """交互式选择Python文件（使用单一Tk实例，避免冲突）"""
    root = Tk()
    root.withdraw()  # 隐藏主窗口
    setup_high_dpi(root)  # 在同一个实例上配置高DPI

    # 设置初始目录
    initial_dir = os.path.expanduser("~")  # 统一使用用户主目录作为初始目录
    if os.name == 'nt':
        # Windows系统优先尝试"文档"文件夹
        docs_dir = os.path.join(os.environ.get('USERPROFILE', initial_dir), 'Documents')
        if os.path.exists(docs_dir):
            initial_dir = docs_dir

    file_path = filedialog.askopenfilename(
        title="选择要处理的Python文件",
        filetypes=[("Python Files", "*.py"), ("All Files", "*.*")],
        initialdir=initial_dir
    )

    # 不销毁root，后续复用（避免重复创建实例）
    return file_path, root


def remove_comments_from_copy(file_path, root):
    # 生成副本路径
    file_dir = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)
    file_name_no_ext, ext = os.path.splitext(file_name)
    copy_path = os.path.join(file_dir, f"{file_name_no_ext}_no_annotation{ext}")

    # 检查副本文件是否已存在
    if os.path.exists(copy_path):
        print(f"⚠️  检测到副本文件已存在：{copy_path}")
        try:
            # 复用同一个Tk实例显示提示（避免冲突）
            root.deiconify()  # 临时显示主窗口（确保消息框能正常弹出）
            overwrite = messagebox.askyesno(
                title="文件已存在",
                message=f"副本文件\n{copy_path}\n已存在，是否覆盖？",
                parent=root
            )
            root.withdraw()  # 再次隐藏主窗口
            if not overwrite:
                print("❌ 用户取消覆盖操作，程序退出")
                root.destroy()
                exit(0)
        except Exception as e:
            print(f"❌ 显示覆盖提示失败：{str(e)}")
            root.destroy()
            exit(1)

    # 复制原文件生成副本
    try:
        with open(file_path, 'r', encoding='utf-8') as src, open(copy_path, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
        print(f"📁 已创建/覆盖原文件副本：{copy_path}")
        print(f"🔒 不修改原文件：{file_path}\n")
    except Exception as e:
        print(f"❌ 复制文件失败：{str(e)}")
        root.destroy()
        exit(1)

    # 读取副本内容
    with open(copy_path, 'r', encoding='utf-8') as f:
        content = f.read()

    deleted_comments = []
    comment_id = 1

    # 更可靠的字符串保护机制：使用状态机区分代码和字符串区域
    protected_content = []
    in_single_quote = False  # 单引号字符串状态
    in_double_quote = False  # 双引号字符串状态
    in_triple_single = False  # 三重单引号状态
    in_triple_double = False  # 三重双引号状态

    i = 0
    n = len(content)
    while i < n:
        # 处理三重引号
        if i + 2 < n:
            # 三重双引号
            if content[i:i + 3] == '"""' and not in_single_quote and not in_triple_single:
                in_triple_double = not in_triple_double
                protected_content.append(content[i:i + 3])
                i += 3
                continue
            # 三重单引号
            if content[i:i + 3] == "'''" and not in_double_quote and not in_triple_double:
                in_triple_single = not in_triple_single
                protected_content.append(content[i:i + 3])
                i += 3
                continue

        # 处理单引号和双引号
        if content[i] == '"' and not in_single_quote and not in_triple_single:
            in_double_quote = not in_double_quote
            protected_content.append('"')
            i += 1
            continue
        if content[i] == "'" and not in_double_quote and not in_triple_double:
            in_single_quote = not in_single_quote
            protected_content.append("'")
            i += 1
            continue

        # 在字符串内部时替换#为特殊标记
        if in_double_quote or in_single_quote or in_triple_double or in_triple_single:
            if content[i] == '#':
                protected_content.append('＃')  # 全角#作为临时标记
            else:
                protected_content.append(content[i])
        else:
            protected_content.append(content[i])
        i += 1

    protected_str = ''.join(protected_content)

    # 处理单独成行的注释
    def capture_single_line_comment(match):
        nonlocal comment_id
        indent = match.group(1)
        comment_content = match.group(2).strip()
        deleted_comments.append(f"{comment_id}. 单行注释：#{comment_content}")
        comment_id += 1
        return indent

    # 匹配规则：行首缩进 + # + 注释内容（整行无其他代码）
    protected_str = re.sub(r'^(\s*)#(.+)$', capture_single_line_comment,
                           protected_str, flags=re.MULTILINE)

    # 处理行内注释
    def capture_inline_comment(match):
        nonlocal comment_id
        code_part = match.group(1).rstrip()
        comment_content = match.group(2).strip()
        deleted_comments.append(f"{comment_id}. 行内注释：#{comment_content}")
        comment_id += 1
        return code_part

    # 匹配规则：代码内容 + 空格 + # + 注释内容
    protected_str = re.sub(r'(.+?)\s+#(.+)$', capture_inline_comment,
                           protected_str, flags=re.MULTILINE)

    # 恢复字符串中的#
    content = protected_str.replace('＃', '#')

    # 优化空行处理：保留最多2个连续空行
    content = re.sub(r'\n{3,}', '\n\n', content).strip() + '\n'  # 确保文件以换行结束

    # 写回处理后的内容
    with open(copy_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # 打印删除记录
    print(f"📝 共删除 {len(deleted_comments)} 个Python注释：")
    for comment in deleted_comments:
        print(comment)
    print(f"\n✅ 处理完成！")
    print(f"📄 无注释副本文件：{copy_path}")
    print(f"🔒 原文件未被修改：{file_path}")

    # 销毁Tk实例，释放资源
    root.destroy()


if __name__ == "__main__":
    print("=== Annotation_Deleter - Python注释删除工具 ===")
    try:
        file_path, root = select_python_file()
        remove_comments_from_copy(file_path, root)
    except UnicodeDecodeError:
        print(f"❌ 处理失败：文件编码不是UTF-8，请确保目标文件以UTF-8编码保存")
        try:
            root.destroy()
        except:
            pass
    except PermissionError:
        print(f"❌ 处理失败：无权限访问文件，请检查文件是否被占用或权限设置")
        try:
            root.destroy()
        except:
            pass
    except Exception as e:
        print(f"❌ 处理失败：{str(e)}")
        try:
            root.destroy()
        except:
            pass
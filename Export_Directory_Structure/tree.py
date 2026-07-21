'''
核心目录树生成：忽略规则解析 + 目录遍历 + 树形文本构建
'''

from pathlib import Path
import sys
from typing import List

from icons import get_file_icon, DIRECTORY_ICON

IGNORE_PATTERNS = [
    ".git", "__pycache__", "*.pyc", "*.log", "venv", "*.env", ".idea",
    ".svn", ".hg", "node_modules", "dist", "build", "out", "target",
    ".pytest_cache", ".vscode", "*.tmp", "*.bak", "*.swp", "Synapse"
]

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
    # 遍历所有 pattern，path.match 同时处理精确匹配和通配符匹配
    for pattern in patterns:
        if path.match(pattern):
            return True
    return False


def sanitize_folder_name(name: str) -> str:
    """过滤文件夹名中的非法字符"""
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    result = name
    for char in invalid_chars:
        result = result.replace(char, '')
    return result


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
        try:
            entries = list(current_path.iterdir())
        except PermissionError:
            # 无权限访问：添加标记并跳过该目录内容
            tree.append(f"{prefix}    🔒 (无权限访问)")
            return
        for item in entries:
            if not is_ignored(item, ignore_patterns, _deep):
                items.append(item)

        items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            current_prefix = "└── " if is_last else "├── "

            if item.is_dir():
                # 符号链接：显示但不递归，防止无限循环
                if item.is_symlink():
                    tree.append(f"{prefix}{current_prefix}{DIRECTORY_ICON} {item.name}/  (→ 符号链接)")
                    if is_last:
                        tree.append(f"{prefix}    ")
                    else:
                        tree.append(f"{prefix}│   ")
                    continue
                
                # 浅排除：显示目录条目，但不递归子内容
                if item.name in _shallow:
                    tree.append(f"{prefix}{current_prefix}{DIRECTORY_ICON} {item.name}/  (... 内容已折叠)")
                    if is_last:
                        tree.append(f"{prefix}    ")
                    else:
                        tree.append(f"{prefix}│   ")
                    continue

                tree.append(f"{prefix}{current_prefix}{DIRECTORY_ICON} {item.name}/")
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

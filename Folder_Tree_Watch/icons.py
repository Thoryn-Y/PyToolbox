# -*- coding: utf-8 -*-
"""
文件图标映射：按扩展名或文件名返回 emoji 图标。

纯数据模块，不含业务逻辑；改图标只需动下面的 _GROUPS / _NAME_ICONS。
"""

from pathlib import Path

# 图标 -> 扩展名集合（不含点号，全小写；同一扩展名以后出现的组为准）
_GROUPS = {
    # ---------- 代码 ----------
    "🐍": ("py", "pyw", "pyi", "pyc", "pyd"),
    "📓": ("ipynb",),
    "📜": ("js", "mjs", "cjs", "ts"),
    "⚛️": ("jsx", "tsx"),
    "🖖": ("vue", "svelte"),
    "☕": ("java",),
    "🔧": ("c", "h", "cpp", "hpp", "cc", "cxx", "m", "asm", "s"),
    "🔷": ("cs", "fs"),
    "🐹": ("go",),
    "🦀": ("rs",),
    "💎": ("rb",),
    "🐘": ("php",),
    "🐦": ("swift",),
    "🅺": ("kt", "kts"),
    "🔵": ("scala", "groovy"),
    "🌙": ("lua",),
    "🎯": ("dart",),
    "λ": ("hs",),
    "📊": ("r", "rmd", "sas", "do"),
    "🐚": ("sh", "bash", "zsh", "fish"),
    "⚙️": ("bat", "cmd", "ps1", "psm1", "vbs"),
    "🧪": ("ex", "exs", "erl", "clj", "jl"),
    # ---------- 前端 / 标记 ----------
    "🌐": ("html", "htm", "xhtml"),
    "🎨": ("css", "scss", "sass", "less", "styl", "svg", "ai", "indd"),
    "📰": ("xml", "xsd", "xsl", "plist"),
    "📝": ("md", "markdown", "mdx", "vtt", "srt", "ass"),
    "📖": ("rst", "adoc", "tex", "bib"),
    # ---------- 配置 / 数据 ----------
    "📋": ("yaml", "yml", "toml", "ini", "conf", "cfg", "properties", "txt", "log"),
    "🔑": ("json", "jsonc", "key", "pub", "pem"),
    "🔒": ("lock", "cer", "crt", "p12", "pfx"),
    "🗄️": ("sql", "db", "sqlite", "sqlite3", "mdb", "accdb", "parquet"),
    "📈": ("csv", "tsv", "xls", "xlsx", "ods", "npy", "npz", "h5", "hdf5",
           "pkl", "pt", "pth", "ckpt", "onnx"),
    # ---------- 文档 ----------
    "📄": ("pdf", "doc", "docx", "odt", "rtf", "pages"),
    "🎤": ("ppt", "pptx", "odp"),
    "📚": ("epub", "mobi", "azw3"),
    # ---------- 图片 ----------
    "🖼️": ("png", "jpg", "jpeg", "gif", "bmp", "webp", "tif", "tiff", "heic", "avif"),
    "🖌️": ("psd", "xcf", "sketch", "fig"),
    "📷": ("raw", "cr2", "nef", "arw", "dng"),
    "🔣": ("ico", "icns"),
    # ---------- 音视频 ----------
    "🎵": ("mp3", "wav", "flac", "ogg", "aac", "m4a", "opus", "wma", "mid"),
    "🎬": ("mp4", "mkv", "avi", "mov", "wmv", "webm", "flv", "mpeg", "mpg", "m4v", "3gp"),
    # ---------- 压缩 / 镜像 / 二进制 ----------
    "🗜️": ("zip", "7z", "rar", "tar", "gz", "tgz", "xz", "bz2", "zst", "lzma", "cab"),
    "📀": ("iso", "img", "vhd", "vhdx"),
    "📦": ("jar", "war", "whl", "msi", "deb", "rpm", "apk", "ipa", "aab", "gem", "nupkg"),
    "🔗": ("dll", "so", "dylib", "lnk", "url", "webloc"),
    "🖥️": ("exe", "app", "bin", "elf", "o", "obj", "lib", "class"),
    "💾": ("bak", "old", "orig", "swp", "swo", "part", "crdownload"),
    "⏳": ("tmp",),
}

# 特殊文件名（整名匹配，优先级高于扩展名）
_NAME_ICONS = {
    "readme.md": "📖",
    "readme": "📖",
    "license": "📜",
    "license.md": "📜",
    "copying": "📜",
    "changelog.md": "📜",
    "makefile": "🔧",
    "cmakelists.txt": "🔧",
    "dockerfile": "🐳",
    "docker-compose.yml": "🐳",
    "requirements.txt": "📋",
    "package.json": "📦",
    "pyproject.toml": "⚙️",
    "setup.py": "⚙️",
    ".gitignore": "🚫",
    ".gitattributes": "🚫",
    ".env": "🔒",
}

DEFAULT_FILE_ICON = "📄"

# 扩展名 -> 图标（同一扩展名取最后定义的那个组）
FILE_ICONS = {}
for _icon, _exts in _GROUPS.items():
    for _ext in _exts:
        FILE_ICONS[_ext] = _icon
del _icon, _exts, _ext


def get_file_icon(file_name: str) -> str:
    """根据文件名（优先）或扩展名返回 emoji 图标。"""
    lowered = file_name.lower()
    icon = _NAME_ICONS.get(lowered)
    if icon:
        return icon
    return FILE_ICONS.get(Path(lowered).suffix.lstrip("."), DEFAULT_FILE_ICON)

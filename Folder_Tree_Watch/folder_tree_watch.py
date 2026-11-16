#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
folder_tree_watch.py —— 把文件夹结构渲染成可折叠 HTML，并用 watchdog 监控变化自动重新生成。

安装依赖:
    pip install watchdog

用法:
    python folder_tree_watch.py                          # 当前目录，产物写到 <当前目录>/<目录名>_structure.html
    python folder_tree_watch.py /path/to/folder
    python folder_tree_watch.py . -o tree.html --show-hidden
    python folder_tree_watch.py . --no-watch             # 只生成一次
    python folder_tree_watch.py . --refresh 3            # 浏览器每 3 秒重载一次
    python folder_tree_watch.py . --ignore "*.log" --collapse-depth -1

说明:
    * 生成的 HTML 用 <details>/<summary> 实现可折叠目录树，不依赖 JS（搜索与右键菜单除外）。
    * 默认输出落在【被扫描目录内】（<目录>/<目录名>_structure.html）；输出文件与它的 .tmp
      中间文件会被自动排除在扫描和监控之外，避免"写 HTML -> 触发事件 -> 再写 HTML"。
    * 右键任意文件 / 文件夹会弹出菜单：「复制路径」把绝对路径写进剪贴板
      （粘贴到资源管理器地址栏即可跳转；对文件会直接定位到该文件）。
      纯静态实现，双击打开 HTML 即可用，不需要任何后台进程。
    * 符号链接不跟随（既避免环，也避免扫到目录外面去）。
    * 每行右侧显示体积：文件夹是【该目录整体占用】（递归累加，含全部子目录），
      文件是自身大小。体积按忽略规则计算，被忽略的条目（如 __pycache__、node_modules）
      不计入，因此可能小于资源管理器里看到的值；被 --max-depth / --max-entries 截断时
      显示 "≥ x" 或 "—" 表示不完整。
    * 样式与 HTML 外壳放在同目录 templates/ 下（tree.html / tree.css），改版式不必动本文件。
    * 忽略规则支持通配符（* ? []），可写成文件名模式（"*.pyc"）或相对路径模式（"build/*"）。
"""

from __future__ import annotations

import argparse
import fnmatch
import html
import os
import signal
import sys
import threading
import time
import traceback
from pathlib import Path

from icons import get_file_icon

# watchdog 缺失时不让模块导入即崩（否则无法被 import / 单测），改为 main() 里报错退出。
try:  # pragma: no cover
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    _WATCHDOG_ERROR: ImportError | None = None
except ImportError as _exc:  # pragma: no cover
    FileSystemEventHandler = object  # type: ignore[assignment,misc]
    Observer = None  # type: ignore[assignment]
    _WATCHDOG_ERROR = _exc


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# 内置忽略项：通配符按文件名匹配，含 / 的按"相对根目录的路径"匹配。
DEFAULT_IGNORE = (
    ".git", ".svn", ".hg",
    "__pycache__", "*.py[cod]", "*.pyd",
    "node_modules", "bower_components",
    "venv", ".venv", "virtualenv", "env", ".env",
    "dist", "build", "out", "target", "bin", "obj",
    ".idea", ".vscode", ".vs", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".ipynb_checkpoints", ".DS_Store", "Thumbs.db", "desktop.ini",
    "*.log", "*.tmp", "*.bak", "*.swp", "*.swo", "*.crdownload", "*.part",
)


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #

def _norm(path) -> str:
    """统一成可比对的绝对路径串（Windows 下忽略大小写与分隔符差异）。"""
    return os.path.normcase(os.path.abspath(str(path)))


def format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    size = float(n)
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024.0
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
    return f"{size:.1f} TB"


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _setup_console() -> None:
    """避免在 cp936 控制台 / 重定向时因 emoji 触发 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


# --------------------------------------------------------------------------- #
# 配置 / 统计
# --------------------------------------------------------------------------- #

class Options:
    """扫描、忽略与渲染规则。"""

    def __init__(self, *, root: Path, ignore_paths=(), ignore_patterns=(),
                 show_hidden: bool = False, max_depth: int | None = None,
                 max_entries: int = 20000, collapse_depth: int = 2,
                 refresh: int = 0):
        self.root_str = str(root)
        self._root_norm = _norm(root)
        self._exact = {_norm(p) for p in ignore_paths}

        patterns = []
        for raw in ignore_patterns:
            pat = raw.strip().replace("\\", "/").lower()
            if pat:
                patterns.append((pat, "/" in pat))
        self._patterns = patterns

        self.show_hidden = show_hidden
        self.max_depth = max_depth
        self.max_entries = max(1, int(max_entries))
        self.collapse_depth = int(collapse_depth)
        self.refresh = max(0, int(refresh))

    def is_expanded(self, depth: int) -> bool:
        """depth 0 = 根目录的直接子项。负值表示全部展开。"""
        return self.collapse_depth < 0 or depth < self.collapse_depth

    def is_ignored(self, entry: os.DirEntry) -> bool:
        if os.path.normcase(entry.path) in self._exact:
            return True
        name = entry.name
        if not self.show_hidden and name.startswith("."):
            return True
        lowered = name.lower()
        for pat, has_sep in self._patterns:
            if has_sep:
                rel = os.path.relpath(entry.path, self.root_str).replace("\\", "/")
                if fnmatch.fnmatchcase(rel.lower(), pat):
                    return True
            elif fnmatch.fnmatchcase(lowered, pat):
                return True
        return False


class Stats:
    __slots__ = ("dirs", "files", "size", "shown", "truncated")

    def __init__(self):
        self.dirs = 0
        self.files = 0
        self.size = 0
        self.shown = 0
        self.truncated = False


# --------------------------------------------------------------------------- #
# 扫描 / 渲染
# --------------------------------------------------------------------------- #

def _sort_key(entry: os.DirEntry) -> tuple:
    try:
        is_dir = entry.is_dir(follow_symlinks=False)
    except OSError:
        is_dir = False
    return (not is_dir, entry.name.lower())


def _size_txt(nbytes: int, complete: bool) -> str:
    """目录体积文案。

    * 统计完整 → 直接给数值；
    * 被截断但已统计到一部分 → 加 ≥，避免读成全量；
    * 完全没统计到（如超出 --max-depth，连子项都没扫） → 用 —，不要写"≥ 0 B"。
    """
    if complete:
        return format_size(nbytes)
    return f"≥ {format_size(nbytes)}" if nbytes > 0 else "—"


def render_dir(dir_path: Path, opts: Options, stats: Stats, depth: int,
               rel: str = "") -> tuple[str, int, int, bool]:
    """返回 (该目录的 HTML, 直接子项数, 递归总字节数, 体积是否统计完整)。

    子项数与体积只有渲染完子目录才知道，所以由递归返回值向上累加。
    """
    if opts.max_depth is not None and depth > opts.max_depth:
        return '<div class="truncated">…（超出最大深度，已省略）</div>', 0, 0, False

    try:
        with os.scandir(dir_path) as it:
            entries = [e for e in it if not opts.is_ignored(e)]
    except OSError as exc:
        return f'<div class="err">⚠ 无法读取：{html.escape(str(exc))}</div>', 0, 0, False

    entries.sort(key=_sort_key)
    if not entries:
        return '<div class="empty">（空目录）</div>', 0, 0, True

    open_attr = " open" if opts.is_expanded(depth) else ""
    total = 0
    complete = True
    out = ["<ul>"]
    for entry in entries:
        if stats.shown >= opts.max_entries:
            stats.truncated = True
            complete = False
            out.append('<li class="truncated">…（条目过多，已截断）</li>')
            break
        stats.shown += 1

        name = html.escape(entry.name)
        child_rel = f"{rel}/{entry.name}" if rel else entry.name
        try:
            is_dir = entry.is_dir(follow_symlinks=False)
            is_link = entry.is_symlink()
        except OSError:
            is_dir = is_link = False

        if is_dir:
            stats.dirs += 1
            children, kids, dsize, dok = render_dir(
                Path(entry.path), opts, stats, depth + 1, child_rel
            )
            total += dsize
            complete = complete and dok
            out.append(
                f'<li class="dir"><details{open_attr} data-p="{html.escape(child_rel)}">'
                '<summary>'
                '<span class="caret"></span>'
                '<span class="ico">📁</span>'
                f'<span class="name">{name}/</span>'
                f'<span class="count">{kids} 项</span>'
                f'<span class="size">{_size_txt(dsize, dok)}</span>'
                f"</summary>{children}</details></li>"
            )
            continue

        if is_link:
            icon, size_txt, size_cls = "🔗", "链接", "size link"
        else:
            icon = get_file_icon(entry.name)
            size_cls = "size"
            try:
                size = entry.stat(follow_symlinks=False).st_size
                stats.size += size
                total += size
                size_txt = format_size(size)
            except OSError:
                complete = False
                size_txt = "—"
        stats.files += 1
        out.append(
            '<li class="file">'
            f'<span class="row" data-p="{html.escape(child_rel)}">'
            f'<span class="ico">{icon}</span>'
            f'<span class="name">{name}</span>'
            f'<span class="{size_cls}">{size_txt}</span>'
            "</span></li>"
        )
    out.append("</ul>")
    return "".join(out), len(entries), total, complete


_asset_cache: dict = {}


def load_assets() -> tuple[str, str]:
    """读取 templates/ 下的外壳与样式；按 mtime 失效，监控期间改 CSS 可即时生效。"""
    files = (TEMPLATE_DIR / "tree.html", TEMPLATE_DIR / "tree.css")
    stamps = tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in files)
    if _asset_cache.get("stamps") != stamps:
        _asset_cache["stamps"] = stamps
        _asset_cache["html"] = files[0].read_text(encoding="utf-8")
        _asset_cache["css"] = files[1].read_text(encoding="utf-8")
    return _asset_cache["html"], _asset_cache["css"]


def generate_html(root: Path, opts: Options) -> tuple[str, str]:
    """返回 (完整 HTML, body 片段)。

    body 不含时间戳与耗时，用作「内容是否真的变了」的判定依据。
    """
    tpl, css = load_assets()

    t0 = time.perf_counter()
    stats = Stats()
    body, _, _, _ = render_dir(root, opts, stats, 0)
    elapsed = (time.perf_counter() - t0) * 1000.0

    name = root.name or str(root)
    ge = "≥" if stats.truncated else ""
    refresh_tag = (
        f'<meta http-equiv="refresh" content="{opts.refresh}">\n'
        if opts.refresh > 0
        else ""
    )

    # BODY 最后替换：文件名里若出现 {{STATS}} 之类字样也不会被二次替换。
    doc = (
        tpl.replace("{{REFRESH}}", refresh_tag)
        .replace("{{CSS}}", css)
        .replace("{{TITLE}}", html.escape(f"{name} 目录结构"))
        .replace("{{NAME}}", html.escape(name))
        .replace("{{PATH}}", html.escape(str(root)))
        .replace("{{NDIRS}}", str(stats.dirs))
        .replace("{{NFILES}}", str(stats.files))
        .replace("{{TSIZE}}", format_size(stats.size))
        .replace("{{MS}}", f"{elapsed:.0f}")
        .replace("{{TIME}}", time.strftime("%Y-%m-%d %H:%M:%S"))
        .replace("{{GE}}", ge)
        .replace("{{TRUNC_ATTR}}", "" if stats.truncated else "hidden")
        .replace("{{BODY}}", body)
    )
    return doc, body


# --------------------------------------------------------------------------- #
# 写盘（原子替换 + 占用重试）
# --------------------------------------------------------------------------- #

def write_atomic(doc: str, tmp: Path, output: Path, *, attempts: int = 3) -> None:
    """写临时文件后 os.replace 原子替换；被占用时退避重试（Windows 上编辑器会持锁）。

    失败时保留 tmp（同进程下次写会直接覆盖），不删除任何已有文件。
    """
    delay = 0.15
    last: BaseException | None = None
    for i in range(max(1, attempts)):
        try:
            tmp.write_text(doc, encoding="utf-8")
            os.replace(tmp, output)
            return
        except PermissionError as exc:  # 目标被占用
            last = exc
            if i + 1 < attempts:
                time.sleep(delay)
                delay *= 2
    raise last if last is not None else OSError(f"写入失败：{output}")


# --------------------------------------------------------------------------- #
# 监控
# --------------------------------------------------------------------------- #

class TreeWatcher(FileSystemEventHandler):
    """尾部防抖 + 串行重建。

    * 尾部防抖：连续变动合并成一次重建；
    * max_wait 上限：即使事件一直不停（大目录拷贝/解压），也保证每 max_wait 秒至少重建一次，
      否则纯尾部防抖会被"饿死"，整批操作期间页面一直不更新；
    * 串行：同一时刻只允许一个重建在跑，避免两个线程同时写 tmp 产出损坏的 HTML；
    * 丢弃「目录被修改」事件：watchdog 在 Windows 上订阅了 LAST_ACCESS 等属性变更，
      而扫描目录本身就会刷新访问时间，只凭这类事件会导致"扫描 -> 事件 -> 再扫描"的自激循环。
      真正的增删改名都会各自产生 created / deleted / moved / modified(文件) 事件，不受影响。
    """

    def __init__(self, regenerate, ignore_paths=(), delay: float = 0.4,
                 max_wait: float = 5.0, max_retries: int = 12, trace: bool = False):
        super().__init__()
        self._regenerate = regenerate
        self._ignore = {_norm(p) for p in ignore_paths}
        self._delay = max(0.0, float(delay))
        self._max_wait = max(self._delay, float(max_wait))
        self._max_retries = max(0, int(max_retries))
        self._trace = trace
        self._retry_left = self._max_retries
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._batch_start: float | None = None
        self._busy = False
        self._pending = False

    def on_any_event(self, event):
        # 目录的「修改」事件（含 LAST_ACCESS / 属性变更）一律丢弃，避免扫描自触发
        if event.is_directory and event.event_type == "modified":
            return

        seen = [
            p for p in (getattr(event, "src_path", None),
                        getattr(event, "dest_path", None)) if p
        ]
        # 自己写输出文件 / .tmp 产生的事件全部忽略
        if seen and all(_norm(p) in self._ignore for p in seen):
            return

        if self._trace:
            print(f"[EVT] {event.event_type:9} dir={event.is_directory} "
                  f"{getattr(event, 'src_path', '')}"
                  f"{' -> ' + event.dest_path if getattr(event, 'dest_path', '') else ''}",
                  flush=True)
        self._schedule()

    def _schedule(self):
        now = time.monotonic()
        with self._lock:
            if self._batch_start is None:
                self._batch_start = now
            wait = min(self._delay, max(0.0, self._max_wait - (now - self._batch_start)))
            if self._timer is not None:
                self._timer.cancel()
            timer = threading.Timer(wait, self._fire)
            timer.daemon = True
            self._timer = timer
            timer.start()

    def _fire(self):
        with self._lock:
            self._timer = None
            self._batch_start = None
            if self._busy:          # 已有构建在跑：记一笔，跑完再补一次
                self._pending = True
                return
            self._busy = True
        retry = False
        ok = True
        try:
            while True:
                # regenerate 约定：返回 False = 本次失败（可自动重试），内部已捕获异常
                try:
                    ok = self._regenerate() is not False
                except Exception:   # 兜底：绝不让监控线程因异常而静默退出
                    traceback.print_exc()
                    ok = False
                with self._lock:
                    if not self._pending:
                        break
                    self._pending = False
        finally:
            with self._lock:
                self._busy = False
                retry, self._pending = self._pending, False
                if ok:
                    self._retry_left = self._max_retries
                elif not retry and self._retry_left > 0:
                    self._retry_left -= 1
                    retry = True
        if retry:
            self._schedule()


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="生成文件夹结构 HTML，并用 watchdog 监控变化自动重新生成。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("folder", nargs="?", default=".", help="要展示 / 监控的文件夹")
    parser.add_argument("-o", "--output",
                        help="输出 HTML 路径（默认落在被扫描目录内：<目录>/<目录名>_structure.html）")
    parser.add_argument("--no-watch", action="store_true", help="只生成一次，不启动监控")
    parser.add_argument("--delay", type=float, default=0.4,
                        help="防抖延迟（秒），连续变动会合并成一次重新生成")
    parser.add_argument("--max-wait", type=float, default=5.0, metavar="SEC",
                        help="变动持续不停时，最长多久强制重建一次（避免大目录拷贝期间页面一直不更新）")
    parser.add_argument("--show-hidden", action="store_true", help="包含隐藏文件/目录（点开头）")
    parser.add_argument("--ignore", action="append", default=[], metavar="PATTERN",
                        help='额外忽略项，支持通配符，可重复：--ignore "*.log" --ignore "build/*"')
    parser.add_argument("--no-default-ignore", action="store_true",
                        help="不使用内置忽略表（.git / __pycache__ / node_modules 等）")
    parser.add_argument("--max-depth", type=int, default=None,
                        help="最大递归深度（0 = 只列根目录的直接子项）")
    parser.add_argument("--max-entries", type=int, default=20000, help="最多渲染多少条目")
    parser.add_argument("--collapse-depth", type=int, default=2, metavar="N",
                        help="默认展开的层数（0 = 全部折叠，-1 = 全部展开）")
    parser.add_argument("--refresh", type=int, default=0, metavar="SEC",
                        help="给 HTML 加 <meta refresh>，浏览器每 SEC 秒重载（0=关闭）")
    parser.add_argument("--trace", action="store_true",
                        help="打印每条会触发重建的文件系统事件（排查「一直更新」用）")
    return parser


def main(argv=None) -> int:
    _setup_console()
    args = _build_parser().parse_args(argv)

    if _WATCHDOG_ERROR is not None and not args.no_watch:
        print(f"❌ 缺少依赖 watchdog（{_WATCHDOG_ERROR}），请先执行:  pip install watchdog",
              file=sys.stderr)
        print("   说明：--no-watch 模式不需要 watchdog。", file=sys.stderr)
        return 3

    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        print(f"❌ 不是文件夹：{root}", file=sys.stderr)
        return 2

    if args.output:
        output = Path(args.output).expanduser().resolve()
    else:
        # 默认落在被扫描目录内
        output = root / f"{root.name or 'root'}_structure.html"
    if output == root:
        print(f"❌ 输出路径不能是目录本身：{output}", file=sys.stderr)
        return 2

    # tmp 名带 pid：同一目录被多个实例同时生成时互不覆盖
    tmp = output.with_name(f".{output.name}.{os.getpid()}.tmp")

    patterns = list(args.ignore)
    if not args.no_default_ignore:
        patterns = list(DEFAULT_IGNORE) + patterns

    opts = Options(
        root=root,
        ignore_paths=(output, tmp),
        ignore_patterns=patterns,
        show_hidden=args.show_hidden,
        max_depth=args.max_depth,
        max_entries=args.max_entries,
        collapse_depth=args.collapse_depth,
        refresh=max(0, args.refresh),
    )

    try:
        load_assets()
    except OSError as exc:
        print(f"❌ 读取模板失败（{TEMPLATE_DIR}）：{exc}", file=sys.stderr)
        return 4

    state: dict = {"body": None}

    def build() -> bool:
        """渲染并写盘。返回 False 表示目录内容与上次完全相同、未写盘。"""
        doc, body = generate_html(root, opts)
        if body == state["body"]:
            return False            # 无实质变化：不写盘，既省 IO 也切断自触发环
        write_atomic(doc, tmp, output)
        state["body"] = body
        return True

    failures = 0

    def safe_build() -> bool:
        """监控期间的构建：失败只告警不中断，且避免反复刷堆栈。返回是否成功。"""
        nonlocal failures
        try:
            wrote = build()
        except PermissionError as exc:
            failures += 1
            if failures == 1:
                _log(f"⚠ 无法写入 {output}（可能被其他程序占用）：{exc}")
                _log("  将自动退避重试；若长期失败，请关闭占用该文件的编辑器/预览面板。")
            return False
        except Exception:
            failures += 1
            if failures == 1:
                traceback.print_exc()
                _log("  （后续同类错误不再打印堆栈）")
            return False
        if not wrote:
            return True             # 内容没变（可能只是被忽略的变动），不必提示
        if failures:
            _log(f"✅ 已恢复正常更新：{output}")
        else:
            _log(f"✅ 已更新：{output}")
        failures = 0
        return True

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"❌ 无法创建输出目录 {output.parent}：{exc}", file=sys.stderr)
        return 1

    # 信号处理尽早注册：首次生成期间收到 Ctrl+C 也能走干净退出路径
    stop = threading.Event()

    def _on_signal(signum, _frame):
        stop.set()

    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _on_signal)
        except (ValueError, OSError):  # 非主线程 / 平台不支持
            pass

    observer = None
    watcher = None
    if not args.no_watch:
        # 先启动监控再首次生成，避免"启动瞬间的改动"被漏掉
        watcher = TreeWatcher(safe_build, ignore_paths=(output, tmp),
                              delay=args.delay, max_wait=args.max_wait,
                              trace=args.trace)
        observer = Observer()
        observer.schedule(watcher, str(root), recursive=True)
        observer.start()

    try:
        build()
    except Exception as exc:
        if observer is not None:
            observer.stop()
            observer.join(timeout=5)
        print(f"❌ 生成失败：{exc}", file=sys.stderr)
        if isinstance(exc, PermissionError):
            print(f"   目标文件可能被占用，请关闭后重试：{output}", file=sys.stderr)
        return 1

    _log(f"✅ 已生成：{output}")
    if observer is None:
        return 0

    hints = "（Ctrl+C 退出）"
    if opts.refresh == 0:
        hints = "（Ctrl+C 退出；浏览器需按 F5 手动刷新，或加 --refresh N 自动重载）"
    _log(f"👀 正在监控：{root} {hints}")

    try:
        while not stop.wait(0.5):
            pass
    except KeyboardInterrupt:
        pass

    _log("⏹ 停止监控…")
    observer.stop()
    observer.join(timeout=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())

'''
入口：CLI 参数解析 + watchdog 监控 + 模式分发
'''

import sys
import time
import signal
import argparse
from pathlib import Path

from tree import IGNORE_PATTERNS, load_ignore_file, generate_project_tree
from gui import main as gui_main


def watch_and_regenerate(start_path: str, ignore_patterns: list,
                         ignore_deep: list = None, ignore_shallow: list = None,
                         output_path: str = None):
    """
    监控目录变化，自动重新生成目录树。
    output_path: 若提供，每次重新生成后自动写入该文件
    """
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

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


def main_cli():
    """命令行模式入口"""
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
            gui_main()
        except Exception as e:
            print(f"❌ 程序运行失败：{str(e)}", file=sys.stderr)
            sys.exit(1)
    else:
        # 有参数：命令行模式
        root_path = Path(args.root).resolve()
        if not root_path.is_dir():
            print(f"错误：路径不存在或不是目录 - {root_path}", file=sys.stderr)
            sys.exit(1)

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
            sys.exit(1)


if __name__ == "__main__":
    main_cli()

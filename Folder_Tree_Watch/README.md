# Folder Tree Watch

把文件夹结构渲染成一个可折叠的 HTML，并在文件变动时自动重建。

## 功能

- **可折叠目录树**：`<details>/<summary>` 实现，不依赖 JS 也能展开/折叠
- **监控模式**：文件变动后自动重建（尾部防抖 + 最长等待，避免大目录拷贝期间页面一直不更新）
- **体积显示**：文件夹右侧显示该目录整体占用（递归累加），文件右侧显示自身大小
- **搜索筛选**：`/` 聚焦搜索框，`Esc` 清空，命中项自动展开祖先路径
- **全展开 / 全折叠**、折叠状态记忆（`sessionStorage`，按根目录路径为键；刷新后可恢复，关闭标签页即清空）
- **按扩展名显示图标**、**深浅双主题**（跟随系统设置）
- **右键复制路径**：绝对路径进剪贴板，粘贴到资源管理器地址栏即可跳转
- **忽略规则支持通配符**：`*.pyc`、`build/*`，可重复传 `--ignore`

## 依赖

- Python 3.9+（实测 3.11.14）
- `watchdog` —— 仅监控模式需要，`--no-watch` 不需要

```bash
pip install watchdog
```

## 用法

```bash
python folder_tree_watch.py                          # 当前目录，产物写在 <目录>/<目录名>_structure.html
python folder_tree_watch.py D:\my_project            # 指定目录
python folder_tree_watch.py . --no-watch             # 只生成一次，不监控
python folder_tree_watch.py . -o out/tree.html       # 自定义输出路径
python folder_tree_watch.py . --collapse-depth -1    # 默认全部展开
python folder_tree_watch.py . --ignore "*.log"       # 额外忽略
```

启动后打印产物路径；监控模式下按 `Ctrl+C` 退出。

## 主要参数

| 参数 | 说明 |
|---|---|
| `folder` | 要展示/监控的目录，默认 `.` |
| `-o, --output` | 输出路径，默认落在被扫描目录内 |
| `--no-watch` | 只生成一次 |
| `--delay` | 防抖延迟秒数（默认 0.4） |
| `--max-wait` | 变动不停时的最长等待，强制重建一次（默认 5.0） |
| `--ignore` | 额外忽略，支持通配符，可重复 |
| `--no-default-ignore` | 关闭内置忽略表 |
| `--show-hidden` | 包含隐藏项（点开头） |
| `--max-depth` | 最大递归深度，`0` = 只列根目录直接子项 |
| `--max-entries` | 最多渲染条目数（默认 20000） |
| `--collapse-depth` | 默认展开层数（`0` 全折叠，`-1` 全展开，默认 2） |
| `--refresh` | 给 HTML 加 `<meta refresh>`，每 N 秒整页重载 |
| `--trace` | 打印真正触发重建的事件，排查「一直更新」用 |

完整列表见 `python folder_tree_watch.py --help`。

## 目录约定

```
Folder_Tree_Watch/
├── folder_tree_watch.py     主脚本
├── icons.py                 扩展名 → 图标（纯数据）
└── templates/
    ├── tree.html            HTML 外壳 + 前端脚本
    └── tree.css             全部样式
```

`templates/` 必须与脚本同目录，否则报「读取模板失败」；改样式不必动主脚本，监控模式下改完即生效（按文件 mtime 失效缓存）。

## 忽略规则与体积语义

- 默认忽略表包含 `.git`、`__pycache__`、`node_modules`、`venv`、`dist`、`target`、`*.pyc`、`*.log` 等，用 `--no-default-ignore` 可整体关闭。
- **被忽略的条目不计入文件夹体积**，所以数字可能比资源管理器里看到的略小；想与资源管理器一致就加 `--no-default-ignore`。
- 输出文件及其 `.tmp` 中间文件会被自动排除在扫描和监控之外，避免「写 HTML → 触发事件 → 再写 HTML」的自激循环。
- 被 `--max-depth` / `--max-entries` 截断时：统计值前加 `≥`，完全没统计到的目录体积显示 `—`。

## 开机自启监控模式

想让某个目录的 HTML 始终跟着变，可以把它挂到用户的「启动」目录，登录后在后台静默运行（无窗口）。

**1. 新建一个 `.vbs`**，内容如下（路径按实际情况替换）：

```vbs
Set WshShell = CreateObject("WScript.Shell")

cmd = "cmd /c " & _
      "chcp 65001 >nul && " & _
      "D: && " & _
      "cd /d ""<本仓库目录>"" && " & _
      "call conda activate <环境名> && " & _
      "python ""Folder_Tree_Watch\folder_tree_watch.py"" " & _
      """<被监控目录>"" " & _
      "-o ""<输出 HTML 路径>"" " & _
      "--delay 0.6 " & _
      ">> ""<日志路径>"" 2>&1"

WshShell.Run cmd, 0, False
```

**2. 放进启动目录**：`Win+R` → 输入 `shell:startup` → 回车，把 `.vbs` 放进去。下次登录即自动运行；想让它立刻跑一次，双击即可。

**3. 容易踩的坑**：

- **编码建议存成 ANSI(GBK)、不要带 BOM**。WSH 对没有 BOM 的 `.vbs` 会按系统 ANSI 代码页解析，若文件是 UTF-8，中文路径可能会变成乱码（`数据库` → `鏁版嵁搴�`），脚本随即静默失败。用 VS Code 编辑时要在右下角手动选 `GB2312/GBK` 保存，别用默认的 UTF-8。但是经实测发现 UTF-8 也可以正常工作。
- **`WshShell.Run cmd, 0, False` 的 `0` 是隐藏窗口**，出错也看不到。所以示例里加了 `>> 日志 2>&1`；确认稳定后可以去掉这个重定向，否则日志会一直追加。
- **输出 HTML 不要落在被监控目录内**（或让它与其它监控工具互相 `--ignore`），否则会与别的监控工具互相触发，见下面的「常见问题」。
- 若不想依赖 `conda activate`，可把 `call conda activate <环境名> && python` 换成环境里 `python.exe` 的绝对路径，如 `""D:\Miniconda\envs\<环境名>\python.exe""`。

**停止自启**：任务管理器结束对应的 `python.exe` 进程即可停当前实例；要永久停用就把 `.vbs` 移出启动目录（对下次登录生效）。

## 常见问题

- **无法写入输出文件**：说明 HTML 被别的程序占着（编辑器、预览面板）。脚本会自动退避重试，失败只告警一次；解锁后即使没有新事件也会自愈。
- **页面「一直更新」**：先看是否有另一个程序在写被监控目录——典型情况是另一个监控工具把产物也写进了同一个目录，两个实例互相触发。用 `--trace` 可打印真正触发重建的事件；也可用 `--ignore` 互相排除对方产物。
- **退出码**：`0` 成功、`1` 生成失败、`2` 目录或输出路径非法、`3` 缺少 watchdog、`4` 模板读取失败。

## 与 Export_Directory_Structure 的关系

两者互相独立、不共享代码：[Export_Directory_Structure](../Export_Directory_Structure)工具输出 `.txt` 目录树，本工具输出可交互的 HTML 并支持监控。可以同时使用，但注意**不要让两者的产物都落在同一个被监控目录内**（见上面的「一直更新」），或者让两者相互忽略对方的产物（用 `--ignore`）。

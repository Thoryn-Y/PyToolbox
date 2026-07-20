# 目录结构导出工具 (Export Directory Structure)

带有 GUI 界面的项目目录结构生成器，支持文件图标、忽略规则、自动监控。

---

# 运行方式

## GUI 模式

```
python main.py
```
无参数运行即打开 GUI 界面。

1. 点击「浏览」选择要扫描的项目目录
2. 在忽略规则文本框中编辑排除项（每行一个，支持 `*` 通配符）
3. 勾选「保存到文件」可指定输出路径（文件夹或完整文件路径均可）
4. 点击「生成目录结构」，结果输出到控制台，若勾选保存则同时写入文件

---

## 命令行模式

通过参数直接进入命令行模式，适合 bat 脚本或开机自启。

### 参数说明

| 参数 | 说明 | 是否必须 |
|------|------|----------|
| `-r` / `--root` | 要扫描的目标目录路径 | 是（不指定则进入 GUI） |
| `-o` / `--output` | 输出文件路径 | 否（默认保存到目标目录下的 `{目录名}_目录结构.txt`） |
| `-w` / `--watch` | 启用文件监控，变动时自动重新生成 | 否 |

### 使用示例

```bat
REM 一次性生成
python main.py -r D:\my_project

REM 指定输出路径
python main.py -r D:\my_project -o D:\output\目录树.txt

REM 生成并持续监控（文件变动自动更新，Ctrl+C 停止）
python main.py -r D:\my_project -w

REM 完整组合
python main.py -r D:\my_project -o D:\output\目录树.txt -w
```

> 使用 `-w` 监控功能需要先安装 watchdog：`pip install watchdog`

---

## 开机自启监控模式

通过 VBS 脚本实现开机后自动启动监控，全程无窗口运行。

### 创建 VBS 文件

**文件内容**（名字随意）：

```vbs
Set WshShell = CreateObject("WScript.Shell")

cmd = "cmd /c " & _
      "chcp 65001 >nul && " & _
      "D: && " & _
      "cd /d ""D:\path\to\PyToolbox"" && " & _
      "call conda activate your_environment_name && " & _
      "python ""Export_Directory_Structure\main.py"" -r ""D:\path\to\target"" -w"

WshShell.Run cmd, 0, False

Set WshShell = Nothing
```

### 关键操作步骤

| 步骤 | 操作 |
|-----|------|
| 1. 创建文件 | 复制代码到记事本 |
| 2. **编码设置** | **另存为 → 编码选"ANSI"**（UTF-8 会导致 VBS 编译错误），并把文件名中的文件后缀从txt改为vbs |
| 3. 保存位置 | 按 `Win + R` 输入 `shell:startup`，将 `.vbs` 文件放入该文件夹 |
| 4. 完成 | 重启测试，脚本后台静默运行，无窗口弹出 |

### 核心要点

| 要点 | 说明 |
|-----|------|
| **为什么用 VBS 而不是 BAT** | VBS 默认无窗口运行，能创建隐藏 CMD 进程执行命令 |
| **`WshShell.Run` 参数** | `0` = 完全隐藏窗口，`False` = 异步执行不等待 |
| **`""` 转义** | VBS 字符串内表示一个双引号字符 |
| **`&&` 连接** | 前一条命令成功后才执行下一条 |
| **文件编码必须用 ANSI** | UTF-8 会导致错误 |

---

# 忽略规则

脚本有两层忽略机制，**叠加生效，互不影响**：

## 1. 全局忽略规则（IGNORE_PATTERNS）

内置于脚本中，排除 `.git`、`__pycache__`、`node_modules` 等通用目录/文件。GUI 模式下可在文本框中实时修改。

## 2. 目标目录忽略文件（.autosummaryignore）

在被扫描的**目标目录根下**放置 `.autosummaryignore` 文件，实现按项目独立配置的排除规则。

**规则格式：**

```
# 完全排除 —— 目录或文件本身及子内容全部不显示（直接写名称）
.git
__pycache__
.DS_Store
thumbs.db

# 浅排除 —— 目录名保留显示，但不展开子内容（名称末尾加 /  (... 内容已折叠)）
logs/
temp/
node_modules/
```

- **完全排除**：匹配到的文件或目录直接从树中移除
- **浅排除**：仅对目录生效，目录条目会显示在树中并标注 `(... 内容已折叠)`，但不递归进入其子内容

若目标目录下没有 `.autosummaryignore` 文件，此功能静默失效，不影响正常使用。

---

# 输出示例

```
📂 my_project (完整路径: D:\my_project)
├── 📂 src/
│   ├── 🐍 main.py
│   ├── 🐍 utils.py
│   └── 📂 config/
│       └── 📋 settings.yaml
├── 📂 logs/  (... 内容已折叠)
│   
├── 📄 README.md
└── 📋 requirements.txt
```

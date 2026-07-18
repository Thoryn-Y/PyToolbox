# 目录结构导出工具 (Export Directory Structure)

带有 GUI 界面的项目目录结构生成器，支持文件图标、忽略规则、自动监控。

---

## 运行方式

```
python Export_Directory_Structure.py
```

无参数运行即打开 GUI 界面。

---

## GUI 模式

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
python Export_Directory_Structure.py -r D:\my_project

REM 指定输出路径
python Export_Directory_Structure.py -r D:\my_project -o D:\output\目录树.txt

REM 生成并持续监控（文件变动自动更新，Ctrl+C 停止）
python Export_Directory_Structure.py -r D:\my_project -w

REM 完整组合
python Export_Directory_Structure.py -r D:\my_project -o D:\output\目录树.txt -w
```

> 使用 `-w` 监控功能需要先安装 watchdog：`pip install watchdog`

---

## 忽略规则

脚本有两层忽略机制，**叠加生效，互不影响**：

### 1. 全局忽略规则（IGNORE_PATTERNS）

内置于脚本中，排除 `.git`、`__pycache__`、`node_modules` 等通用目录/文件。GUI 模式下可在文本框中实时修改。

### 2. 目标目录忽略文件（.autosummaryignore）

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

## 输出示例

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

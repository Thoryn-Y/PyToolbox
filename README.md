# PyToolbox

<div align="center">
  <p>
    <a href="README.en.md" target="_blank" rel="noopener noreferrer">
      <img src="https://img.shields.io/badge/Language-English-green.svg" alt="English Version"></a>
  </p>
  <p>
    <a href="README.md" target="_blank" rel="noopener noreferrer">
      <img src="https://img.shields.io/badge/Language-Chinese-blue.svg" alt="Chinese Version"></a>
  </p>
  <br>
</div>

包含一些python脚本，处理一些有些麻烦的、可能需要重复做的小事。

## Annotation_Deleter

Python 注释删除工具。通过 GUI 选择一个 `.py` 文件，自动在原文件同目录下生成一份去除了所有注释的副本（`{原文件名}_no_annotation.py`），原文件不会被修改。

**特点：**
- 使用状态机区分字符串内外的 `#`，不会误删字符串中的 `#` 字符
- 支持删除单独成行的注释和行内注释
- 副本已存在时会弹窗询问是否覆盖

## Bilibili_Bullet_Screen_Analysis

B站弹幕解析工具。读取 B 站导出的 XML 弹幕文件，解析每条弹幕的时间、类型、颜色、发送者等信息，输出 Excel 分析表（含用户行为统计）并生成时间分布直方图和类型占比饼图。

**特点：**
- 支持过滤短弹幕、可配置是否生成图表
- 自动按用户维度统计发送数量、活跃时长和高频词汇
- 结果保存为多 Sheet 的 Excel 文件，方便进一步分析
- 需要结合B站弹幕导出工具使用

## Code_Function_Call_Analyzer

Python 函数调用关系分析工具。通过 GUI 选择一个项目文件夹，使用 AST 解析提取所有 `.py` 文件中的函数定义与调用关系，生成有向调用关系图（PNG），帮助快速理解代码结构。

**特点：**
- 支持普通函数、异步函数和类方法的调用关系提取
- 自动排除 `venv`、`__pycache__`、`.git` 等无关目录
- 结果图保存至 `result/` 文件夹，文件名取自项目文件夹名

## Code_Line_Count_Statistics

代码行数统计工具。通过 GUI 选择一个项目文件夹，统计各语言文件的总行数、有效代码行数、注释行数和空行数，输出 Excel 报告（含文件明细、语言小计、综合统计）和可视化饼图。

**特点：**
- 支持 20+ 种编程语言（Python、C/C++、Java、Go、Rust 等），自动识别注释规则
- 自动排除 `venv`、`node_modules`、`.git` 等无关目录
- 结果按项目文件夹名分子目录保存至 `result/`

## Password_Generator

密码生成器。根据配置的字符类型和长度批量生成随机密码，并对每个密码进行强度评估（弱/中/强/极强），给出详细分析反馈。

**特点：**
- 支持 5 种字符类型可选组合（大小写、数字、基本标点、扩展特殊字符）
- 强度评估考虑长度、字符多样性、分布均匀度、连续字符和常见模式
- 配置集中在脚本底部，修改方便

## Sync_Folders（当前仍有问题，不可用）

目录同步工具。将源目录同步到目标目录，使其内容完全一致。支持指定不同步的文件或目录，基于哈希校验判断文件是否相同，仅复制有差异的文件。

**特点：**
- 支持多种哈希算法（MD5/SHA1/SHA256）和大文件并行处理
- 逐项确认删除目标目录中多余的文件，防止误删
- 带进度条显示同步状态，支持符号链接处理

## Word_and_PDF_format_conversion

Word/PDF 转 Markdown 工具。将 `.docx` 或 `.pdf` 文件转换为 Markdown 格式，自动提取图片并以图注命名，保留标题层级、正文段落和表格。

**特点：**
- 同时支持 Word 和 PDF 两种输入格式
- 图片自动提取并以图注（小标题）命名，无图注时自动编号
- 提供 GUI 界面和命令行两种使用方式

## File_Operation_Class

文件内容拆分工具。通过命令行按比例随机拆分文件内容，适合拆分数据集 txt 文件。拆分后原文件保留剩余内容，指定比例的内容写入新文件。

**特点：**
- 支持命令行参数或交互式输入，灵活配置拆分比例和随机种子
- 使用固定随机种子可复现拆分结果
- 自动创建输出目录，覆盖前会提示确认

## Export_Directory_Structure

项目目录结构导出工具。通过 GUI 选择项目文件夹，递归遍历目录树并生成带文件类型图标的目录结构文本，支持自定义忽略规则，可输出到控制台或保存为文本文件。

**特点：**
- 内置丰富的文件类型图标映射，目录结构一目了然
- 支持自定义忽略规则（每行一条，支持通配符）
- 可选保存到 `result/` 目录或直接输出到控制台

## Code_Relationship_Analyzer

Python 代码关系分析工具。通过 GUI 选择一个项目文件夹，使用 AST 解析提取函数调用关系、类继承关系和导入关系，生成函数调用关系图、类继承关系图（PNG）以及分析摘要文本文件。

**特点：**
- 同时分析函数调用、类继承、模块导入三类关系
- 自动排除 `venv`、`node_modules`、`.git` 等无关目录
- 结果按项目文件夹名分子目录保存至 `result/`

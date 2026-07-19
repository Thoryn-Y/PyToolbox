# PyToolbox

<div align="center">
  <p>
    [中文](README.md) | [English](README.en.md)
  </p>
</div>

A collection of Python scripts for handling small but tedious tasks that may need to be repeated.

## Annotation_Deleter

Python comment deletion tool. Select a `.py` file via GUI to automatically generate a copy without all comments in the same directory as the original file (`{original_filename}_no_annotation.py`). The original file remains unchanged.

**Features:**
- Uses a state machine to distinguish `#` inside strings from outside, preventing accidental deletion of `#` characters in strings
- Supports deleting standalone comments and inline comments
- Prompts to overwrite if the copy already exists

## Bilibili_Bullet_Screen_Analysis

Bilibili danmaku analysis tool. Reads exported XML danmaku files from Bilibili, parses each danmaku's time, type, color, sender, and other information, outputs Excel analysis sheets (including user behavior statistics) and generates time distribution histograms and type proportion pie charts.

**Features:**
- Supports filtering short danmaku and configurable chart generation
- Automatically counts messages per user, active duration, and high-frequency words
- Results saved as multi-sheet Excel files for further analysis
- Requires use of Bilibili danmaku export tool

## Code_Function_Call_Analyzer

Python function call relationship analysis tool. Select a project folder via GUI to extract all function definitions and call relationships from `.py` files using AST parsing, generating directed call relationship graphs (PNG) to help quickly understand code structure.

**Features:**
- Supports extracting call relationships for regular functions, async functions, and class methods
- Automatically excludes irrelevant directories like `venv`, `__pycache__`, `.git`
- Results saved in `result/` folder with filename derived from the project folder name

## Code_Line_Count_Statistics

Code line count statistics tool. Select a project folder via GUI to count total lines, effective code lines, comment lines, and blank lines for each language file, output Excel reports (including file details, language subtotals, comprehensive statistics) and visualization pie charts.

**Features:**
- Supports 20+ programming languages (Python, C/C++, Java, Go, Rust, etc.) with automatic comment rule recognition
- Automatically excludes irrelevant directories like `venv`, `node_modules`, `.git`
- Results saved in `result/` folder organized by project folder name

## Password_Generator

Password generator. Batch generate random passwords based on configured character types and length, and perform strength assessment (weak/medium/strong/very strong) for each password with detailed analysis feedback.

**Features:**
- Supports 5 character type combinations (uppercase, lowercase, numbers, basic punctuation, extended special characters)
- Strength assessment considers length, character diversity, distribution uniformity, consecutive characters, and common patterns
- Configuration centralized at the bottom of the script for easy modification

## Sync_Folders (Currently has issues, not usable)

Directory synchronization tool. Synchronizes source directory to target directory to make their contents identical. Supports specifying files or directories to exclude, uses hash verification to determine if files are the same, and only copies files with differences.

**Features:**
- Supports multiple hash algorithms (MD5/SHA1/SHA256) and parallel processing of large files
- Prompts to confirm deletion of extra files in the target directory one by one to prevent accidental deletion
- Displays synchronization status with progress bar, supports symbolic link handling

## Word_and_PDF_format_conversion

Word/PDF to Markdown conversion tool. Converts `.docx` or `.pdf` files to Markdown format, automatically extracts images and names them with captions, preserves heading hierarchy, body paragraphs, and tables.

**Features:**
- Supports both Word and PDF input formats
- Images automatically extracted and named with captions (subtitles), auto-numbered if no caption
- Provides both GUI interface and command-line usage modes

## File_Operation_Class

File content splitting tool. Splits file content by ratio via command line, suitable for splitting dataset txt files. After splitting, the original file retains the remaining content, and the specified proportion of content is written to a new file.

**Features:**
- Supports command-line arguments or interactive input, flexible configuration of split ratio and random seed
- Fixed random seed for reproducible split results
- Automatically creates output directory, prompts for confirmation before overwriting

## Export_Directory_Structure

Project directory structure export tool. Select a project folder via GUI to recursively traverse the directory tree and generate directory structure text with file type icons, supports custom ignore rules, can output to console or save as text file.

**Features:**
- Built-in rich file type icon mapping for clear directory structure
- Supports custom ignore rules (one rule per line, supports wildcards)
- Optional save to `result/` directory or direct output to console

## Code_Relationship_Analyzer

Python code relationship analysis tool. Select a project folder via GUI to extract function call relationships, class inheritance relationships, and import relationships using AST parsing, generating function call relationship graphs, class inheritance relationship graphs (PNG), and analysis summary text files.

**Features:**
- Analyzes three types of relationships: function calls, class inheritance, and module imports
- Automatically excludes irrelevant directories like `venv`, `node_modules`, `.git`
- Results saved in `result/` folder organized by project folder name

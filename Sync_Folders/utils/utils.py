#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块，包含通用的辅助函数
"""

import os
import fnmatch

# 尝试导入 unicodedata 来处理字符串宽度计算
try:
    import unicodedata
    def str_display_width(text):
        """
        计算字符串在终端中的显示宽度，正确处理中英文字符
        
        Args:
            text (str): 要计算宽度的字符串
            
        Returns:
            int: 字符串在终端中的显示宽度
        """
        width = 0
        for char in text:
            # 获取字符的东亚宽度属性
            eaw = unicodedata.east_asian_width(char)
            # F(全宽)、W(宽)、A(模糊)字符宽度为2，其他为1
            if eaw in ('F', 'W', 'A'):
                width += 2
            else:
                width += 1
        return width
except ImportError:
    # 如果无法导入 unicodedata，回退到简单计算方法
    def str_display_width(text):
        """
        计算字符串在终端中的显示宽度（简化版）
        
        Args:
            text (str): 要计算宽度的字符串
            
        Returns:
            int: 字符串在终端中的显示宽度
        """
        # 简单估算：假设非ASCII字符（可能包括中文）占2个字符宽度
        width = 0
        for char in text:
            if ord(char) < 128:  # ASCII字符
                width += 1
            else:  # 非ASCII字符，可能是中文或其他多字节字符
                width += 2
        return width


# ANSI颜色代码类，用于在终端中输出彩色文本
class Colors:
    HEADER = '\033[95m'     # 紫色
    OKBLUE = '\033[94m'     # 蓝色
    OKCYAN = '\033[96m'     # 青色
    OKGREEN = '\033[92m'    # 绿色
    WARNING = '\033[93m'    # 黄色
    FAIL = '\033[91m'       # 红色
    ENDC = '\033[0m'        # 结束颜色
    BOLD = '\033[1m'        # 粗体
    UNDERLINE = '\033[4m'   # 下划线


def print_colored(text, color_code, **kwargs):
    """
    打印彩色文本，支持传递额外参数给print函数
    
    Args:
        text (str): 要打印的文本
        color_code (str): 颜色代码
        **kwargs: 传递给print函数的额外参数
    """
    print(f"{color_code}{text}{Colors.ENDC}", **kwargs)


def matches_any_pattern(item_path, patterns, base_path):
    """
    检查路径是否匹配任何排除模式
    
    Args:
        item_path (str): 要检查的文件或目录路径
        patterns (list): 排除模式列表
        base_path (str): 基准路径，用于计算相对路径
        
    Returns:
        bool: 如果路径匹配任何排除模式返回True，否则返回False
    """
    # 计算相对于基路径的相对路径，便于模式匹配
    try:
        rel_item_path = os.path.relpath(item_path, base_path)
    except ValueError:
        # 当两个路径没有共同祖先时（比如不同的驱动器），使用绝对路径
        rel_item_path = item_path
    
    # 处理相对路径开头的 './'
    if rel_item_path.startswith('./'):
        rel_item_path = rel_item_path[2:]
    elif rel_item_path.startswith('.\\'):  # Windows风格
        rel_item_path = rel_item_path[2:]
        
    # 也生成绝对路径用于匹配
    abs_item_path = os.path.abspath(item_path)
    
    # 规范化路径分隔符（处理Windows和Unix系统差异）
    rel_item_path_normalized = rel_item_path.replace('\\', '/')
    abs_item_path_normalized = abs_item_path.replace('\\', '/')
    
    # 获取文件或目录名
    basename = os.path.basename(item_path)

    for pattern in patterns:
        # 移除模式两端的空白字符
        pattern = pattern.strip()
        
        # 规范化模式中的路径分隔符
        pattern_normalized = pattern.replace('\\', '/')
        
        # 特殊处理目录模式（以/结尾的模式）
        is_dir_pattern = pattern.endswith('/')
        if is_dir_pattern:
            # 检查是否匹配目录（不带/的模式也能匹配目录）
            pattern = pattern.rstrip('/')
            pattern_normalized = pattern_normalized.rstrip('/')
            
        # 支持多种匹配方式：
        # 1. 相对路径匹配
        # 2. 绝对路径匹配
        # 3. 文件名/目录名匹配
        # 4. 相对路径标准化后匹配
        # 5. 绝对路径标准化后匹配
        if (fnmatch.fnmatch(rel_item_path, pattern) or 
            fnmatch.fnmatch(abs_item_path, pattern) or 
            fnmatch.fnmatch(basename, pattern) or
            fnmatch.fnmatch(rel_item_path_normalized, pattern_normalized) or
            fnmatch.fnmatch(abs_item_path_normalized, pattern_normalized)):
            return True
            
        # 如果是目录模式，还要检查目录情况
        if is_dir_pattern and os.path.isdir(item_path):
            # 检查目录的各种路径形式是否匹配
            dir_patterns = [pattern, pattern + '/', pattern_normalized, pattern_normalized + '/']
            rel_patterns = [rel_item_path, rel_item_path + '/', rel_item_path_normalized, rel_item_path_normalized + '/']
            abs_patterns = [abs_item_path, abs_item_path + '/', abs_item_path_normalized, abs_item_path_normalized + '/']
            
            for dir_p in dir_patterns:
                for rel_p in rel_patterns:
                    if fnmatch.fnmatch(rel_p, dir_p):
                        return True
                for abs_p in abs_patterns:
                    if fnmatch.fnmatch(abs_p, dir_p):
                        return True
                         
    return False

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件操作模块，负责文件复制、删除和符号链接处理等功能
"""

import os
import shutil

from utils.utils import print_colored, Colors
from core.hashing import get_file_hash


def copy_file_with_hash_check(src, dst, algorithm):
    """
    带哈希校验的文件复制函数
    
    Args:
        src (str): 源文件路径
        dst (str): 目标文件路径
        algorithm (str): 哈希算法
        
    Returns:
        tuple: (success, copied) 其中 success 表示操作是否成功，
               copied 表示是否实际执行了复制操作
    """
    src_hash = get_file_hash(src, algorithm)
    if src_hash is None:
        return (False, False)  # 无法计算源文件哈希

    # 检查目标文件是否存在且哈希相同
    if os.path.exists(dst):
        dst_hash = get_file_hash(dst, algorithm)
        if dst_hash is not None and src_hash == dst_hash:
            # 文件相同，无需复制
            return (True, False)

    # 文件不同或目标不存在，需要复制
    # 确保目标目录存在
    dst_dir = os.path.dirname(dst)
    if dst_dir and not os.path.exists(dst_dir):
        try:
            os.makedirs(dst_dir)
        except OSError as e:
            print_colored(f"警告: 无法创建目录 '{dst_dir}': {e}", Colors.WARNING)
            return (False, False)

    try:
        shutil.copy2(src, dst)  # copy2 保留元数据
    except Exception as e:
        print_colored(f"警告: 无法复制文件 '{src}' 到 '{dst}': {e}", Colors.WARNING)
        return (False, False)
    return (True, True)


def create_symlink(target, link_path):
    """
    创建符号链接
    
    Args:
        target (str): 符号链接的目标路径
        link_path (str): 符号链接的路径
        
    Returns:
        bool: 创建成功返回True，否则返回False
    """
    # 确保链接所在目录存在
    link_dir = os.path.dirname(link_path)
    if link_dir and not os.path.exists(link_dir):
        try:
            os.makedirs(link_dir)
        except OSError as e:
            print_colored(f"警告: 无法创建目录 '{link_dir}' 用于符号链接: {e}", Colors.WARNING)
            return False
            
    # 如果链接已存在，先删除
    if os.path.lexists(link_path):  # lexists 可以检测到 broken links
        try:
            if os.path.islink(link_path) or os.path.isfile(link_path):
                os.remove(link_path)
            elif os.path.isdir(link_path):
                shutil.rmtree(link_path)
        except Exception as e:
            print_colored(f"警告: 无法删除现有的链接或文件 '{link_path}': {e}", Colors.WARNING)
            return False
    
    try:
        os.symlink(target, link_path)
    except Exception as e:
        print_colored(f"警告: 无法创建符号链接 '{link_path}' -> '{target}': {e}", Colors.WARNING)
        return False
    return True


def copy_symbolic_link(src_link, dst_link):
    """
    复制符号链接
    
    Args:
        src_link (str): 源符号链接路径
        dst_link (str): 目标符号链接路径
        
    Returns:
        bool: 复制成功返回True，否则返回False
    """
    try:
        # 读取源符号链接的目标路径
        target = os.readlink(src_link)
        # 创建目标符号链接
        return create_symlink(target, dst_link)
    except Exception as e:
        print_colored(f"警告: 无法复制符号链接 '{src_link}' -> '{dst_link}': {e}", Colors.WARNING)
        return False


def files_are_identical(src, dst, algorithm):
    """
    检查两个文件内容是否相同
    
    Args:
        src (str): 源文件路径
        dst (str): 目标文件路径
        algorithm (str): 哈希算法
        
    Returns:
        bool: 如果文件内容相同返回True，否则返回False
    """
    # 如果目标文件不存在，则文件不相同
    if not os.path.exists(dst):
        return False
    
    # 计算源文件哈希
    src_hash = get_file_hash(src, algorithm)
    if src_hash is None:
        return False  # 无法计算源文件哈希
    
    # 计算目标文件哈希
    dst_hash = get_file_hash(dst, algorithm)
    if dst_hash is None:
        return False  # 无法计算目标文件哈希
    
    # 比较哈希值
    return src_hash == dst_hash


def delete_item(item_path):
    """
    删除文件或目录
    
    Args:
        item_path (str): 要删除的文件或目录路径
        
    Returns:
        bool: 删除成功返回True，否则返回False
    """
    try:
        if os.path.isfile(item_path) or os.path.islink(item_path):
            os.remove(item_path)
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)
        return True
    except Exception as e:
        print_colored(f"警告: 无法删除项目 '{item_path}': {e}", Colors.WARNING)
        return False

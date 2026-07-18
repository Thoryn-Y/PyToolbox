#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
目录操作模块，负责目录比较、文件收集和递归计数等功能
"""

import os
from tqdm import tqdm

from utils.utils import print_colored, Colors, matches_any_pattern
from core.hashing import calculate_hashes_in_parallel
from core.file_operations import files_are_identical
from core.file_operations import copy_file_with_hash_check, create_symlink, copy_symbolic_link


def dirs_are_identical(src, dst, algorithm, excludes=None):
    """
    检查两个目录内容是否相同（递归比较所有文件）
    
    Args:
        src (str): 源目录路径
        dst (str): 目标目录路径
        algorithm (str): 哈希算法
        excludes (list, optional): 排除模式列表
        
    Returns:
        bool: 如果目录内容相同返回True，否则返回False
    """
    # 如果目标目录不存在，则目录不相同
    if not os.path.exists(dst):
        return False
    
    # 如果源目录不存在，则目录不相同
    if not os.path.exists(src):
        return False
    
    # 获取源目录中的所有项目
    try:
        src_items = set(os.listdir(src))
    except PermissionError:
        return False  # 无法访问源目录
    
    # 获取目标目录中的所有项目
    try:
        dst_items = set(os.listdir(dst))
    except PermissionError:
        return False  # 无法访问目标目录
    
    # 应用排除规则到源目录项目
    if excludes:
        filtered_src_items = set()
        for item in src_items:
            item_full_path = os.path.join(src, item)
            # 只有未被排除的项目才加入filtered_src_items
            if not matches_any_pattern(item_full_path, excludes, src):
                filtered_src_items.add(item)
        src_items = filtered_src_items
    
    # 应用排除规则到目标目录项目
    if excludes:
        filtered_dst_items = set()
        for item in dst_items:
            item_full_path = os.path.join(dst, item)
            # 只有未被排除的项目才加入filtered_dst_items
            if not matches_any_pattern(item_full_path, excludes, dst):
                filtered_dst_items.add(item)
        dst_items = filtered_dst_items
    
    # 检查项目列表是否相同
    if src_items != dst_items:
        return False
    
    # 分离文件和目录，分别处理
    src_files = []
    dst_files = []
    subdirs = []
    symlinks = []
    
    for item in src_items:
        src_item_path = os.path.join(src, item)
        dst_item_path = os.path.join(dst, item)
        
        if os.path.isfile(src_item_path) and os.path.isfile(dst_item_path):
            # 收集文件路径对
            src_files.append(src_item_path)
            dst_files.append(dst_item_path)
        elif os.path.isdir(src_item_path) and os.path.isdir(dst_item_path):
            # 收集子目录对
            subdirs.append((src_item_path, dst_item_path))
        elif os.path.islink(src_item_path) and os.path.islink(dst_item_path):
            # 收集符号链接对
            symlinks.append((src_item_path, dst_item_path))
        else:
            # 项目类型不同
            return False
    
    # 处理符号链接
    for src_link, dst_link in symlinks:
        try:
            src_link_target = os.readlink(src_link)
            dst_link_target = os.readlink(dst_link)
            if src_link_target != dst_link_target:
                return False
        except:
            return False
    
    # 并行处理文件比较
    if src_files:
        # 收集所有需要计算哈希的文件
        all_files = src_files + dst_files
        # 并行计算所有文件的哈希值
        file_hashes = calculate_hashes_in_parallel(all_files, algorithm)
        
        # 比较源文件和目标文件的哈希值
        for src_file, dst_file in zip(src_files, dst_files):
            src_hash = file_hashes.get(src_file)
            dst_hash = file_hashes.get(dst_file)
            if src_hash is None or dst_hash is None or src_hash != dst_hash:
                return False
    
    # 处理子目录（递归）
    for src_subdir, dst_subdir in subdirs:
        if not dirs_are_identical(src_subdir, dst_subdir, algorithm, excludes):
            return False
    
    return True


def count_items_recursively(src, excludes):
    """
    递归计算源目录中需要复制的总项目数（文件+目录），考虑排除规则
    
    Args:
        src (str): 源目录路径
        excludes (list): 排除模式列表
        
    Returns:
        int: 需要复制的总项目数
    """
    total = 0
    try:
        # 获取源目录中的项目
        items = os.listdir(src)
    except PermissionError:
        print_colored(f"警告: 无法列出源目录 '{src}' 的内容 (权限不足)", Colors.WARNING)
        return total
    except Exception as e:
        print_colored(f"警告: 计算源目录项目总数时出错: {e}", Colors.WARNING)
        return total
    
    # 应用排除规则
    if excludes:
        filtered_items = []
        for item in items:
            item_full_path = os.path.join(src, item)
            if not matches_any_pattern(item_full_path, excludes, src):
                filtered_items.append(item)
        items = filtered_items
    
    # 遍历每个项目
    for item in items:
        item_path = os.path.join(src, item)
        
        # 增加当前项目的计数
        total += 1
        
        # 如果是目录，递归计算其子项目数
        if os.path.isdir(item_path):
            total += count_items_recursively(item_path, excludes)
    
    return total


def copytree_with_progress_and_links(src, dst, pbar, excludes, algorithm, follow_symlinks=False, src_base=None, dst_base=None):
    """
    带进度条、排除、哈希校验和符号链接处理的 copytree 辅助函数
    
    Args:
        src (str): 源目录路径
        dst (str): 目标目录路径
        pbar (tqdm): 进度条对象
        excludes (list): 排除模式列表
        algorithm (str): 哈希算法
        follow_symlinks (bool): 是否跟随符号链接
        src_base (str): 源目录的根路径，用于计算相对路径进行排除匹配
        dst_base (str): 目录的根路径，用于计算相对路径进行排除匹配
    """
    # 初始化 src_base 和 dst_base (在顶层调用时)
    if src_base is None:
        src_base = src
    if dst_base is None:
        dst_base = dst

    # 检查当前目录是否被排除
    if excludes and matches_any_pattern(src, excludes, src_base):
        # 如果当前目录被排除，则跳过整个目录树
        try:
            # 计算需要跳过的项目数以更新进度条
            total_skipped = 0
            for root, dirs, files in os.walk(src):
                total_skipped += len(dirs) + len(files)
                # 应用排除规则到子目录
                dirs[:] = [d for d in dirs if not matches_any_pattern(os.path.join(root, d), excludes, src_base)]
            pbar.update(min(total_skipped, pbar.total - pbar.n))  # 避免超出总进度
        except:
            pass  # 忽略统计错误
        return True

    if not os.path.exists(dst):
        try:
            os.makedirs(dst)
            pbar.update(1) # 更新目录创建
        except OSError as e:
            print_colored(f"警告: 无法创建目录 '{dst}': {e}", Colors.WARNING)
            return False

    try:
        items = os.listdir(src)
    except PermissionError:
        print_colored(f"警告: 无法列出目录 '{src}' 的内容 (权限不足)", Colors.WARNING)
        return

    # 应用排除规则到当前 src 目录下的 items
    if excludes:
        # 过滤 items 列表，移除被排除的项
        original_items = items[:]
        items = []
        for item in original_items:
            item_full_path = os.path.join(src, item)
            # 使用 src_base 进行匹配
            if not matches_any_pattern(item_full_path, excludes, src_base):
                items.append(item)
            else:
                # 对于被排除的项，也需要更新进度条（假装处理过了）
                pbar.update(1)
                # 如果是目录，还需要更新其内部所有项的进度
                if os.path.isdir(item_full_path):
                     # 递归计算子项数并更新进度条
                     try:
                         total_subitems = 0
                         for root, dirs, files in os.walk(item_full_path):
                             total_subitems += len(dirs) + len(files)
                             # 对子目录也应用排除规则
                             dirs[:] = [d for d in dirs if not matches_any_pattern(os.path.join(root, d), excludes, src_base)]
                         pbar.update(min(total_subitems, pbar.total - pbar.n))
                     except:
                         pass  # 忽略统计错误

    for item in items:
        s = os.path.join(src, item)
        d = os.path.join(dst, item)

        # 检查是否为符号链接
        if os.path.islink(s):
            if not follow_symlinks:
                # 复制符号链接本身
                link_target = os.readlink(s)
                if not create_symlink(link_target, d):
                    print_colored(f"警告: 未能正确创建符号链接 {d}", Colors.WARNING)
                pbar.update(1)
            else:
                # 跟随符号链接（如果它指向目录或文件，会按下面的逻辑处理）
                # os.path.isdir / isfile 会跟随链接
                pass # 继续执行下面的 isdir/isfile 检查

        if os.path.isdir(s) and not (not follow_symlinks and os.path.islink(s)):
            # 递归调用时传递 src_base 和 dst_base
            copytree_with_progress_and_links(s, d, pbar, excludes, algorithm, follow_symlinks, src_base, dst_base)
        elif os.path.isfile(s) and not (not follow_symlinks and os.path.islink(s)):
            success, copied = copy_file_with_hash_check(s, d, algorithm)
            if copied and pbar:
                pbar.update(1)
            elif not success:
                # 即使复制失败，也要更新进度条以避免卡住
                if pbar:
                    pbar.update(1)
        # 如果是链接且 follow_symlinks=False，已经在上面处理过了


def collect_sync_items(src, dst, excludes):
    """
    收集需要同步的项目列表
    
    Args:
        src (str): 源目录路径
        dst (str): 目标目录路径
        excludes (list): 排除模式列表
        
    Returns:
        tuple: (items_to_copy, items_to_delete)
            items_to_copy: 需要复制或更新的项目列表
            items_to_delete: 需要删除的项目列表
    """
    items_to_copy = []
    items_to_delete = []
    
    # 获取源目录中的所有项目
    try:
        src_items = os.listdir(src)
    except PermissionError:
        print_colored(f"警告: 无法列出源目录 '{src}' 的内容 (权限不足)", Colors.WARNING)
        return items_to_copy, items_to_delete
    
    # 获取目标目录中的所有项目
    try:
        dst_items = os.listdir(dst) if os.path.exists(dst) else []
    except PermissionError:
        print_colored(f"警告: 无法列出目标目录 '{dst}' 的内容 (权限不足)", Colors.WARNING)
        return items_to_copy, items_to_delete
    
    # 应用排除规则到源目录项目
    if excludes:
        filtered_src_items = []
        for item in src_items:
            item_full_path = os.path.join(src, item)
            if not matches_any_pattern(item_full_path, excludes, src):
                filtered_src_items.append(item)
        src_items = filtered_src_items
    
    # 应用排除规则到目标目录项目
    if excludes:
        filtered_dst_items = []
        for item in dst_items:
            item_full_path = os.path.join(dst, item)
            if not matches_any_pattern(item_full_path, excludes, dst):
                filtered_dst_items.append(item)
        dst_items = filtered_dst_items
    
    # 收集需要复制或更新的项目
    for item in src_items:
        src_item_path = os.path.join(src, item)
        dst_item_path = os.path.join(dst, item)
        
        if not os.path.exists(dst_item_path):
            # 目标项目不存在，需要复制
            items_to_copy.append((src_item_path, dst_item_path, os.path.isdir(src_item_path)))
        elif os.path.isfile(src_item_path) and os.path.isfile(dst_item_path):
            # 都是文件，可能需要更新
            items_to_copy.append((src_item_path, dst_item_path, False))
        elif os.path.isdir(src_item_path) and os.path.isdir(dst_item_path):
            # 都是目录，递归处理
            sub_items_to_copy, sub_items_to_delete = collect_sync_items(src_item_path, dst_item_path, excludes)
            items_to_copy.extend(sub_items_to_copy)
            items_to_delete.extend(sub_items_to_delete)
    
    # 收集需要删除的项目
    for item in dst_items:
        src_item_path = os.path.join(src, item)
        dst_item_path = os.path.join(dst, item)
        
        if not os.path.exists(src_item_path):
            # 源项目不存在，需要删除
            items_to_delete.append((dst_item_path, os.path.isdir(dst_item_path)))
    
    return items_to_copy, items_to_delete

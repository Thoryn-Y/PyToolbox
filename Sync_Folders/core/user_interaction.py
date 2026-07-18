#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户交互模块，负责处理用户输入和交互逻辑
"""

import os

from utils.utils import print_colored, Colors


def get_user_input_path(prompt):
    """
    获取用户输入的路径，并进行基本验证
    
    Args:
        prompt (str): 提示信息
        
    Returns:
        str: 验证通过的绝对路径
    """
    while True:
        path = input(prompt).strip()
        if not path:
            print_colored("路径不能为空，请重新输入。", Colors.WARNING)
            continue
        # 尝试获取绝对路径
        try:
            abs_path = os.path.abspath(path)
        except Exception as e:
            print_colored(f"路径格式错误: {e}", Colors.FAIL)
            continue
            
        # 检查路径是否存在（对于源路径）或父目录是否存在（对于目标路径）
        if "源" in prompt:  # 源文件夹路径
            if not os.path.exists(abs_path):
                print_colored(f"错误: 源目录 '{abs_path}' 不存在。", Colors.FAIL)
                continue
            if not os.path.isdir(abs_path):
                print_colored(f"错误: '{abs_path}' 不是一个有效的目录。", Colors.FAIL)
                continue
        else:  # 目标文件夹路径
            parent_dir = os.path.dirname(abs_path)
            if parent_dir and not os.path.exists(parent_dir):
                print_colored(f"错误: 目标目录的父目录 '{parent_dir}' 不存在。", Colors.FAIL)
                continue
                
        return abs_path


def confirm_recursive_deletion(folder_path):
    """
    递归确认文件夹内的文件和子文件夹是否需要删除
    
    Args:
        folder_path (str): 文件夹路径
        
    Returns:
        set: 包含确认删除的项目路径
    """
    confirmed_items = set()
    
    try:
        # 获取文件夹内容
        items = os.listdir(folder_path)
        if not items:
            return confirmed_items
            
        # 询问用户如何处理文件夹内容
        while True:
            choice = input(f"对于文件夹 '{folder_path}' 内容的处理方式 ([Y/y]全部删除 / [N/n]逐个确认): ").strip().lower()
            if choice in ('y', 'yes'):
                # 确认删除文件夹内所有内容
                for item in items:
                    item_path = os.path.join(folder_path, item)
                    confirmed_items.add(item_path)
                break
            elif choice in ('n', 'no'):
                # 逐个确认删除
                for item in items:
                    item_path = os.path.join(folder_path, item)
                    # 检查是否是文件夹
                    if os.path.isdir(item_path):
                        # 对于子文件夹，递归调用确认删除流程
                        print_colored(f"检测到 '{item_path}' 是一个文件夹。", Colors.WARNING)
                        recursive_items = confirm_recursive_deletion(item_path)
                        confirmed_items.update(recursive_items)
                    else:
                        # 对于文件，直接确认是否删除
                        while True:
                            confirm = input(f"是否删除 '{item_path}'? (y/[n]): ").strip().lower()
                            if confirm in ('y', 'yes'):
                                confirmed_items.add(item_path)
                                break
                            elif confirm in ('n', '', 'no'):
                                break
                            else:
                                print_colored("无效输入，请输入 y 或 n。", Colors.WARNING)
                break
            else:
                print_colored("无效输入，请输入 Y/y 或 N/n。", Colors.WARNING)
                
        return confirmed_items
    except Exception as e:
        print_colored(f"处理文件夹 '{folder_path}' 时出错: {e}", Colors.FAIL)
        return confirmed_items


def confirm_deletion(item_path):
    """
    确认是否删除单个项目，如果是文件夹且用户选择不删除，则进一步确认是否删除其内容
    
    Args:
        item_path (str): 项目路径
        
    Returns:
        tuple: (should_delete_item: bool, recursive_confirmed_items: set)
    """
    while True:
        confirm = input(f"是否删除 '{item_path}'? (y/[n]): ").strip().lower()
        if confirm in ('y', 'yes'):
            # 用户确认删除该项目
            return True, set()
        elif confirm in ('n', '', 'no'):
            # 用户不删除该项目
            # 检查是否是文件夹
            if os.path.isdir(item_path):
                # 对于文件夹，询问是否删除其内容
                print_colored(f"检测到 '{item_path}' 是一个文件夹。", Colors.WARNING)
                recursive_items = confirm_recursive_deletion(item_path)
                return False, recursive_items
            else:
                # 对于文件，直接返回不删除
                return False, set()
        else:
            print_colored("无效输入，请输入 y 或 n。", Colors.WARNING)


def manage_excludes(common_excludes):
    """
    管理排除项列表，允许用户添加或删除排除项
    
    Args:
        common_excludes (list): 初始排除项列表
        
    Returns:
        list: 更新后的排除项列表
    """
    excludes = common_excludes.copy()
    
    # 显示当前排除项列表
    print("\n当前排除项列表:")
    for idx, exclude in enumerate(excludes):
        print(f"  {idx}: {exclude}")
    
    # 询问用户是否修改排除项
    modify_excludes = input("\n是否修改排除项？(Y/N): ").strip().lower()
    if modify_excludes not in ('y', 'yes'):
        return excludes
    
    # 询问操作类型
    while True:
        action = input("请选择操作类型 (A或a-添加/R或r-减少): ").strip().lower()
        if action in ('a', 'add'):
            # 添加排除项
            print("\n添加排除项（输入空行或N/n停止）:")
            while True:
                new_exclude = input("输入新的排除项: ").strip()
                if not new_exclude or new_exclude.lower() in ('n', 'no'):
                    break
                if new_exclude not in excludes:
                    excludes.append(new_exclude)
                    print_colored(f"已添加: {new_exclude}", Colors.OKGREEN)
                else:
                    print_colored(f"排除项 '{new_exclude}' 已存在", Colors.WARNING)
            break
        elif action in ('r', 'remove'):
            # 移除排除项
            print("\n移除排除项（输入序号，多个序号用英文逗号隔开）:")
            remove_input = input("输入要删除的排除项序号: ").strip()
            if remove_input:
                try:
                    # 解析输入的序号列表
                    indices = [int(idx.strip()) for idx in remove_input.split(',')]
                    # 按从大到小排序，避免删除前面的元素影响后面的索引
                    indices.sort(reverse=True)
                    
                    # 移除指定索引的排除项
                    for idx in indices:
                        if 0 <= idx < len(excludes):
                            removed = excludes.pop(idx)
                            print_colored(f"已移除: {removed}", Colors.OKGREEN)
                        else:
                            print_colored(f"无效序号: {idx}", Colors.WARNING)
                except ValueError:
                    print_colored("输入格式错误，请输入数字序号", Colors.FAIL)
            break
        else:
            print_colored("无效操作类型，请输入 A/a 或 R/r", Colors.WARNING)
    
    # 显示更新后的排除项列表
    print("\n更新后的排除项列表:")
    for idx, exclude in enumerate(excludes):
        print(f"  {idx}: {exclude}")
    
    return excludes

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync_Folders 主程序入口
将源目录同步到目标目录，保持内容完全一致
"""

import os
import sys
import shutil
from tqdm import tqdm

from utils.utils import print_colored, Colors, matches_any_pattern
from core.config import ConfigManager
from core.performance import PerformanceMonitor
from core.user_interaction import get_user_input_path, confirm_deletion, manage_excludes
from core.directory import (
    dirs_are_identical, count_items_recursively, 
    copytree_with_progress_and_links, collect_sync_items
)
from core.file_operations import copy_file_with_hash_check, copy_symbolic_link, delete_item


def preview_sync_info(src, dst, excludes):
    """
    预览同步信息，显示需要复制和删除的项目
    
    Args:
        src (str): 源目录路径
        dst (str): 目标目录路径
        excludes (list): 排除模式列表
        
    Returns:
        tuple: (items_to_copy_len, items_to_delete_len)
            items_to_copy_len: 需要复制的项目数量
            items_to_delete_len: 需要删除的项目数量
    """
    print_colored("\n=== 同步预览 ===", Colors.HEADER)
    print(f"源目录: {src}")
    print(f"目标目录: {dst}")
    
    # 收集同步项目
    items_to_copy, items_to_delete = collect_sync_items(src, dst, excludes)
    
    # 统计数量
    items_to_copy_len = len(items_to_copy)
    items_to_delete_len = len(items_to_delete)
    
    # 显示需要复制的项目
    if items_to_copy_len > 0:
        print_colored(f"\n需要复制或更新的项目 ({items_to_copy_len} 项):", Colors.OKGREEN)
        # 只显示前10项
        for i, (src_item, dst_item, is_dir) in enumerate(items_to_copy[:10]):
            item_type = "[目录]" if is_dir else "[文件]"
            rel_path = os.path.relpath(src_item, src)
            print(f"  {item_type} {rel_path}")
        if items_to_copy_len > 10:
            print(f"  ... 还有 {items_to_copy_len - 10} 项未显示")
    else:
        print_colored("\n没有需要复制或更新的项目", Colors.OKGREEN)
    
    # 显示需要删除的项目
    if items_to_delete_len > 0:
        print_colored(f"\n需要删除的项目 ({items_to_delete_len} 项):", Colors.FAIL)
        # 只显示前10项
        for i, (dst_item, is_dir) in enumerate(items_to_delete[:10]):
            item_type = "[目录]" if is_dir else "[文件]"
            rel_path = os.path.relpath(dst_item, dst)
            print(f"  {item_type} {rel_path}")
        if items_to_delete_len > 10:
            print(f"  ... 还有 {items_to_delete_len - 10} 项未显示")
    else:
        print_colored("\n没有需要删除的项目", Colors.FAIL)
    
    return items_to_copy_len, items_to_delete_len


def sync_directories(src, dst, excludes, algorithm, follow_symlinks, confirmed_deletions, pbar=None, is_top_level=True, items_to_copy_len=None):
    """
    同步两个目录
    
    Args:
        src (str): 源目录路径
        dst (str): 目标目录路径
        excludes (list): 排除模式列表
        algorithm (str): 哈希算法
        follow_symlinks (bool): 是否跟随符号链接
        confirmed_deletions (dict): 确认删除的项目字典，键为项目路径，值为其确认删除的内容集合
        pbar (tqdm, optional): 进度条对象（仅顶层调用时为None）
        is_top_level (bool): 是否为顶层调用
        items_to_copy_len (int, optional): 预计算的需要复制的项目数量（用于进度条）
        
    Returns:
        bool: 同步是否成功
    """
    try:
        # 确保目标目录存在
        os.makedirs(dst, exist_ok=True)
        
        # 获取源目录中的所有项目
        try:
            src_items = set(os.listdir(src))
        except PermissionError:
            print_colored(f"警告: 无法列出源目录 '{src}' 的内容 (权限不足)", Colors.WARNING)
            return False
        
        # 获取目标目录中的所有项目
        try:
            dst_items = set(os.listdir(dst))
        except PermissionError:
            print_colored(f"警告: 无法列出目标目录 '{dst}' 的内容 (权限不足)", Colors.WARNING)
            return False
        
        # 应用排除规则
        if excludes:
            filtered_src_items = set()
            for item in src_items:
                item_full_path = os.path.join(src, item)
                if not matches_any_pattern(item_full_path, excludes, src):
                    filtered_src_items.add(item)
            src_items = filtered_src_items
        
        # 如果是顶层调用，初始化进度条
        local_pbar = pbar
        if is_top_level and local_pbar is None:
            # 计算总任务数（复制项目数 + 删除项目数）
            if items_to_copy_len is not None:
                # 使用预计算的复制任务数
                total_copy_tasks = items_to_copy_len
            else:
                # 回退到原来的计算方法
                total_copy_tasks = count_items_recursively(src, excludes)
            total_delete_tasks = sum(1 if not recursive_items else len(recursive_items) 
                                    for recursive_items in confirmed_deletions.values())
            total_tasks = total_copy_tasks + total_delete_tasks
            
            # 初始化进度条
            local_pbar = tqdm(total=total_tasks, desc="同步中-准备", unit="项", ncols=100)
        
        # 复制或更新源目录中的项目到目标目录
        for item in src_items:
            src_item_path = os.path.join(src, item)
            dst_item_path = os.path.join(dst, item)
            
            # 更新进度条描述
            if local_pbar:
                local_pbar.set_description("同步中-复制/更新")
            
            # 检查是否应该跳过此项目（基于排除规则）
            if matches_any_pattern(src_item_path, excludes, src):
                if local_pbar:
                    local_pbar.update(1)
                continue
            
            # 处理符号链接
            if os.path.islink(src_item_path):
                if follow_symlinks:
                    # 跟随符号链接，将其视为普通文件或目录
                    if os.path.isdir(src_item_path):
                        # 递归同步目录
                        if not sync_directories(src_item_path, dst_item_path, excludes, algorithm, follow_symlinks, confirmed_deletions, local_pbar, False, items_to_copy_len):
                            # 如果是顶层调用，关闭进度条
                            if is_top_level and local_pbar:
                                # 确保进度条达到100%
                                if local_pbar.n < local_pbar.total:
                                    local_pbar.update(local_pbar.total - local_pbar.n)
                                local_pbar.set_description("同步完成")
                                local_pbar.close()
                            return False
                    else:
                        # 复制文件
                        success, copied = copy_file_with_hash_check(src_item_path, dst_item_path, algorithm)
                        if copied and local_pbar:
                            local_pbar.update(1)
                        elif not success and local_pbar:
                            # 即使复制失败，也要更新进度条以避免卡住
                            local_pbar.update(1)
                else:
                    # 不跟随符号链接，直接复制符号链接本身
                    copy_symbolic_link(src_item_path, dst_item_path)
                    if local_pbar:
                        local_pbar.update(1)
            elif os.path.isdir(src_item_path):
                # 递归同步目录
                if not sync_directories(src_item_path, dst_item_path, excludes, algorithm, follow_symlinks, confirmed_deletions, local_pbar, False, items_to_copy_len):
                    # 如果是顶层调用，关闭进度条
                    if is_top_level and local_pbar:
                        # 确保进度条达到100%
                        if local_pbar.n < local_pbar.total:
                            local_pbar.update(local_pbar.total - local_pbar.n)
                        local_pbar.set_description("同步完成")
                        local_pbar.close()
                    return False
            elif os.path.isfile(src_item_path):
                # 复制文件
                success, copied = copy_file_with_hash_check(src_item_path, dst_item_path, algorithm)
                if copied and local_pbar:
                    local_pbar.update(1)
                elif not success and local_pbar:
                    # 即使复制失败，也要更新进度条以避免卡住
                    local_pbar.update(1)
        
        # 删除用户确认的项目（仅在顶层调用时执行）
        if is_top_level and confirmed_deletions:
            if local_pbar:
                local_pbar.set_description("同步中-删除")
                
            for item_path, recursive_items in confirmed_deletions.items():
                # 检查这是一个完整的项目删除还是部分内容删除
                if not recursive_items:
                    # 完整项目删除
                    try:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            os.remove(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                    except Exception as e:
                        print_colored(f"删除 '{item_path}' 时出错: {e}", Colors.FAIL)
                        if local_pbar:
                            local_pbar.close()
                        return False
                    # 更新进度条
                    if local_pbar:
                        local_pbar.update(1)
                else:
                    # 部分内容删除（仅删除指定的文件/文件夹）
                    for sub_item_path in recursive_items:
                        try:
                            if os.path.isfile(sub_item_path) or os.path.islink(sub_item_path):
                                os.remove(sub_item_path)
                            elif os.path.isdir(sub_item_path):
                                shutil.rmtree(sub_item_path)
                        except Exception as e:
                            print_colored(f"删除 '{sub_item_path}' 时出错: {e}", Colors.FAIL)
                            if local_pbar:
                                local_pbar.close()
                            return False
                        # 更新进度条
                        if local_pbar:
                            local_pbar.update(1)
        
        # 如果是顶层调用，关闭进度条
        if is_top_level and local_pbar:
            # 确保进度条达到100%
            if local_pbar.n < local_pbar.total:
                local_pbar.update(local_pbar.total - local_pbar.n)
            local_pbar.set_description("同步完成")
            local_pbar.close()
        
        return True
    except Exception as e:
        print_colored(f"同步过程中发生错误: {e}", Colors.FAIL)
        return False


def main():
    """
    主程序入口
    """
    print_colored("=== Sync_Folders 目录同步工具 ===", Colors.HEADER)
    
    # 初始化配置管理器
    config_manager = ConfigManager()
    
    try:
        # 获取用户输入的源目录和目标目录
        src = get_user_input_path("请输入源目录路径: ")
        dst = get_user_input_path("请输入目标目录路径: ")
        
        # 获取常见排除项
        common_excludes = config_manager.get_common_excludes()
        
        # 管理排除项
        excludes = manage_excludes(common_excludes)
        
        # 设置默认哈希算法
        default_algorithm = config_manager.get_default_hash_algorithm()
        
        # 初始化性能监控（仅在实际执行计算和同步时计时）
        performance_monitor = PerformanceMonitor()
        
        # 预览同步信息
        performance_monitor.start_program()  # 开始计时
        performance_monitor.start_phase("预览同步信息")
        items_to_copy_len, items_to_delete_len = preview_sync_info(src, dst, excludes)
        performance_monitor.end_phase("预览同步信息")
        
        # 确认是否继续
        print_colored(f"\n总计: {items_to_copy_len} 项需要复制/更新，{items_to_delete_len} 项需要删除", Colors.WARNING)
        if items_to_copy_len == 0 and items_to_delete_len == 0:
            print_colored("源目录和目标目录内容已经完全一致，无需同步。", Colors.OKGREEN)
            performance_monitor.end_program()  # 结束计时
            performance_monitor.print_report()
            return
        
        confirm = input("是否继续执行同步？(Y/[N]): ").strip().lower()
        if confirm not in ('y', 'yes'):
            print_colored("同步已取消。", Colors.WARNING)
            performance_monitor.end_program()  # 结束计时
            performance_monitor.print_report()
            return
        
        # 同步目录
        performance_monitor.start_phase("执行目录同步")
        
        # 收集需要删除的项目
        confirmed_deletions = {}
        if items_to_delete_len > 0:
            # 获取目标目录中的所有项目（已应用排除规则）
            try:
                dst_items = os.listdir(dst) if os.path.exists(dst) else []
                # 应用排除规则
                filtered_dst_items = []
                for item in dst_items:
                    item_full_path = os.path.join(dst, item)
                    if not matches_any_pattern(item_full_path, excludes, dst):
                        filtered_dst_items.append(item)
                dst_items = filtered_dst_items
            except PermissionError:
                print_colored(f"警告: 无法列出目标目录 '{dst}' 的内容 (权限不足)", Colors.WARNING)
                dst_items = []
            
            # 获取源目录中的所有项目（已应用排除规则）
            try:
                src_items = os.listdir(src)
                # 应用排除规则
                filtered_src_items = []
                for item in src_items:
                    item_full_path = os.path.join(src, item)
                    if not matches_any_pattern(item_full_path, excludes, src):
                        filtered_src_items.append(item)
                src_items = filtered_src_items
            except PermissionError:
                print_colored(f"警告: 无法列出源目录 '{src}' 的内容 (权限不足)", Colors.WARNING)
                src_items = []
            
            # 收集需要删除的项目
            for item in dst_items:
                src_item_path = os.path.join(src, item)
                dst_item_path = os.path.join(dst, item)
                if item not in src_items:
                    # 询问是否删除
                    should_delete, recursive_items = confirm_deletion(dst_item_path)
                    if should_delete:
                        confirmed_deletions[dst_item_path] = set()
                    elif recursive_items:
                        confirmed_deletions[dst_item_path] = recursive_items
        
        # 执行同步
        success = sync_directories(
            src, dst, excludes, default_algorithm, 
            follow_symlinks=False, confirmed_deletions=confirmed_deletions,
            items_to_copy_len=items_to_copy_len
        )
        
        performance_monitor.end_phase("执行目录同步")
        
        # 验证同步结果
        performance_monitor.start_phase("验证同步结果")
        if success:
            if dirs_are_identical(src, dst, default_algorithm, excludes):
                print_colored("\n✅ 同步成功！源目录和目标目录内容完全一致。", Colors.OKGREEN)
            else:
                print_colored("\n⚠️  同步完成，但源目录和目标目录内容不一致。可能存在权限问题或被排除的文件。", Colors.WARNING)
        else:
            print_colored("\n❌ 同步失败。", Colors.FAIL)
        performance_monitor.end_phase("验证同步结果")
        
        # 生成性能报告
        performance_monitor.end_program()  # 结束计时
        performance_monitor.print_report()
        
    except KeyboardInterrupt:
        print_colored("\n程序被用户中断。", Colors.WARNING)
    except Exception as e:
        print_colored(f"程序执行过程中发生错误: {e}", Colors.FAIL)
    finally:
        # 确保性能监控器已经结束
        if 'performance_monitor' in locals():
            try:
                performance_monitor.end_program()
            except:
                pass


if __name__ == "__main__":
    main()

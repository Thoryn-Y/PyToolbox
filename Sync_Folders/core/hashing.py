#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
哈希计算模块，负责文件哈希值的计算
"""

import os
import hashlib
from concurrent.futures import ThreadPoolExecutor

from utils.utils import print_colored, Colors
from core.config import ConfigManager
from core.performance import get_available_cpu_cores


config_manager = ConfigManager()


def get_file_hash(file_path, algorithm):
    """
    计算文件的哈希值
    
    Args:
        file_path (str): 文件路径
        algorithm (str): 使用的哈希算法
        
    Returns:
        str: 文件的哈希值，计算失败返回None
    """
    hash_func = hashlib.new(algorithm)
    buffer_size = config_manager.get_buffer_size()
    
    try:
        with open(file_path, 'rb') as f:
            # 使用更大的缓冲区读取文件，提高I/O效率
            for chunk in iter(lambda: f.read(buffer_size), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except Exception as e:
        print_colored(f"警告: 无法读取文件 '{file_path}' 以计算哈希: {e}", Colors.WARNING)
        return None


def calculate_hashes_in_parallel(file_paths, algorithm):
    """
    并行计算多个文件的哈希值，根据文件大小自动选择处理方式
    
    Args:
        file_paths (list): 文件路径列表
        algorithm (str): 使用的哈希算法
        
    Returns:
        dict: 文件名到哈希值的映射
    """
    def calculate_single_hash(file_path):
        """
        计算单个文件的哈希值（内部辅助函数）
        """
        return get_file_hash(file_path, algorithm)
    
    # 结果字典
    file_hashes = {}
    
    if not file_paths:
        return file_hashes
    
    # 获取配置参数
    small_file_threshold = config_manager.get_small_file_threshold()
    
    # 分离小文件和大文件
    small_files = []
    large_files = []
    
    for file_path in file_paths:
        try:
            # 获取文件大小
            file_size = os.path.getsize(file_path)
            
            # 根据文件大小分类
            if file_size < small_file_threshold:
                small_files.append(file_path)
            else:
                large_files.append(file_path)
        except Exception as e:
            print_colored(f"警告: 无法获取文件大小 '{file_path}': {e}", Colors.WARNING)
    
    # 处理小文件：使用单线程处理，减少线程管理开销
    if small_files:
        for file_path in small_files:
            hash_value = get_file_hash(file_path, algorithm)
            if hash_value is not None:
                file_hashes[file_path] = hash_value
    
    # 处理大文件：使用并行处理，提高效率
    if large_files:
        # 获取可用CPU核心数，使用快速模式减少延迟
        available_cores = get_available_cpu_cores(quick_mode=True)
        
        # 使用ThreadPoolExecutor并行计算大文件的哈希值
        with ThreadPoolExecutor(max_workers=available_cores) as executor:
            # 提交所有大文件的哈希计算任务
            results = list(executor.map(calculate_single_hash, large_files))
            
        # 更新结果字典
        for file_path, hash_value in zip(large_files, results):
            if hash_value is not None:
                file_hashes[file_path] = hash_value
    
    return file_hashes

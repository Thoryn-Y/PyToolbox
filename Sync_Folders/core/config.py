#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块，负责加载和解析配置文件
"""

import json
import os

from utils.utils import print_colored, Colors


class ConfigManager:
    """
    配置管理类，用于加载、解析和访问配置文件
    """
    
    def __init__(self, config_path=None):
        """
        初始化配置管理器
        
        Args:
            config_path (str, optional): 配置文件路径
        """
        # 默认配置文件路径
        default_config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
        self.config_path = config_path or default_config_path
        self.config = None
        
        # 加载配置
        self.load_config()
    
    def load_config(self):
        """
        加载配置文件
        
        Raises:
            FileNotFoundError: 如果配置文件不存在
            json.JSONDecodeError: 如果配置文件格式错误
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            print_colored(f"错误: 配置文件 '{self.config_path}' 不存在。", Colors.FAIL)
            raise
        except json.JSONDecodeError as e:
            print_colored(f"错误: 配置文件格式错误: {e}", Colors.FAIL)
            raise
    
    def get_hash_algorithms(self):
        """
        获取支持的哈希算法列表
        
        Returns:
            list: 支持的哈希算法列表
        """
        return self.config.get('hash', {}).get('supported_algorithms', [])
    
    def get_default_hash_algorithm(self):
        """
        获取默认哈希算法
        
        Returns:
            str: 默认哈希算法
        """
        return self.config.get('hash', {}).get('default_algorithm', 'sha256')
    
    def get_max_resource_usage_ratio(self):
        """
        获取最大资源使用率
        
        Returns:
            float: 最大资源使用率
        """
        return self.config.get('resource', {}).get('max_usage_ratio', 0.7)
    
    def get_small_file_threshold(self):
        """
        获取小文件阈值
        
        Returns:
            int: 小文件阈值（字节）
        """
        return self.config.get('file_processing', {}).get('small_file_threshold', 10 * 1024 * 1024)
    
    def get_buffer_size(self):
        """
        获取文件读取缓冲区大小
        
        Returns:
            int: 缓冲区大小（字节）
        """
        return self.config.get('file_processing', {}).get('buffer_size', 256 * 1024)
    
    def get_common_excludes(self):
        """
        获取常见排除项列表
        
        Returns:
            list: 常见排除项列表
        """
        return self.config.get('common_excludes', [])

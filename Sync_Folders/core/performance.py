#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控模块，用于记录和分析程序各阶段的执行时间
"""

import time
import psutil

from utils.utils import print_colored, Colors
from core.config import ConfigManager


config_manager = ConfigManager()


def get_available_cpu_cores(quick_mode=False):
    """
    获取当前可用的CPU核心数，基于系统空闲率
    
    Args:
        quick_mode (bool): 是否使用快速模式，快速模式下使用更短的CPU使用率采样间隔
        
    Returns:
        int: 可用的CPU核心数，不超过系统CPU核心总数的MAX_RESOURCE_USAGE_RATIO
    """
    try:
        # 获取系统CPU使用率（快速模式下使用0.1秒平均，否则使用1秒平均）
        interval = 0.1 if quick_mode else 1
        cpu_percent = psutil.cpu_percent(interval=interval)
        # 获取总CPU核心数
        total_cores = psutil.cpu_count()
        
        # 计算空闲CPU百分比
        idle_percent = 100 - cpu_percent
        
        # 计算可用CPU核心数
        # 基于空闲率计算可用核心数，并限制不超过总核心数的MAX_RESOURCE_USAGE_RATIO
        max_ratio = config_manager.get_max_resource_usage_ratio()
        available_cores = int(total_cores * (idle_percent / 100) * max_ratio)
        
        # 确保至少有1个核心可用
        available_cores = max(available_cores, 1)
        # 同时确保不超过总核心数
        available_cores = min(available_cores, total_cores)
        
        return available_cores
    except Exception as e:
        print_colored(f"警告: 无法获取系统CPU信息: {e}", Colors.WARNING)
        # 发生错误时，返回一个保守值（总核心数的一半）
        return max(1, int(psutil.cpu_count() / 2))


class PerformanceMonitor:
    """
    性能监控类，用于记录和分析程序各阶段的执行时间
    
    Attributes:
        start_time (float): 程序开始时间
        end_time (float): 程序结束时间
        phases (dict): 各阶段的开始和结束时间
    """
    
    def __init__(self):
        """初始化性能监控器"""
        self.start_time = 0.0
        self.end_time = 0.0
        self.phases = {}
    
    def start_program(self):
        """
        记录程序开始时间
        """
        self.start_time = time.time()
    
    def end_program(self):
        """
        记录程序结束时间
        """
        self.end_time = time.time()
    
    def start_phase(self, phase_name):
        """
        记录某个阶段的开始时间
        
        Args:
            phase_name (str): 阶段名称
        """
        if phase_name not in self.phases:
            self.phases[phase_name] = {}
        self.phases[phase_name]['start'] = time.time()
    
    def end_phase(self, phase_name):
        """
        记录某个阶段的结束时间
        
        Args:
            phase_name (str): 阶段名称
        """
        if phase_name in self.phases:
            self.phases[phase_name]['end'] = time.time()
    
    def get_phase_duration(self, phase_name):
        """
        获取某个阶段的持续时间
        
        Args:
            phase_name (str): 阶段名称
            
        Returns:
            float: 阶段持续时间（秒），如果阶段未完成则返回0
        """
        if (phase_name in self.phases and 
            'start' in self.phases[phase_name] and 
            'end' in self.phases[phase_name]):
            return self.phases[phase_name]['end'] - self.phases[phase_name]['start']
        return 0.0
    
    def get_total_duration(self):
        """
        获取程序总执行时间
        
        Returns:
            float: 程序总执行时间（秒）
        """
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    def generate_report(self):
        """
        生成性能报告
        
        Returns:
            str: 格式化的性能报告
        """
        report = ["\n=== 性能分析报告 ==="]
        report.append(f"总执行时间: {self.get_total_duration():.2f} 秒")
        
        if self.phases:
            report.append("\n各阶段执行时间:")
            # 按执行时间排序
            sorted_phases = sorted(
                self.phases.items(), 
                key=lambda x: self.get_phase_duration(x[0]),
                reverse=True
            )
            
            for phase_name, times in sorted_phases:
                duration = self.get_phase_duration(phase_name)
                report.append(f"  {phase_name}: {duration:.2f} 秒")
        
        return "\n".join(report)
    
    def print_report(self):
        """
        打印性能报告
        """
        print_colored(self.generate_report(), Colors.OKCYAN)
    
    def compare_with(self, other_monitor):
        """
        与另一个性能监控器比较性能
        
        Args:
            other_monitor (PerformanceMonitor): 另一个性能监控器实例
            
        Returns:
            str: 格式化的性能比较报告
        """
        report = ["\n=== 性能对比报告 ==="]
        
        # 计算总时间对比
        total1 = self.get_total_duration()
        total2 = other_monitor.get_total_duration()
        if total2 > 0:
            improvement = ((total2 - total1) / total2) * 100
            report.append(f"总执行时间改进: {improvement:.2f}% ({total2:.2f}s → {total1:.2f}s)")
        
        # 计算各阶段对比
        all_phases = set(self.phases.keys()) | set(other_monitor.phases.keys())
        if all_phases:
            report.append("\n各阶段执行时间对比:")
            
            for phase_name in sorted(all_phases):
                duration1 = self.get_phase_duration(phase_name)
                duration2 = other_monitor.get_phase_duration(phase_name)
                
                if duration2 > 0:
                    improvement = ((duration2 - duration1) / duration2) * 100
                    report.append(f"  {phase_name}: {improvement:+.2f}% ({duration2:.2f}s → {duration1:.2f}s)")
                else:
                    report.append(f"  {phase_name}: 未比较 ({duration1:.2f}s)")
        
        return "\n".join(report)
    
    def print_comparison(self, other_monitor):
        """
        打印性能比较报告
        
        Args:
            other_monitor (PerformanceMonitor): 另一个性能监控器实例
        """
        print_colored(self.compare_with(other_monitor), Colors.OKCYAN)

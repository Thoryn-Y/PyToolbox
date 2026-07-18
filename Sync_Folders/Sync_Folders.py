'''
将源目录同步到目标目录，使其内容完全一致（支持指定不同步的文件或目录）
'''
import os
import shutil
import hashlib
import fnmatch
import sys
import time
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
import psutil

# 尝试导入 unicodedata 来处理字符串宽度计算
try:
    import unicodedata
    def str_display_width(text):
        """计算字符串在终端中的显示宽度，正确处理中英文字符"""
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
        """计算字符串在终端中的显示宽度（简化版）"""
        # 简单估算：假设非ASCII字符（可能包括中文）占2个字符宽度
        width = 0
        for char in text:
            if ord(char) < 128:  # ASCII字符
                width += 1
            else:  # 非ASCII字符，可能是中文或其他多字节字符
                width += 2
        return width

# --- 配置 ---
# 支持的哈希算法列表
SUPPORTED_HASHES = ['md5', 'sha1', 'sha256']
DEFAULT_HASH = 'sha256'

# 系统资源使用限制
MAX_RESOURCE_USAGE_RATIO = 0.7  # 最大资源使用率，不超过系统空闲算力的70%

# 文件处理配置
SMALL_FILE_THRESHOLD = 10 * 1024 * 1024  # 小文件阈值，默认10MB
BUFFER_SIZE = 256 * 1024  # 文件读取缓冲区大小，默认256KB


def get_available_cpu_cores(quick_mode=False):
    """获取当前可用的CPU核心数，基于系统空闲率
    
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
        available_cores = int(total_cores * (idle_percent / 100) * MAX_RESOURCE_USAGE_RATIO)
        
        # 确保至少有1个核心可用
        available_cores = max(available_cores, 1)
        # 同时确保不超过总核心数
        available_cores = min(available_cores, total_cores)
        
        return available_cores
    except Exception as e:
        print(f"警告: 无法获取系统CPU信息: {e}")
        # 发生错误时，返回一个保守值（总核心数的一半）
        return max(1, int(psutil.cpu_count() / 2))


class PerformanceMonitor:
    """性能监控类，用于记录和分析程序各阶段的执行时间
    
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
        """记录程序开始时间"""
        self.start_time = time.time()
    
    def end_program(self):
        """记录程序结束时间"""
        self.end_time = time.time()
    
    def start_phase(self, phase_name):
        """记录某个阶段的开始时间
        
        Args:
            phase_name (str): 阶段名称
        """
        if phase_name not in self.phases:
            self.phases[phase_name] = {}
        self.phases[phase_name]['start'] = time.time()
    
    def end_phase(self, phase_name):
        """记录某个阶段的结束时间
        
        Args:
            phase_name (str): 阶段名称
        """
        if phase_name in self.phases:
            self.phases[phase_name]['end'] = time.time()
    
    def get_phase_duration(self, phase_name):
        """获取某个阶段的持续时间
        
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
        """获取程序总执行时间
        
        Returns:
            float: 程序总执行时间（秒）
        """
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    def generate_report(self):
        """生成性能报告
        
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
        """打印性能报告"""
        print_colored(self.generate_report(), Colors.OKCYAN)
    
    def compare_with(self, other_monitor):
        """与另一个性能监控器比较性能
        
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
        """打印性能比较报告
        
        Args:
            other_monitor (PerformanceMonitor): 另一个性能监控器实例
        """
        print_colored(self.compare_with(other_monitor), Colors.OKCYAN)

# ANSI颜色代码
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
    """打印彩色文本，支持传递额外参数给print函数"""
    print(f"{color_code}{text}{Colors.ENDC}", **kwargs)

def get_user_input_path(prompt):
    """获取用户输入的路径，并进行基本验证"""
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

def matches_any_pattern(item_path, patterns, base_path):
    """检查路径是否匹配任何排除模式
    
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


def confirm_recursive_deletion(folder_path):
    """
    递归确认文件夹内的文件和子文件夹是否需要删除
    
    :param folder_path: 文件夹路径
    :return: set 包含确认删除的项目路径
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
    
    :param item_path: 项目路径
    :return: tuple (should_delete_item: bool, recursive_confirmed_items: set)
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


def get_file_hash(file_path, algorithm):
    """计算文件的哈希值
    
    Args:
        file_path (str): 文件路径
        algorithm (str): 使用的哈希算法
        
    Returns:
        str: 文件的哈希值，计算失败返回None
    """
    hash_func = hashlib.new(algorithm)
    try:
        with open(file_path, 'rb') as f:
            # 使用更大的缓冲区读取文件，提高I/O效率
            for chunk in iter(lambda: f.read(BUFFER_SIZE), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except Exception as e:
        print_colored(f"警告: 无法读取文件 '{file_path}' 以计算哈希: {e}", Colors.WARNING)
        return None


def calculate_hashes_in_parallel(file_paths, algorithm=DEFAULT_HASH):
    """并行计算多个文件的哈希值，根据文件大小自动选择处理方式
    
    Args:
        file_paths (list): 文件路径列表
        algorithm (str): 使用的哈希算法
        
    Returns:
        dict: 文件名到哈希值的映射
    """
    def calculate_single_hash(file_path):
        """计算单个文件的哈希值（内部辅助函数）"""
        return get_file_hash(file_path, algorithm)
    
    # 结果字典
    file_hashes = {}
    
    if not file_paths:
        return file_hashes
    
    # 分离小文件和大文件
    small_files = []
    large_files = []
    
    for file_path in file_paths:
        try:
            # 获取文件大小
            file_size = os.path.getsize(file_path)
            
            # 根据文件大小分类
            if file_size < SMALL_FILE_THRESHOLD:
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


def copy_file_with_hash_check(src, dst, algorithm):
    """带哈希校验的文件复制函数
    
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
    """创建符号链接"""
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
    """复制符号链接"""
    try:
        # 读取源符号链接的目标路径
        target = os.readlink(src_link)
        # 创建目标符号链接
        return create_symlink(target, dst_link)
    except Exception as e:
        print_colored(f"警告: 无法复制符号链接 '{src_link}' -> '{dst_link}': {e}", Colors.WARNING)
        return False


def files_are_identical(src, dst, algorithm):
    """检查两个文件内容是否相同
    
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


def dirs_are_identical(src, dst, algorithm, excludes=None):
    """检查两个目录内容是否相同（递归比较所有文件）
    
    Args:
        src (str): 源目录路径
        dst (str): 目标目录路径
        algorithm (str): 哈希算法
        excludes (list): 排除模式列表
        
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
    # 这里可以考虑并行处理子目录，但需要注意递归深度和资源使用
    for src_subdir, dst_subdir in subdirs:
        if not dirs_are_identical(src_subdir, dst_subdir, algorithm, excludes):
            return False
    
    return True





def count_items_recursively(src, excludes):
    """递归计算源目录中需要复制的总项目数（文件+目录），考虑排除规则"""
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
    """带进度条、排除、哈希校验和符号链接处理的 copytree 辅助函数
    
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


def sync_directories(src, dst, excludes, algorithm, follow_symlinks, confirmed_deletions, pbar=None, is_top_level=True, items_to_copy_len=None):
    """
    同步两个目录
    
    :param src: 源目录路径
    :param dst: 目标目录路径
    :param excludes: 排除模式列表
    :param algorithm: 哈希算法
    :param follow_symlinks: 是否跟随符号链接
    :param confirmed_deletions: 确认删除的项目字典，键为项目路径，值为其确认删除的内容集合
    :param pbar: 进度条对象（仅顶层调用时为None）
    :param is_top_level: 是否为顶层调用
    :param items_to_copy_len: 预计算的需要复制的项目数量（用于进度条）
    :return: 布尔值，表示同步是否成功
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
        print_colored(f"同步目录时发生错误: {str(e)}", Colors.FAIL)
        # 如果是顶层调用且有进度条，关闭进度条
        if is_top_level and local_pbar:
            local_pbar.close()
        return False


def preview_sync_info(src_root, dst_root, items_to_copy_info, partial_dir_contents, confirmed_deletions, excludes, algorithm, follow_symlinks):
    """
    显示同步预览信息
    
    :param src_root: 源目录路径
    :param dst_root: 目标目录路径
    :param items_to_copy_info: 需要复制的项目信息字典，键为项目路径，值为包含"type"和"status"的字典
    :param partial_dir_contents: 部分目录内部需要复制的具体内容，键为部分目录路径，值为需要复制的内部项目列表
    :param confirmed_deletions: 确认删除的项目字典，键为项目路径，值为其确认删除的内容集合
    :param excludes: 排除项列表
    :param algorithm: 使用的哈希算法
    :param follow_symlinks: 是否跟随符号链接
    :return: 布尔值，表示是否成功显示预览信息
    """
    try:
        print_colored("\n=== 同步信息预览 ===", Colors.HEADER)
        print(f"源地址: {src_root}")
        print(f"目标地址: {dst_root}")
        print(f"哈希算法: {algorithm}")
        print(f"跟随符号链接: {follow_symlinks}")
        
        # 显示排除项
        if excludes:
            print("\n排除项:")
            for exclude in excludes:
                print_colored(f"  - {exclude}", Colors.WARNING)
        else:
            print("\n排除项: 无")
        
        # 显示将要复制的项目
        if items_to_copy_info:
            print_colored("\n将要复制的项目:", Colors.OKGREEN)
            
            # 分别显示不同类型的项目
            full_directories = []  # 完整目录
            partial_directories = []  # 部分目录
            files = []  # 文件
            symlinks = []  # 符号链接
            
            # 分类项目
            for item_path, info in items_to_copy_info.items():
                if info["type"] == "directory":
                    if info["status"] == "full":
                        full_directories.append(item_path)
                    else:
                        partial_directories.append(item_path)
                elif info["type"] == "file":
                    files.append(item_path)
                elif info["type"] == "symlink":
                    symlinks.append(item_path)
            
            # 显示完整目录
            if full_directories:
                print_colored("\n  完整目录 (将完全复制，不展开内部内容):", Colors.OKGREEN)
                # 计算最长的源路径显示宽度以用于对齐
                max_src_width = max(str_display_width(item) for item in full_directories)
                # 确保至少有20个字符宽，以便对齐效果更好
                max_src_width = max(max_src_width, 20)
                
                for item in sorted(full_directories):
                    src_item_path = item
                    # 计算相对于源根目录的路径用于目标路径
                    relative_path = os.path.relpath(item, src_root)
                    dst_item_path = os.path.join(dst_root, relative_path)
                    
                    # 计算源路径的实际显示宽度
                    src_width = str_display_width(src_item_path)
                    # 计算需要补充的空格数以实现对齐
                    padding = ' ' * (max_src_width - src_width)
                    
                    # 先打印源路径和补充空格，再打印箭头和目标路径
                    print_colored(f"    {src_item_path}", Colors.OKGREEN, end='')
                    print(padding, end='')
                    print_colored(" -> ", Colors.WARNING, end='')
                    print_colored(dst_item_path, Colors.OKBLUE)
            
            # 显示部分目录及其内部需要复制的内容
            if partial_directories:
                print_colored("\n  部分目录 (仅复制变更内容，展开显示内部项目):", Colors.OKCYAN)
                
                # 收集所有部分目录及其内部项目，用于统一计算最大宽度
                all_partial_items = []
                for item in partial_directories:
                    all_partial_items.append(item)
                    if item in partial_dir_contents and partial_dir_contents[item]:
                        all_partial_items.extend(partial_dir_contents[item])
                        # 递归收集所有内部项目
                        for internal_item in partial_dir_contents[item]:
                            if internal_item in partial_dir_contents and partial_dir_contents[internal_item]:
                                all_partial_items.extend(partial_dir_contents[internal_item])
                
                # 计算所有部分目录项目的最大源路径宽度
                if all_partial_items:
                    max_src_width = max(str_display_width(item) for item in all_partial_items)
                    # 确保至少有20个字符宽，以便对齐效果更好
                    max_src_width = max(max_src_width, 20)
                else:
                    max_src_width = 20
                
                # 递归处理目录展开显示的函数
                def display_directory_contents(directory_path, level=1):
                    """
                    递归显示目录内容，支持多级目录展开和对齐
                    
                    :param directory_path: 当前目录路径
                    :param level: 当前目录级别
                    """
                    # 计算当前级别的缩进
                    indent = "    " * level
                    
                    # 计算源路径和目标路径
                    relative_path = os.path.relpath(directory_path, src_root)
                    dst_path = os.path.join(dst_root, relative_path)
                    
                    # 打印当前目录
                    src_width = str_display_width(directory_path)
                    padding = ' ' * (max_src_width - src_width)
                    print_colored(f"{indent}{directory_path}", Colors.OKCYAN, end='')
                    print(padding, end='')
                    print_colored(" -> ", Colors.WARNING, end='')
                    print_colored(dst_path, Colors.OKBLUE)
                    
                    # 显示内部需要复制的项目
                    if directory_path in partial_dir_contents and partial_dir_contents[directory_path]:
                        # 对内部项目进行排序
                        sorted_internal_items = sorted(partial_dir_contents[directory_path])
                        
                        for internal_item in sorted_internal_items:
                            # 计算内部项目的源路径和目标路径
                            internal_relative_path = os.path.relpath(internal_item, src_root)
                            internal_dst_path = os.path.join(dst_root, internal_relative_path)
                            
                            # 检查内部项目是否为目录（实际文件系统判断）
                            is_directory = os.path.isdir(internal_item)
                            
                            if is_directory:
                                # 递归显示子目录内容
                                display_directory_contents(internal_item, level + 1)
                            else:
                                # 计算内部项目的源路径宽度和对齐空格
                                internal_src_width = str_display_width(internal_item)
                                internal_padding = ' ' * (max_src_width - internal_src_width)
                                
                                # 打印内部项目
                                internal_indent = "    " * (level + 1) + "+ "
                                print_colored(f"{internal_indent}{internal_item}", Colors.OKBLUE, end='')
                                print(internal_padding, end='')
                                print_colored(" -> ", Colors.WARNING, end='')
                                print_colored(internal_dst_path, Colors.OKBLUE)
                    else:
                        # 无内部项目需要复制
                        print(f"{indent}    (无需要复制的内部项目)")
                
                # 遍历所有部分目录并显示
                for item in sorted(partial_directories):
                    display_directory_contents(item)
            
            # 显示文件
            if files:
                print_colored("\n  文件:", Colors.OKGREEN)
                # 计算最长的源路径显示宽度以用于对齐
                max_src_width = max(str_display_width(item) for item in files)
                # 确保至少有20个字符宽，以便对齐效果更好
                max_src_width = max(max_src_width, 20)
                
                for item in sorted(files):
                    src_item_path = item
                    # 计算相对于源根目录的路径用于目标路径
                    relative_path = os.path.relpath(item, src_root)
                    dst_item_path = os.path.join(dst_root, relative_path)
                    
                    # 计算源路径的实际显示宽度
                    src_width = str_display_width(src_item_path)
                    # 计算需要补充的空格数以实现对齐
                    padding = ' ' * (max_src_width - src_width)
                    
                    # 先打印源路径和补充空格，再打印箭头和目标路径
                    print_colored(f"    {src_item_path}", Colors.OKGREEN, end='')
                    print(padding, end='')
                    print_colored(" -> ", Colors.WARNING, end='')
                    print_colored(dst_item_path, Colors.OKBLUE)
            
            # 显示符号链接
            if symlinks:
                print_colored("\n  符号链接:", Colors.OKGREEN)
                # 计算最长的源路径显示宽度以用于对齐
                max_src_width = max(str_display_width(item) for item in symlinks)
                # 确保至少有20个字符宽，以便对齐效果更好
                max_src_width = max(max_src_width, 20)
                
                for item in sorted(symlinks):
                    src_item_path = item
                    # 计算相对于源根目录的路径用于目标路径
                    relative_path = os.path.relpath(item, src_root)
                    dst_item_path = os.path.join(dst_root, relative_path)
                    
                    # 计算源路径的实际显示宽度
                    src_width = str_display_width(src_item_path)
                    # 计算需要补充的空格数以实现对齐
                    padding = ' ' * (max_src_width - src_width)
                    
                    # 先打印源路径和补充空格，再打印箭头和目标路径
                    print_colored(f"    {src_item_path}", Colors.OKGREEN, end='')
                    print(padding, end='')
                    print_colored(" -> ", Colors.WARNING, end='')
                    print_colored(dst_item_path, Colors.OKBLUE)
        else:
            print_colored("\n将要复制的项目: 无", Colors.OKGREEN)
        
        # 显示将要删除的项目（只显示经过用户确认的项目）
        if confirmed_deletions:
            print_colored("\n将要删除的项目:", Colors.FAIL)
            # 收集所有要删除的项目路径
            all_deletion_items = set()
            for item_path, recursive_items in confirmed_deletions.items():
                if not recursive_items:
                    # 完整项目删除
                    all_deletion_items.add(item_path)
                else:
                    # 部分内容删除
                    all_deletion_items.update(recursive_items)
            
            # 显示所有要删除的项目
            for item_path in sorted(all_deletion_items):
                print_colored(f"  - {item_path}", Colors.FAIL)
        else:
            print_colored("\n将要删除的项目: 无", Colors.FAIL)
        
        return True
    except Exception as e:
        print_colored(f"生成同步预览时发生错误: {str(e)}", Colors.FAIL)
        return False


def main():
    """主函数，处理用户交互和同步流程控制"""
    # 初始化性能监控器
    perf_monitor = PerformanceMonitor()
    perf_monitor.start_program()
    
    # 交互式获取源和目标路径
    src_root = get_user_input_path("请输入源文件夹绝对地址: ")
    dst_root = get_user_input_path("请输入目标文件夹绝对地址: ")
    
    # 地址一致性校验
    while os.path.abspath(src_root) == os.path.abspath(dst_root):
        print_colored("警告: 源文件夹地址与目标文件夹地址相同，这可能导致数据覆盖风险！", Colors.FAIL)
        print_colored("请重新输入目标文件夹地址。", Colors.WARNING)
        dst_root = get_user_input_path("请输入目标文件夹绝对地址: ")
    
    # 收集排除项
    excludes = []
    while True:
        exclude_input = input("是否有要排除的文件夹或文件? (输入文件/文件夹名称，或输入 N/n 结束): ").strip()
        if exclude_input.lower() in ('n', ''):
            break
        if exclude_input:
            excludes.append(exclude_input)
            print_colored(f"已添加排除项: {exclude_input}", Colors.OKGREEN)
    
    # 获取源目录中的所有项目（文件和目录）
    try:
        src_items = set(os.listdir(src_root))
    except PermissionError:
        print_colored(f"警告: 无法列出源目录 '{src_root}' 的内容 (权限不足)", Colors.WARNING)
        sys.exit(1)
    
    # 获取目标目录中的所有项目以便比较
    try:
        dst_items = set(os.listdir(dst_root))
    except PermissionError:
        print_colored(f"警告: 无法列出目标目录 '{dst_root}' 的内容 (权限不足)", Colors.WARNING)
        sys.exit(1)
    except FileNotFoundError:
        # 如果目标目录不存在，初始化为空集
        dst_items = set()
    
    # 应用排除规则到源目录项目
    if excludes:
        filtered_src_items = set()
        for item in src_items:
            item_full_path = os.path.join(src_root, item)
            # 只有未被排除的项目才加入filtered_src_items
            if not matches_any_pattern(item_full_path, excludes, src_root):
                filtered_src_items.add(item)
        src_items = filtered_src_items
    
    # 计算需要删除的项目（存在于目标目录但不在源目录中）
    # 注意：这里不考虑排除规则对目标目录的影响，因为排除规则通常应用于源目录
    items_to_delete = dst_items - src_items
    
    # 添加删除确认逻辑
    print_colored("\n=== 删除确认 ===", Colors.HEADER)
    print_colored("若确认某个文件夹将要删除时，其内部文件及其子文件夹也将自动确认删除", Colors.OKCYAN)
    
    # confirmed_deletions 字典用于存储用户确认删除的项目
    # 键为项目路径，值为其确认删除的内容集合（对于文件夹的部分删除）
    confirmed_deletions = {}
    
    # 逐项确认删除
    for item in sorted(items_to_delete):
        item_path = os.path.join(dst_root, item)
        should_delete, recursive_items = confirm_deletion(item_path)
        if should_delete:
            # 用户确认删除整个项目
            confirmed_deletions[item_path] = set()  # 空集合表示删除整个项目
        elif recursive_items:
            # 用户选择不删除整个文件夹，但确认删除其中的部分内容
            confirmed_deletions[item_path] = recursive_items
    
    # 创建一个字典存储实际需要复制的项目信息（用于预览）
    # 键为项目路径，值为字典，包含"type"（"file"或"directory"）和"status"（"partial"或"full"）
    items_to_copy_info = {}
    
    # 创建一个字典存储部分目录内部需要复制的具体内容
    # 键为部分目录路径，值为需要复制的内部项目列表
    partial_dir_contents = {}
    
    # 设置默认参数
    algorithm = DEFAULT_HASH
    follow_symlinks = False  # 默认不跟随符号链接
    
    # 开始收集需要复制的项目
    perf_monitor.start_phase("收集需要复制的项目")
    
    def collect_items_to_copy(src_dir, dst_dir, relative_path=""):
        """递归收集需要复制的项目"""
        try:
            src_items = os.listdir(src_dir)
        except PermissionError:
            print_colored(f"警告: 无法列出源目录 '{src_dir}' 的内容 (权限不足)", Colors.WARNING)
            return set()  # 返回空集合
        
        # 应用排除规则到当前目录的项目
        if excludes:
            filtered_src_items = []
            for item in src_items:
                item_full_path = os.path.join(src_dir, item)
                if not matches_any_pattern(item_full_path, excludes, src_root):
                    filtered_src_items.append(item)
            src_items = filtered_src_items
        
        # 用于收集当前目录下需要复制的项目
        current_items_to_copy = set()
        
        for item in src_items:
            src_path = os.path.join(src_dir, item)
            dst_path = os.path.join(dst_dir, item)
            relative_item_path = os.path.join(relative_path, item) if relative_path else item
            full_src_path = os.path.join(src_root, relative_item_path)  # 注意这里使用的是src_root
            
            # 检查项目是否为符号链接
            if os.path.islink(src_path):
                # 在预览模式下，我们总是显示符号链接本身
                current_items_to_copy.add(full_src_path)
            # 根据项目类型（目录或文件）决定是否需要复制
            elif os.path.isdir(src_path):
                # 对于目录，只有在内容不同时才需要复制
                if not dirs_are_identical(src_path, dst_path, algorithm, excludes):
                    # 递归检查子目录中的具体文件
                    sub_items = collect_items_to_copy(src_path, dst_path, relative_item_path)
                    current_items_to_copy.update(sub_items)
                else:
                    # 如果目录内容相同，不需要复制任何东西
                    pass
            elif os.path.isfile(src_path):
                # 对于文件，只有在内容不同时才需要复制
                if not files_are_identical(src_path, dst_path, algorithm):
                    current_items_to_copy.add(full_src_path)
        
        return current_items_to_copy
    
    # 遍历过滤后的源目录项目，确定需要复制的内容
    for item in src_items:
        src_path = os.path.join(src_root, item)
        dst_path = os.path.join(dst_root, item)
        
        # 检查项目是否为符号链接
        if os.path.islink(src_path):
            # 在预览模式下，我们总是显示符号链接本身
            items_to_copy_info[src_path] = {"type": "symlink", "status": "full"}
        # 根据项目类型（目录或文件）决定是否需要复制
        elif os.path.isdir(src_path):
            # 对于目录，只有在内容不同时才需要复制
            if not dirs_are_identical(src_path, dst_path, algorithm, excludes):
                # 检查是否是整个目录需要复制还是部分文件需要复制
                # 通过递归收集子目录中的文件来判断
                temp_items = set()
                
                def collect_dir_files(current_src_dir, current_relative_path):
                    """收集目录中的所有文件"""
                    try:
                        current_items = os.listdir(current_src_dir)
                    except PermissionError:
                        print_colored(f"警告: 无法列出源目录 '{current_src_dir}' 的内容 (权限不足)", Colors.WARNING)
                        return
                    
                    # 应用排除规则到当前目录的项目
                    if excludes:
                        filtered_current_items = []
                        for current_item in current_items:
                            current_item_full_path = os.path.join(current_src_dir, current_item)
                            if not matches_any_pattern(current_item_full_path, excludes, src_root):
                                filtered_current_items.append(current_item)
                        current_items = filtered_current_items
                    
                    for current_item in current_items:
                        current_src_path = os.path.join(current_src_dir, current_item)
                        current_relative_item_path = os.path.join(current_relative_path, current_item) if current_relative_path else current_item
                        full_current_src_path = os.path.join(src_root, current_relative_item_path)
                        
                        if os.path.isdir(current_src_path):
                            # 递归检查子目录
                            collect_dir_files(current_src_path, current_relative_item_path)
                        elif os.path.isfile(current_src_path):
                            # 添加文件到临时集合
                            temp_items.add(full_current_src_path)
                
                # 收集目录中的所有文件
                collect_dir_files(src_path, item)
                
                # 收集目录中所有需要复制的具体文件
                temp_items_to_copy = collect_items_to_copy(src_path, dst_path, item)
                
                # 比较两个集合来判断是部分还是全部文件需要复制
                if len(temp_items_to_copy) == len(temp_items):
                    # 所有文件都需要复制，标记整个目录需要复制
                    items_to_copy_info[src_path] = {"type": "directory", "status": "full"}
                else:
                    # 只有部分文件需要复制，标记目录为部分复制
                    items_to_copy_info[src_path] = {"type": "directory", "status": "partial"}
                    # 记录部分目录内部需要复制的具体内容
                    partial_dir_contents[src_path] = list(temp_items_to_copy)
            else:
                # 如果整个目录内容相同，不需要复制
                pass
        elif os.path.isfile(src_path):
            # 对于文件，只有在内容不同时才需要复制
            if not files_are_identical(src_path, dst_path, algorithm):
                items_to_copy_info[src_path] = {"type": "file", "status": "full"}
    
    # 提取需要复制的项目路径集合（保持向后兼容）
    items_to_copy = set(items_to_copy_info.keys())
    
    # 结束收集需要复制的项目阶段
    perf_monitor.end_phase("收集需要复制的项目")
    
    # 开始生成同步预览
    perf_monitor.start_phase("生成同步预览")
    
    # 显示同步信息预览（只显示经过确认的待删除项目）
    # 在预览中只传递经过确认的项目
    if not preview_sync_info(src_root, dst_root, items_to_copy_info, partial_dir_contents, confirmed_deletions, excludes, algorithm, follow_symlinks):
        print_colored("无法生成同步预览信息，程序退出。", Colors.FAIL)
        sys.exit(1)
    
    # 结束生成同步预览阶段
    perf_monitor.end_phase("生成同步预览")
    
    # 最终确认
    while True:
        confirm = input("\n是否开始同步文件? (y/[n]): ").strip().lower()
        if confirm in ('y', 'yes'):
            break
        elif confirm in ('n', '', 'no'):
            print_colored("用户取消同步操作，程序退出。", Colors.OKCYAN)
            sys.exit(0)
        else:
            print_colored("无效输入，请输入 y 或 n。", Colors.WARNING)
    
    # 开始执行同步
    perf_monitor.start_phase("执行同步")
    
    # 执行同步，传入预览阶段确定的items_to_copy集合大小作为复制任务数
    if not sync_directories(src_root, dst_root, excludes, algorithm, follow_symlinks, confirmed_deletions, items_to_copy_len=len(items_to_copy)):
        sys.exit(1)  # 如果同步过程中有错误或警告，退出码为1
    
    # 结束执行同步阶段
    perf_monitor.end_phase("执行同步")
    
    # 结束程序性能监控
    perf_monitor.end_program()
    
    # 打印性能报告
    perf_monitor.print_report()
    
    # 成功执行则正常退出 (exit code 0)


if __name__ == "__main__":
    main()
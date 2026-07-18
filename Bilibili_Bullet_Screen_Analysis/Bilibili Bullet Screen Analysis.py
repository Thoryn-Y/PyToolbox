"""
B站弹幕解析工具
"""
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
import os
import re
import matplotlib.pyplot as plt
from collections import Counter

# ======================== matplotlib 中文字体配置 ========================
# 检测系统中实际可用的中文字体，避免中文显示为方块
import matplotlib.font_manager as fm
_CN_CANDIDATES = ['Microsoft YaHei', 'SimHei', 'STSong', 'STFangsong', 'AR PL UMing CN']
_available = {f.name for f in fm.fontManager.ttflist}
_CN_FONT = next((f for f in _CN_CANDIDATES if f in _available), None)
if _CN_FONT:
    plt.rcParams['font.sans-serif'] = [_CN_FONT]
else:
    print("警告：未找到常见中文字体，图表中文可能显示异常")
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示为方块的问题
# ==========================================================================

# ======================== 配置区（在这里修改所有参数）========================
CONFIG = {
    # 输入文件配置
    "input_xml_path": "",  # 目标XML弹幕文件路径

    # 输出目录配置（所有结果将保存到这个文件夹）
    "output_directory": "",          # 输出文件夹路径

    # 视频时长配置（使用时:分:秒格式，如"1:23:45"表示1小时23分45秒）（同时支持分:秒格式）
    "video_duration": "",             # 视频总时长（与B站显示格式一致）

    # 过滤配置
    "ignore_short_danmaku": False,           # 是否忽略短弹幕
    "short_danmaku_length": 3,               # 短弹幕判断阈值（字符数）

    # 图表配置
    "enable_charts": True,                   # 是否生成统计图表
}
# ============================================================================

class DanmakuParser:
    def __init__(self, config):
        # 输入文件路径
        self.input_file = config["input_xml_path"]

        # 输出目录设置
        self.output_dir = config["output_directory"]
        self.excel_filename = "弹幕分析结果.xlsx"  # Excel文件名
        self.output_excel_path = os.path.join(self.output_dir, self.excel_filename)

        # 解析视频时长（从时:分:秒格式转换为秒）
        self.video_duration_sec = self._parse_duration(config["video_duration"])

        # 过滤设置
        self.ignore_short = config["ignore_short_danmaku"]
        self.short_threshold = config["short_danmaku_length"]
        self.enable_charts = config["enable_charts"]

        # 确保输出目录存在
        self._create_output_directory()

        # 数据存储
        self.danmaku_data = []
        self.user_stats = {}
        self.dfs = None  # 存储已保存的DataFrame，避免重复保存

        # 映射表
        self.danmaku_type_map = {
            "1": "滚动弹幕", "4": "底部固定", "5": "顶部固定",
            "6": "逆向弹幕", "7": "高级弹幕", "8": "代码弹幕"
        }
        self.color_map = {
            16777215: "白色", 16711680: "红色", 65280: "绿色",
            255: "蓝色", 16776960: "黄色", 16711935: "紫色"
        }

    def _parse_duration(self, duration_str):
        """将时:分:秒格式的时长转换为总秒数"""
        try:
            # 分割时间部分，支持2位（分:秒）或3位（时:分:秒）格式
            parts = list(map(int, duration_str.split(':')))

            if len(parts) == 2:
                minutes, seconds = parts
                hours = 0
            elif len(parts) == 3:
                hours, minutes, seconds = parts
            else:
                raise ValueError("格式错误")

            total_seconds = hours * 3600 + minutes * 60 + seconds
            print(f"视频时长解析成功: {hours}时{minutes}分{seconds}秒 ({total_seconds}秒)")
            return total_seconds
        except Exception as e:
            print(f"时长格式错误，使用默认值5000秒。请使用'时:分:秒'格式（如'1:23:45'）")
            return 5000

    def _create_output_directory(self):
        """创建输出目录（如果不存在）"""
        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
                print(f"已创建输出目录: {os.path.abspath(self.output_dir)}")
            else:
                print(f"输出目录: {os.path.abspath(self.output_dir)}")
        except Exception as e:
            print(f"创建目录失败: {str(e)}")
            raise  # 无法创建目录时终止程序

    def rgb_to_hex(self, rgb):
        blue = rgb & 255
        green = (rgb >> 8) & 255
        red = (rgb >> 16) & 255
        return f'#{red:02x}{green:02x}{blue:02x}'

    def analyze_user_behavior(self, user_hash, appear_time, content):
        """分析用户行为数据"""
        if user_hash not in self.user_stats:
            self.user_stats[user_hash] = {
                "发送数量": 0,
                "首次发送": appear_time,
                "末次发送": appear_time,
                "总长度": 0,
                "内容列表": []
            }

        stats = self.user_stats[user_hash]
        stats["发送数量"] += 1
        stats["末次发送"] = max(stats["末次发送"], appear_time)
        stats["总长度"] += len(content)
        stats["内容列表"].append(content)

    def parse_danmaku(self):
        """解析XML弹幕文件"""
        try:
            if not os.path.exists(self.input_file):
                print(f"错误：找不到输入文件 {self.input_file}")
                return False

            tree = ET.parse(self.input_file)
            root = tree.getroot()
            total_danmakus = len(root.findall('d'))
            print(f"发现 {total_danmakus} 条弹幕，开始解析...")

            for idx, danmaku in enumerate(root.findall('d')):
                p_attr = danmaku.attrib['p'].split(',')
                if len(p_attr) < 9:
                    continue

                try:
                    # 解析基础参数
                    appear_time = float(p_attr[0])
                    content = danmaku.text.strip() if danmaku.text else ""

                    # 过滤短弹幕
                    if self.ignore_short and len(content) <= self.short_threshold:
                        continue

                    # 解析其他参数
                    danmaku_type = self.danmaku_type_map.get(p_attr[1], f"未知({p_attr[1]})")
                    color_rgb = int(p_attr[3])
                    color_name = self.color_map.get(color_rgb, self.rgb_to_hex(color_rgb))
                    send_time = datetime.fromtimestamp(int(p_attr[4])).strftime('%Y-%m-%d %H:%M:%S')
                    is_member = "是" if p_attr[5] == "1" else "否"
                    user_hash = p_attr[6]

                    # 分析用户行为
                    self.analyze_user_behavior(user_hash, appear_time, content)

                    # 保存数据
                    self.danmaku_data.append({
                        "序号": idx + 1,
                        "出现时间(秒)": round(appear_time, 2),
                        "出现时间点": f"{int(appear_time//3600)}:{int((appear_time%3600)//60)}:{int(appear_time%60)}",
                        "弹幕类型": danmaku_type,
                        "颜色": color_name,
                        "发送时间": send_time,
                        "是否会员": is_member,
                        "用户标识": user_hash,
                        "弹幕内容": content,
                        "内容长度": len(content)
                    })
                except Exception as e:
                    continue

            print(f"解析完成，有效弹幕: {len(self.danmaku_data)} 条")
            return True
        except Exception as e:
            print(f"解析出错: {str(e)}")
            return False

    def save_results(self):
        """保存解析结果到Excel（仅保存一次）"""
        if self.dfs is not None:
            return self.dfs  # 已保存过，直接返回结果，避免重复保存

        if not self.danmaku_data:
            print("没有可保存的数据")
            return None

        # 创建主数据表
        df_main = pd.DataFrame(self.danmaku_data)

        # 创建用户分析表
        user_data = []
        for user_hash, stats in self.user_stats.items():
            # 提取高频词
            all_text = ' '.join(stats["内容列表"])
            words = re.findall(r'\b\w{2,}\b', all_text)
            top_words = Counter(words).most_common(3)

            user_data.append({
                "用户标识": user_hash,
                "发送数量": stats["发送数量"],
                "活跃时长(秒)": round(stats["末次发送"] - stats["首次发送"], 1),
                "平均长度": round(stats["总长度"] / stats["发送数量"], 1) if stats["发送数量"] > 0 else 0,
                "高频词汇": ', '.join([w[0] for w in top_words]) if top_words else "无"
            })

        df_users = pd.DataFrame(user_data).sort_values("发送数量", ascending=False)

        # 保存到Excel
        try:
            with pd.ExcelWriter(self.output_excel_path) as writer:
                df_main.to_excel(writer, sheet_name="弹幕列表", index=False)
                df_users.to_excel(writer, sheet_name="用户分析", index=False)
            print(f"Excel结果已保存到: {self.output_excel_path}")
            self.dfs = (df_main, df_users)  # 保存结果到实例变量
            return self.dfs
        except Exception as e:
            print(f"保存文件失败: {str(e)}")
            return None

    def generate_charts(self):
        """生成统计图表（使用已保存的DataFrame，避免重复保存）"""
        if not self.enable_charts or not self.danmaku_data:
            return

        # 获取已保存的DataFrame（如果未保存则先保存）
        if self.dfs is None:
            self.dfs = self.save_results()
        if self.dfs is None:
            return

        df_main, df_users = self.dfs

        # 1. 弹幕时间分布图表
        plt.figure(figsize=(12, 6))
        bins = int(self.video_duration_sec / 60)  # 每60秒一个区间
        plt.hist(df_main["出现时间(秒)"], bins=bins, color='#3498db')
        plt.title('弹幕时间分布')
        plt.xlabel('视频时间(秒)')
        plt.ylabel('弹幕数量')
        plt.grid(alpha=0.3)
        plt.savefig(os.path.join(self.output_dir, '弹幕时间分布.png'), dpi=300, bbox_inches='tight')
        plt.close()

        # 2. 弹幕类型分布图表
        plt.figure(figsize=(8, 8))
        type_counts = df_main["弹幕类型"].value_counts()
        plt.pie(type_counts, labels=type_counts.index, autopct='%1.1f%%',
                colors=['#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#3498db'])
        plt.title('弹幕类型占比')
        plt.savefig(os.path.join(self.output_dir, '弹幕类型分布.png'), dpi=300, bbox_inches='tight')
        plt.close()

        print(f"统计图表已保存到: {self.output_dir}")

    def run(self):
        """运行解析流程"""
        print("===== B站弹幕解析工具 =====")
        if self.parse_danmaku():
            self.save_results()  # 只保存一次Excel
            if self.enable_charts:
                self.generate_charts()  # 生成图表时复用已保存的DataFrame
        print("===== 处理完成 =====")

if __name__ == "__main__":
    # 使用配置初始化解析器并运行
    parser = DanmakuParser(CONFIG)
    parser.run()
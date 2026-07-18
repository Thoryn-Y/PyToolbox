'''
增强版密码生成器
'''

import random
import sys
import string
import re
from typing import List, Dict, Tuple

# 字符集定义
UPPERCASE = string.ascii_uppercase  # 大写字母
LOWERCASE = string.ascii_lowercase  # 小写字母
NUMBERS = string.digits             # 数字
BASIC_PUNCT = '!@#$%^&*()_+-=[]{}|;:\'",.<>/?'  # 基本标点符号
EXTENDED_PUNCT = '~`§±¶€£¥¢©®™'     # 扩展特殊字符集


def evaluate_strength(password: str) -> Tuple[str, List[str]]:
    """
    评估密码强度并返回评级和详细分析

    参数:
        password: 待评估的密码字符串

    返回:
        强度评级("弱"/"中"/"强"/"极强")和详细分析列表
    """
    score = 0
    feedback = []

    # 1. 长度评分 (0-4分)
    length = len(password)
    if length >= 20:
        score += 4
        feedback.append(f"密码长度优秀({length}位)")
    elif length >= 16:
        score += 3
        feedback.append(f"密码长度良好({length}位)")
    elif length >= 12:
        score += 2
        feedback.append(f"密码长度一般({length}位)")
    elif length >= 8:
        score += 1
        feedback.append(f"密码长度偏短({length}位)")
    else:
        feedback.append(f"密码长度过短({length}位)，安全性低")

    # 2. 字符类型评分 (0-4分)
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_number = any(c.isdigit() for c in password)
    has_punct = any(c in BASIC_PUNCT + EXTENDED_PUNCT for c in password)

    type_count = sum([has_upper, has_lower, has_number, has_punct])
    score += type_count

    if type_count == 4:
        feedback.append("包含所有类型字符(大小写字母、数字、符号)")
    elif type_count >= 2:
        feedback.append(f"包含{type_count}种不同类型字符")
    else:
        feedback.append(f"仅包含{type_count}种字符类型，多样性不足")

    # 3. 字符分布评分 (0-2分)
    if length >= 8:  # 长度足够时才评估分布
        upper_ratio = sum(1 for c in password if c.isupper()) / length
        lower_ratio = sum(1 for c in password if c.islower()) / length
        number_ratio = sum(1 for c in password if c.isdigit()) / length
        punct_ratio = sum(1 for c in password if c in BASIC_PUNCT + EXTENDED_PUNCT) / length

        # 检查是否有某类字符占比过高(>70%)
        if max(upper_ratio, lower_ratio, number_ratio, punct_ratio) < 0.7:
            score += 2
            feedback.append("字符分布均匀")
        else:
            feedback.append("部分字符类型占比过高")

    # 4. 连续字符检测 (扣0-2分)
    consecutive_count = 0
    for i in range(len(password)-2):
        # 检测连续3个相同字符(如aaa, 111)
        if password[i] == password[i+1] == password[i+2]:
            consecutive_count += 1

    if consecutive_count > 0:
        score -= min(consecutive_count, 2)  # 最多扣2分
        feedback.append(f"包含{consecutive_count}处连续相同字符，降低了安全性")

    # 5. 常见模式检测 (扣0-2分)
    common_patterns = [
        r'\d{4,}',          # 连续4位以上数字(如1234)
        r'[a-zA-Z]{5,}',    # 连续5位以上字母(如abcde)
        r'123|abc|qwe|asd'  # 常见序列
    ]

    pattern_matches = 0
    for pattern in common_patterns:
        if re.search(pattern, password, re.IGNORECASE):
            pattern_matches += 1

    if pattern_matches > 0:
        score -= min(pattern_matches, 2)  # 最多扣2分
        feedback.append(f"包含{pattern_matches}种常见字符模式，安全性降低")

    # 确定评级
    if score >= 8:
        rating = "极强"
    elif score >= 6:
        rating = "强"
    elif score >= 4:
        rating = "中"
    else:
        rating = "弱"

    return rating, feedback


def generate_password(
    length: int,
    upper: bool,
    lower: bool,
    number: bool,
    basic_punct: bool,
    extended_punct: bool
) -> str:
    """生成指定条件的随机密码"""
    # 验证参数有效性
    required_types = sum([upper, lower, number, basic_punct, extended_punct])
    if required_types == 0:
        raise ValueError("至少需要选择一种字符类型")
    if length < required_types:
        raise ValueError(f"密码长度({length})不能小于所需字符类型数量({required_types})")

    # 筛选启用的字符集
    enabled_sets: List[str] = []
    if upper:
        enabled_sets.append(UPPERCASE)
    if lower:
        enabled_sets.append(LOWERCASE)
    if number:
        enabled_sets.append(NUMBERS)
    if basic_punct:
        enabled_sets.append(BASIC_PUNCT)
    if extended_punct:
        enabled_sets.append(EXTENDED_PUNCT)

    # 分配每种字符的数量
    counts = [1] * len(enabled_sets)
    remaining = length - len(enabled_sets)

    # 随机分配剩余字符数
    for _ in range(remaining):
        counts[random.randint(0, len(counts)-1)] += 1

    # 生成各类型字符并合并
    password_chars: List[str] = []
    for i, char_set in enumerate(enabled_sets):
        password_chars.extend([random.choice(char_set) for _ in range(counts[i])])

    # 打乱字符顺序
    random.shuffle(password_chars)

    return ''.join(password_chars)


def main(config: Dict):
    """生成并打印多个密码，带强度评估"""
    try:
        print(f"生成{config['num_passwords']}个长度为{config['length']}的密码：")
        print("-" * 80)
        print(f"{'序号':<5} {'密码':<29} {'强度':<5} 分析")
        print("-" * 80)

        for i in range(config['num_passwords']):
            pw = generate_password(
                length=config['length'],
                upper=config['upper'],
                lower=config['lower'],
                number=config['number'],
                basic_punct=config['basic_punct'],
                extended_punct=config['extended_punct']
            )
            strength, feedback = evaluate_strength(pw)
            print(f"{i+1:<6} {pw:<30} {strength:<5} {'; '.join(feedback)}")

        print("-" * 80)
        print("提示：强密码建议长度≥16位并包含3种以上字符类型，避免常见模式")

    except ValueError as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # 所有可配置参数集中在这里
    config = {
        'num_passwords': 10,     # 生成密码的数量
        'length': 8,           # 单个密码长度
        'upper': True,          # 是否包含大写字母
        'lower': True,          # 是否包含小写字母
        'number': True,         # 是否包含数字
        'basic_punct': True,    # 是否包含基本标点
        'extended_punct': False # 是否包含扩展标点
    }

    main(config)

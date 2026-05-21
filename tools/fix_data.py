#!/usr/bin/env python3
"""
修复数据文件中的编码问题
把错误编码的中文修复回来
"""
import json
import sys
from pathlib import Path
import re


def fix_mojibake(text: str) -> str:
    """
    修复乱码问题：把被错误latin-1编码的中文修复回UTF-8
    原理：原来的UTF-8字节被当成latin-1解码了，现在重新编码回去

    参数：
        text: 包含乱码的字符串

    返回：
        修复后的字符串
    """
    if not text:
        return text

    # 检测是否包含乱码特征
    mojibake_pattern = re.compile(r'[\x80-\xff]')
    if not mojibake_pattern.search(text):
        return text

    try:
        # 修复方法：把字符串按latin-1编码回字节，再按UTF-8解码
        # 但要小心，只有确实是乱码的部分才修复

        # 尝试修复
        fixed = text.encode('latin-1').decode('utf-8')
        return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        try:
            # 如果latin-1不行试试ISO-8859-1
            fixed = text.encode('iso-8859-1').decode('utf-8')
            return fixed
        except:
            # 还是失败返回原文本
            return text


def fix_dict_recursive(obj):
    """递归修复字典中的字符串"""
    if isinstance(obj, dict):
        return {k: fix_dict_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [fix_dict_recursive(item) for item in obj]
    elif isinstance(obj, str):
        return fix_mojibake(obj)
    else:
        return obj


def fix_json_file(file_path: Path):
    """修复json文件"""
    print(f"修复文件: {file_path}")

    if not file_path.exists():
        print(f"文件不存在: {file_path}")
        return False

    # 读取文件
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 备份原文件
    backup_path = file_path.parent / f"{file_path.stem}_原{file_path.suffix}"
    file_path.rename(backup_path)
    print(f"备份到: {backup_path}")

    # 修复数据
    fixed_data = fix_dict_recursive(data)

    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(fixed_data, f, ensure_ascii=False, indent=2)

    print(f"修复完成: {file_path}")
    return True


def fix_markdown_file(file_path: Path):
    """修复markdown文件"""
    print(f"修复文件: {file_path}")

    if not file_path.exists():
        print(f"文件不存在: {file_path}")
        return False

    # 读取文件
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 备份原文件
    backup_path = file_path.parent / f"{file_path.stem}_原{file_path.suffix}"
    file_path.rename(backup_path)
    print(f"备份到: {backup_path}")

    # 修复数据
    fixed_content = fix_mojibake(content)

    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)

    print(f"修复完成: {file_path}")
    return True


def main():
    output_dir = Path("/Users/mac/Documents/trae_projects/prompt-engineering/output")

    dates = ["20260508", "20260509"]

    for date in dates:
        date_dir = output_dir / date

        if not date_dir.exists():
            continue

        print(f"\n处理目录: {date_dir}")

        # 查找数据文件
        data_files = list(date_dir.glob("*数据.json"))
        for data_file in data_files:
            fix_json_file(data_file)

        # 纪要文件
        md_files = list(date_dir.glob("*纪要.md"))
        for md_file in md_files:
            fix_markdown_file(md_file)

    print("\n修复完成！")


if __name__ == "__main__":
    main()

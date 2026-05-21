#!/usr/bin/env python3
"""
修复数据文件中的编码问题 - V2
直接读取原始字节来修复
"""
import json
from pathlib import Path


def fix_file_direct(file_path: Path):
    """直接读取原始字节，检测并修复"""
    print(f"修复文件: {file_path}")

    # 读取原始字节
    with open(file_path, 'rb') as f:
        bytes_data = f.read()

    try:
        # 先用UTF-8读一次
        content = bytes_data.decode('utf-8')
    except UnicodeDecodeError:
        print(f"不是UTF-8编码，尝试其他方式...")
        return False

    # 现在修复内容中的乱码
    # 这种乱码特征：被utf-8编码但被误读为latin-1，所以会有很多å, è, ä等字符
    # 修复策略：
    # 对于包含latin-1字符范围(0x80-0xFF)的字符串，尝试修复
    import re

    # 先备份
    backup_path = file_path.parent / f"{file_path.stem}_原{file_path.suffix}"
    file_path.rename(backup_path)
    print(f"备份到: {backup_path}")

    # 找出需要修复的字符序列
    # 这种乱码通常是连续的latin-1扩展字符
    # 我们用更激进的方式：尝试修复整个文件

    # 为了安全，我们逐段处理
    fixed_content = try_fix_text(content)

    # 写回
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)

    print(f"修复完成: {file_path}")
    return True


def try_fix_text(text: str) -> str:
    """尝试修复文本中的乱码"""
    # 把文本中可能是乱码的部分修复
    result = []
    i = 0
    n = len(text)

    while i < n:
        # 检测是否可能是乱码区域：连续的latin-1扩展字符(ord >= 0x80)
        if ord(text[i]) >= 0x80:
            # 收集连续的高位字符
            start = i
            while i < n and ord(text[i]) >= 0x80:
                i += 1

            # 提取这段可能的乱码
            mojibake_part = text[start:i]

            # 尝试修复
            fixed_part = try_repair(mojibake_part)
            result.append(fixed_part)
        else:
            result.append(text[i])
            i += 1

    return ''.join(result)


def try_repair(s: str) -> str:
    """尝试修复乱码片段"""
    # 首先看这段是不是能修复
    if len(s) < 2:
        return s

    try:
        # 标准修复：latin-1编码 -> utf-8解码
        return s.encode('latin-1').decode('utf-8')
    except:
        # 如果失败试试其他方式
        try:
            # 有些是用cp1252存的
            return s.encode('cp1252').decode('utf-8')
        except:
            # 实在不行就原样返回
            return s


def main():
    output_dir = Path("/Users/mac/Documents/trae_projects/prompt-engineering/output")

    dates = ["20260508", "20260509"]

    for date in dates:
        date_dir = output_dir / date

        if not date_dir.exists():
            continue

        print(f"\n处理目录: {date_dir}")

        # 先把之前修改错误的文件从备份恢复
        for backup_file in date_dir.glob("*_原*"):
            # 找到原文件
            orig_name = backup_file.name.replace("_原", "", 1)
            orig_file = date_dir / orig_name
            if orig_file.exists():
                orig_file.unlink()
            backup_file.rename(orig_file)
            print(f"已恢复: {orig_file}")

        # 现在开始修复
        for json_file in date_dir.glob("*数据.json"):
            fix_file_direct(json_file)

        for md_file in date_dir.glob("*纪要.md"):
            fix_file_direct(md_file)

    print("\n修复完成！")


if __name__ == "__main__":
    main()

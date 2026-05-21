#!/usr/bin/env python3
"""诊断编码问题"""

# 测试样本
sample = "è½¬å"  # 应为"转发"
print(f"原文: {sample}")

# 尝试各种修复方式
print("\n尝试1: latin-1编码 -> utf-8解码:")
try:
    fixed = sample.encode('latin-1').decode('utf-8')
    print(f"结果: {fixed}")
except Exception as e:
    print(f"失败: {e}")

print("\n尝试2: 直接查字符编码:")
for c in sample:
    print(f"'{c}' → U+{ord(c):04X}")

# 让我看看原始字节
print("\n尝试3: 各种编码组合:")
from encodings.aliases import aliases

test_encodings = ['latin-1', 'iso-8859-1', 'cp1252', 'utf-8', 'gbk', 'gb2312', 'big5']

for enc1 in test_encodings:
    for enc2 in test_encodings:
        if enc1 == enc2:
            continue
        try:
            fixed = sample.encode(enc1).decode(enc2)
            if "转" in fixed or "发" in fixed or len(fixed) < len(sample):
                print(f"{enc1} → {enc2}: {fixed}")
        except:
            pass

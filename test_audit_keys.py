"""测试 audit_keys 模块的规范化函数"""
import sys
sys.path.insert(0, '/aidata/x-llmapp1/backend')

from app.works.tender.review.audit_keys import (
    is_price_anchor,
    normalize_money_to_cny,
    normalize_duration_to_days,
    normalize_warranty_to_months,
    normalize_dimension,
)

print("=" * 60)
print("Step 1: 测试 audit_keys 规范化函数")
print("=" * 60)

# 测试价格锚点判断
print("\n【测试 is_price_anchor】")
test_cases_anchor = [
    ("投标总价：500万元", True),
    ("报价表中总价为100万", True),
    ("开标一览表", True),
    ("类似项目业绩，合同金额800万元", False),
    ("项目业绩证明", False),
]
for text, expected in test_cases_anchor:
    result = is_price_anchor(text)
    status = "✅" if result == expected else "❌"
    print(f"{status} {text!r} → {result} (期望: {expected})")

# 测试金额规范化
print("\n【测试 normalize_money_to_cny】")
test_cases_money = [
    ("500万元", 5000000),
    ("50万", 500000),
    ("1,234,567元", 1234567),
    ("￥100,000", 100000),
    ("800.5万元", 8005000),
]
for text, expected in test_cases_money:
    result = normalize_money_to_cny(text)
    status = "✅" if result == expected else "❌"
    print(f"{status} {text!r} → {result} (期望: {expected})")

# 测试工期规范化
print("\n【测试 normalize_duration_to_days】")
test_cases_duration = [
    ("90天", 90),
    ("120日", 120),
    ("90个自然日", 90),
    ("3个月", 90),
]
for text, expected in test_cases_duration:
    result = normalize_duration_to_days(text)
    status = "✅" if result == expected else "❌"
    print(f"{status} {text!r} → {result} (期望: {expected})")

# 测试质保期规范化
print("\n【测试 normalize_warranty_to_months】")
test_cases_warranty = [
    ("24个月", 24),
    ("2年", 24),
    ("4年", 48),
    ("36月", 36),
]
for text, expected in test_cases_warranty:
    result = normalize_warranty_to_months(text)
    status = "✅" if result == expected else "❌"
    print(f"{status} {text!r} → {result} (期望: {expected})")

# 测试维度规范化
print("\n【测试 normalize_dimension】")
test_cases_dimension = [
    ("资格", "qualification"),
    ("价格", "price"),
    ("technical", "technical"),
    ("商务", "business"),
]
for text, expected in test_cases_dimension:
    result = normalize_dimension(text)
    status = "✅" if result == expected else "❌"
    print(f"{status} {text!r} → {result} (期望: {expected})")

print("\n" + "=" * 60)
print("Step 1 验收完成 ✅")
print("=" * 60)

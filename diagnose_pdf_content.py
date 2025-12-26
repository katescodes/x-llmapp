#!/usr/bin/env python3
"""
PDF内容诊断脚本 - 查看测试1项目的PDF文件内容
"""
import sys
sys.path.insert(0, '/app')

from app.services.fragment.pdf_layout_extractor import extract_pdf_items
from app.services.fragment.pdf_sample_detector import detect_pdf_fragments, locate_region
from app.services.fragment.fragment_matcher import FragmentTitleMatcher
import json

# 项目信息
PROJECT_ID = "tp_3246be74991b44b1a75a93825501a101"
PDF_PATH = "/app/data/tender_assets/tp_3246be74991b44b1a75a93825501a101/tender_2840f3b4287a44f89528ff3e7ca2fa60_含山县城乡统筹供水一体化升级改造工程项目-仙踪镇剩余供水支管网改造工程（加压泵站设备采购及安装项目）-招标文件正文.pdf"

print("=" * 60)
print("PDF范本提取诊断")
print("=" * 60)
print(f"项目ID: {PROJECT_ID}")
print(f"PDF路径: {PDF_PATH}")
print()

# Step 1: 提取PDF items
print("📄 Step 1: 提取PDF items...")
print("-" * 60)
try:
    items, pdf_diag = extract_pdf_items(PDF_PATH, max_pages=500)
    print(f"✅ 提取成功")
    print(f"   总计items: {len(items)}")
    print(f"   诊断信息: {json.dumps(pdf_diag, ensure_ascii=False, indent=2)}")
    print()
    
    print("   前30个段落:")
    para_count = 0
    for i, it in enumerate(items):
        if it.get("type") == "paragraph":
            text = (it.get("text") or "").strip()
            if text:
                para_count += 1
                print(f"   [{i}] {text[:100]}")
                if para_count >= 30:
                    break
except Exception as e:
    print(f"❌ 提取失败: {e}")
    sys.exit(1)

print()

# Step 2: 区域定位
print("📍 Step 2: 定位范本区域...")
print("-" * 60)
try:
    r_start, r_end, region_diag = locate_region(items, window_pages=12)
    print(f"✅ 定位成功")
    print(f"   区域范围: {r_start} → {r_end} (共 {r_end - r_start} items)")
    print(f"   诊断信息: {json.dumps(region_diag, ensure_ascii=False, indent=2)}")
    print()
    
    print(f"   区域内的前20个段落:")
    seg = items[r_start:r_end]
    para_count = 0
    for i, it in enumerate(seg):
        if it.get("type") == "paragraph":
            text = (it.get("text") or "").strip()
            if text:
                para_count += 1
                actual_idx = r_start + i
                print(f"   [{actual_idx}] {text[:100]}")
                if para_count >= 20:
                    break
except Exception as e:
    print(f"❌ 定位失败: {e}")

print()

# Step 3: 标题检测
print("🔍 Step 3: 检测范本标题...")
print("-" * 60)
try:
    matcher = FragmentTitleMatcher()
    fragments, det_diag = detect_pdf_fragments(
        items=items,
        title_normalize_fn=matcher.normalize,
        title_to_type_fn=lambda norm: matcher.match_type(norm),
    )
    print(f"✅ 检测完成")
    print(f"   检测到fragments: {len(fragments)}")
    print(f"   诊断信息: {json.dumps(det_diag, ensure_ascii=False, indent=2)}")
    print()
    
    if fragments:
        print(f"   检测到的fragments详情:")
        for i, frag in enumerate(fragments, 1):
            print(f"   {i}. {frag['title']}")
            print(f"      - 范围: {frag['start_body_index']} → {frag['end_body_index']}")
            print(f"      - 置信度: {frag.get('confidence', 0):.2f}")
            print(f"      - 策略: {frag.get('strategy', 'N/A')}")
            print()
    else:
        print("   ❌ 未检测到任何fragments")
        print()
        print("   💡 可能原因:")
        print("      1. 区域定位失败（r_end - r_start < 3）")
        print("      2. 标题格式不匹配（编号模式、关键词）")
        print("      3. 标题分数过低（< 4.0）")
        print("      4. PDF文本提取质量问题")
        
except Exception as e:
    print(f"❌ 检测失败: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("诊断完成")
print("=" * 60)


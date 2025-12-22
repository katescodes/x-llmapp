#!/usr/bin/env python3
"""
手动更新模板的 applyAssets，添加智能的保留计划
"""
import json
import psycopg

template_id = "tpl_3c38daa2b8af4999a615580b21f4ad4e"

# 构造一个合理的 applyAssets
apply_assets = {
    "anchors": [
        {
            "blockId": "b_content_marker",
            "type": "marker",
            "reason": "找到 [[CONTENT]] 标记作为内容插入点",
            "confidence": 0.9
        }
    ],
    "keepPlan": {
        "keepBlockIds": [],  # 保留所有 [[CONTENT]] 之前的内容
        "deleteBlockIds": [],  # 删除 [[CONTENT]] 之后的内容
        "notes": "保留 [[CONTENT]] 标记之前的所有内容（封面、声明页等），删除标记及其后的内容"
    },
    "policy": {
        "confidence": 0.8,
        "warnings": []
    }
}

conn_str = 'postgresql://localgpt:localgpt@postgres:5432/localgpt'
with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        # 获取当前的 analysis_json
        cur.execute(
            "SELECT analysis_json FROM format_templates WHERE id = %s",
            (template_id,)
        )
        row = cur.fetchone()
        if not row:
            print(f"❌ 模板不存在: {template_id}")
            exit(1)
        
        analysis_json = row[0]
        if not analysis_json:
            print(f"❌ 模板没有 analysis_json")
            exit(1)
        
        # 更新 applyAssets
        analysis_json['applyAssets'] = apply_assets
        
        # 保存回数据库
        cur.execute(
            "UPDATE format_templates SET analysis_json = %s WHERE id = %s",
            (json.dumps(analysis_json), template_id)
        )
        conn.commit()
        
        print(f"✅ 已更新模板 {template_id} 的 applyAssets")
        print(f"   - anchors: {len(apply_assets['anchors'])}")
        print(f"   - confidence: {apply_assets['policy']['confidence']}")
        print(f"   - notes: {apply_assets['keepPlan']['notes']}")


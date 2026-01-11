"""
测试范本内容提取功能
验证从 blocks 提取纯文本内容是否正确
"""
from app.works.tender.snippet.doc_blocks import blocks_to_text


def test_blocks_to_text():
    """测试 blocks 转文本功能"""
    
    # 模拟范本 blocks
    sample_blocks = [
        {
            "blockId": "b1",
            "type": "p",
            "text": "投标函"
        },
        {
            "blockId": "b2",
            "type": "p",
            "text": ""
        },
        {
            "blockId": "b3",
            "type": "p",
            "text": "致：XX采购单位"
        },
        {
            "blockId": "b4",
            "type": "p",
            "text": "我方愿意参加贵方组织的（项目名称）招标，投标总价为人民币（大写）：          元（￥          元）。"
        },
        {
            "blockId": "b5",
            "type": "p",
            "text": "我方承诺在投标有效期内不修改、撤销投标文件。"
        },
        {
            "blockId": "b6",
            "type": "table",
            "rows": [
                ["项目", "内容"],
                ["投标人名称", ""],
                ["法定代表人", ""],
                ["联系电话", ""],
                ["投标日期", ""]
            ]
        },
        {
            "blockId": "b7",
            "type": "p",
            "text": "投标人：（盖章）"
        },
        {
            "blockId": "b8",
            "type": "p",
            "text": "日期：    年    月    日"
        }
    ]
    
    # 提取文本内容
    content_text = blocks_to_text(sample_blocks, include_tables=True)
    
    print("=" * 80)
    print("范本内容提取测试")
    print("=" * 80)
    print(f"\n输入 blocks 数量: {len(sample_blocks)}")
    print(f"\n提取的纯文本内容:\n")
    print(content_text)
    print(f"\n文本长度: {len(content_text)} 字符")
    print("=" * 80)
    
    # 验证关键内容是否存在
    assert "投标函" in content_text
    assert "XX采购单位" in content_text
    assert "投标总价" in content_text
    assert "[表格开始]" in content_text
    assert "投标人名称" in content_text
    assert "[表格结束]" in content_text
    assert "投标人：（盖章）" in content_text
    
    print("\n✅ 所有断言通过！")
    
    # 测试不包含表格
    content_without_tables = blocks_to_text(sample_blocks, include_tables=False)
    print(f"\n不包含表格的文本长度: {len(content_without_tables)} 字符")
    assert "[表格开始]" not in content_without_tables
    print("✅ 不包含表格模式正常！")


if __name__ == "__main__":
    test_blocks_to_text()

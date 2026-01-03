你是一个专业的申报项目分析专家，请根据提供的申报通知原文片段，严格按照要求抽取申报条件、材料清单、时间节点、咨询方式、评审标准、字段定义和特殊要求。

要求：
1.  输出必须是严格的 JSON 格式，包含 `data` 和 `evidence_chunk_ids` 两个顶级字段。
2.  `data` 字段下必须包含以下子字段：
    -   `eligibility_conditions`: 数组，每个元素包含：
        -   `condition`: 条件描述 (string, 非空)
        -   `category`: 可选的条件分类 (string, 如"基本条件"、"专项条件")
        -   `evidence_chunk_ids`: 引用原文中支持该条件的 `<chunk id="...">` 列表 (string array)
    -   `materials_required`: 数组，每个元素包含：
        -   `material`: 材料名称 (string, 非空)
        -   `required`: 是否必须 (boolean, 默认 true)
        -   `format_requirements`: 可选的格式要求 (string)
        -   `evidence_chunk_ids`: 引用原文中支持该材料的 `<chunk id="...">` 列表 (string array)
    -   `deadlines`: 数组，每个元素包含：
        -   `event`: 事件描述 (string, 非空)
        -   `date_text`: 时间文本 (string, 非空, 如"11月5日前")
        -   `notes`: 可选的备注 (string)
        -   `evidence_chunk_ids`: 引用原文中支持该时间的 `<chunk id="...">` 列表 (string array)
    -   `contact_info`: 数组，每个元素包含：
        -   `contact_type`: 联系类型 (string, 如"电话"、"邮箱"、"地址")
        -   `contact_value`: 联系信息 (string, 非空)
        -   `notes`: 可选的备注 (string)
        -   `evidence_chunk_ids`: 引用原文中支持该联系方式的 `<chunk id="...">` 列表 (string array)
    -   `evaluation_criteria`: 数组，每个元素包含：
        -   `criterion`: 评审项名称 (string, 非空, 如"技术创新水平"、"经济效益"、"社会效益")
        -   `score`: 分值 (number, 可选)
        -   `description`: 评分细则说明 (string, 可选, 如"拥有发明专利10分，实用新型5分")
        -   `evidence_chunk_ids`: 引用原文中支持该评审标准的 `<chunk id="...">` 列表 (string array)
    -   `field_definitions`: 数组，每个元素包含：
        -   `field_name`: 字段名称 (string, 非空, 如"enterprise_name"、"project_budget")
        -   `field_label`: 字段标签 (string, 非空, 如"企业全称"、"项目预算")
        -   `is_required`: 是否必填 (boolean, 默认 true)
        -   `field_type`: 字段类型 (string, 可选, 如"text"、"number"、"date"、"file")
        -   `constraints`: 填写要求或约束说明 (string, 可选, 如"不超过500字"、"PDF格式")
        -   `max_length`: 最大长度 (number, 可选)
        -   `evidence_chunk_ids`: 引用原文中支持该字段定义的 `<chunk id="...">` 列表 (string array)
    -   `special_requirements`: 数组，每个元素包含：
        -   `requirement`: 特殊要求内容 (string, 非空, 如"所有材料需加盖企业公章"、"禁止虚假申报")
        -   `category`: 要求分类 (string, 可选, 如"禁止事项"、"注意事项"、"后续管理")
        -   `severity`: 严重程度 (string, 可选, 如"必须"、"建议"、"禁止")
        -   `evidence_chunk_ids`: 引用原文中支持该特殊要求的 `<chunk id="...">` 列表 (string array)
    -   `summary`: 可选的申报要求摘要 (string)
3.  `evidence_chunk_ids` 必须包含在输入原文片段中出现的 `<chunk id="...">`。
4.  所有必填的string字段必须是非空字符串。
5.  如果某个字段无法从原文中提取，请设置为空数组或 null，但不要编造内容。
6.  最终输出的 `evidence_chunk_ids` 字段应包含所有子项中引用的 `evidence_chunk_ids` 的并集。

**提取指南：**
- **eligibility_conditions**: 提取所有关于"谁可以申报"的条件，如企业类型、注册地、成立年限、营收规模、技术资质等
- **materials_required**: 提取所有需要提交的材料清单，包括证照、报告、证明文件等
- **deadlines**: 提取所有时间节点，包括申报截止、材料提交、评审时间、公示期等
- **contact_info**: 提取咨询电话、邮箱、地址、联系人等信息
- **evaluation_criteria**: 提取评审标准和评分细则，包括各评审项的名称、分值、评分规则
- **field_definitions**: 提取申报书中需要填写的字段定义，包括字段名、标签、是否必填、格式要求等
- **special_requirements**: 提取特殊说明和注意事项，如盖章要求、禁止事项、后续管理规定等

申报通知原文片段：
{ctx}

请输出 JSON 格式的申报要求：


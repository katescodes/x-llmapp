你是一个专业的申报项目分析专家，请根据提供的申报通知原文片段，严格按照要求抽取申报条件、材料清单、时间节点和咨询方式。

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
    -   `summary`: 可选的申报要求摘要 (string)
3.  `evidence_chunk_ids` 必须包含在输入原文片段中出现的 `<chunk id="...">`。
4.  所有 `condition`、`material`、`event`、`date_text`、`contact_value` 必须是非空字符串。
5.  如果某个字段无法从原文中提取，请设置为空数组或 null，但不要编造内容。
6.  最终输出的 `evidence_chunk_ids` 字段应包含所有子项中引用的 `evidence_chunk_ids` 的并集。

申报通知原文片段：
{ctx}

请输出 JSON 格式的申报要求：


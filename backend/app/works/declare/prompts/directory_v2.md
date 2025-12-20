你是一个专业的申报文档分析专家，请根据提供的申报通知原文片段（包括通知正文和附件模板），严格抽取申报书应提交的目录结构。

要求：
1.  输出必须是严格的 JSON 格式，包含 `data` 和 `evidence_chunk_ids` 两个顶级字段。
2.  `data` 字段下必须包含一个 `nodes` 数组，每个元素代表一个目录章节。
3.  每个 `node` 必须包含以下字段：
    -   `title`: 章节标题 (string, 非空)
    -   `level`: 章节层级 (integer, 1-6)
    -   `order_no`: 章节序号 (integer, 必须是整数，用于排序)
    -   `parent_ref`: 可选的父节点标题或本地ID (string, 可为空，用于辅助构建树结构)
    -   `required`: 该章节是否为必须提交 (boolean, 无法确定时默认为 true)
    -   `notes`: 可选的说明或备注 (string, 可为空)
    -   `evidence_chunk_ids`: 引用原文中支持该章节内容的 `<chunk id="...">` 列表 (string array, 必须来自输入片段的 chunk id)
4.  `evidence_chunk_ids` 必须包含在输入原文片段中出现的 `<chunk id="...">`。
5.  `nodes` 数组中的 `level` 必须是 1 到 6 之间的整数。
6.  `order_no` 必须是整数。
7.  `title` 必须是非空字符串。
8.  如果无法明确判断 `required` 字段，请默认设置为 `true`。
9.  `parent_ref` 字段可以为空，后续会根据 `level` 和 `order_no` 自动构建树结构。
10. 最终输出的 `evidence_chunk_ids` 字段应包含所有 `nodes` 中引用的 `evidence_chunk_ids` 的并集。
11. 重点关注申报通知中的"附件"、"申报书模板"、"申报书格式"等部分，这些通常包含目录结构信息。
12. 目录章节通常使用"一、""（一）""1."等编号，请准确识别层级关系。

申报通知原文片段：
{ctx}

请输出 JSON 格式的申报书目录：


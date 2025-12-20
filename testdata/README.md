# 测试数据说明

本目录包含 Smoke 测试所需的样例文件。

## 文件列表

| 文件 | 大小 | 说明 | 用途 |
|------|------|------|------|
| `tender_sample.pdf` | 752 KB | 招标文件样例 | 用于测试招标文件上传和解析 |
| `bid_sample.docx` | 33 MB | 投标文件样例 | 用于测试投标文件上传和审查 |
| `rules.yaml` | 254 bytes | 自定义规则样例 | 用于测试自定义规则功能（当前为空） |

## 数据来源

这些文件是从现有的 `storage/attachments/` 和 `data/tender_assets/` 目录复制而来，确保测试使用真实的业务数据。

## 使用方式

### 默认使用

直接运行测试脚本，会自动使用这些文件：

```bash
python scripts/smoke/tender_e2e.py
```

### 自定义文件

通过环境变量指定其他测试文件：

```bash
TENDER_FILE=/path/to/custom/tender.pdf \
BID_FILE=/path/to/custom/bid.docx \
python scripts/smoke/tender_e2e.py
```

## 添加新的测试数据

如需添加新的测试文件：

1. 将文件放入此目录
2. 通过环境变量指定文件路径
3. 运行测试验证

```bash
# 复制新文件
cp /path/to/new/file.pdf testdata/

# 使用新文件测试
TENDER_FILE=testdata/file.pdf python scripts/smoke/tender_e2e.py
```

## 注意事项

- 测试文件应具有代表性，能够覆盖常见场景
- 避免使用过大的文件（建议 < 50 MB）
- 确保文件格式正确（PDF/DOCX）
- 敏感信息应脱敏处理

## 维护

定期检查和更新测试数据：
- 确保文件完整性
- 更新过时的样例
- 添加新场景的样例

---

**创建日期**: 2025-12-19  
**维护**: 开发团队





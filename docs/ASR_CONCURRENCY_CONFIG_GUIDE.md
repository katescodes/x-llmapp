# ASR 并发优化配置指南

## 🎯 针对自建Whisper + nginx架构

您的系统架构：
```
Backend → nginx → Whisper服务（GPU独占）
```

**优化策略**：我们只能在Backend端控制并发，无法修改Whisper服务本身。

---

## ⚙️ 配置参数说明

### 1. ASR_MAX_CONCURRENT（最大并发数）

**作用**：控制Backend同时向Whisper服务发起的转录请求数

**推荐配置流程**：

#### 阶段1：保守起步（1天）
```bash
ASR_MAX_CONCURRENT=1
```
- ✅ 最安全，不会OOM
- ✅ 观察Whisper服务的显存使用模式
- ⚠️ 多用户时会排队

#### 阶段2：谨慎提升（3-7天）
```bash
ASR_MAX_CONCURRENT=2
```
- 观察：
  - 是否仍有OOM？
  - GPU显存峰值是多少？
  - 转录成功率如何？

#### 阶段3：最优配置（长期）
```bash
# 如果阶段2稳定，可以尝试
ASR_MAX_CONCURRENT=3

# 或保持保守
ASR_MAX_CONCURRENT=2
```

**计算公式**：
```
最大并发数 = (GPU总显存 - 系统预留) / 单个转录峰值显存
```

根据您的RTX 3090 24GB：
```
假设单个转录峰值：6GB（包含模型和推理）
系统预留：6GB
可用：24 - 6 = 18GB
理论最大：18 / 6 = 3

但实际建议：2（留有余地）
```

### 2. ASR_MAX_RETRIES（最大重试次数）

```bash
ASR_MAX_RETRIES=3
```

**说明**：
- OOM错误会自动重试
- 每次重试前会等待（让GPU有时间释放显存）
- 3次是合理的平衡值

### 3. ASR_RETRY_DELAY（重试延迟）

```bash
ASR_RETRY_DELAY=10  # 秒
```

**智能延迟策略**（已自动实现）：
- 普通错误：5秒、10秒、20秒（指数退避）
- OOM错误：10秒、30秒、90秒（延长等待）
- 最近30秒内有OOM：自动延迟15秒启动新任务

### 4. ASR_REQUEST_TIMEOUT（请求超时）

```bash
ASR_REQUEST_TIMEOUT=300  # 秒
```

根据音频长度调整：
- 1分钟音频：30-60秒
- 5分钟音频：120-180秒
- 10分钟音频：300秒

---

## 🔧 当前优化功能

### 1. 队列管理
```python
最大排队数 = ASR_MAX_CONCURRENT × 10
```

示例：
- 并发数=2，最多排队20个任务
- 超过20个会被拒绝，提示"服务繁忙"

### 2. 智能延迟
- 检测到最近OOM → 新任务延迟15秒启动
- 给GPU时间释放显存
- 避免雪崩效应

### 3. OOM特殊处理
- OOM错误延迟更长（3倍）
- 记录最后OOM时间
- 自动调整后续任务节奏

### 4. 详细统计
```bash
curl -H "Authorization: Bearer TOKEN" \
  http://your-domain/api/recordings/stats/asr-concurrency
```

返回示例：
```json
{
  "max_concurrent": 2,
  "active_tasks": 1,
  "queued_tasks": 3,
  "total_tasks": 100,
  "failed_tasks": 5,
  "rejected_tasks": 2,
  "oom_errors": 3,
  "last_oom": "2025-01-29T10:30:00",
  "success_rate": "95.0%",
  "queue_usage": "3/20 (15%)"
}
```

---

## 📊 监控和诊断

### 1. 实时监控命令

**监控GPU**：
```bash
watch -n 1 nvidia-smi
```

观察指标：
- GPU利用率
- 显存使用量
- 显存峰值

**监控Backend日志**：
```bash
docker logs -f backend | grep "ASR并发"
```

关键日志：
```
[ASR并发] 开始转录 task_id=xxx active=1/2 queued=3
[ASR并发] 显存不足 task_id=xxx oom_count=1
[ASR并发] 检测到最近OOM，延迟15秒后开始
[ASR并发] 队列已满，拒绝任务
```

### 2. 问题诊断流程

#### 问题：仍然频繁OOM

**步骤1：检查配置**
```bash
cat .env | grep ASR_MAX_CONCURRENT
```

**步骤2：降低并发**
```bash
echo "ASR_MAX_CONCURRENT=1" >> .env
docker-compose restart backend
```

**步骤3：查看统计**
```bash
curl -H "Authorization: Bearer TOKEN" \
  http://your-domain/api/recordings/stats/asr-concurrency
```

**步骤4：检查Whisper服务**
```bash
# Whisper服务是否正常？
curl http://whisper-service-url/health

# 显存是否真的释放？
docker exec -it whisper-container nvidia-smi
```

#### 问题：转录太慢，排队严重

**原因**：并发数太低

**解决**：
```bash
# 前提：确认GPU有余量且无OOM
echo "ASR_MAX_CONCURRENT=2" >> .env
docker-compose restart backend
```

#### 问题：偶尔出现OOM，但大多数成功

**这是正常的**！说明配置接近上限。

**优化**：
1. 保持当前并发数
2. 依靠重试机制处理偶发OOM
3. 监控OOM频率：
   - <5%：可接受
   - 5-10%：考虑降低并发
   - >10%：必须降低并发

---

## 🎯 推荐配置（RTX 3090 24GB）

### 方案A：保守稳定（推荐）
```bash
ASR_MAX_CONCURRENT=1
ASR_MAX_RETRIES=3
ASR_RETRY_DELAY=10
ASR_REQUEST_TIMEOUT=300
```

**特点**：
- ✅ 几乎不会OOM
- ✅ 系统稳定
- ⚠️ 吞吐量较低
- **适用**：用户数少、稳定性优先

### 方案B：平衡性能（生产推荐）
```bash
ASR_MAX_CONCURRENT=2
ASR_MAX_RETRIES=3
ASR_RETRY_DELAY=10
ASR_REQUEST_TIMEOUT=300
```

**特点**：
- ✅ 性能翻倍
- ✅ OOM风险可控
- ⚠️ 需要监控
- **适用**：中等用户数、性能要求较高

### 方案C：激进高性能（慎用）
```bash
ASR_MAX_CONCURRENT=3
ASR_MAX_RETRIES=5
ASR_RETRY_DELAY=15
ASR_REQUEST_TIMEOUT=300
```

**特点**：
- ✅ 最高吞吐量
- ⚠️ OOM风险高
- ⚠️ 需要充分测试
- **适用**：高并发场景、Whisper服务经过优化

---

## 🚀 实施步骤

### 第1步：应用配置

```bash
# 编辑 .env 文件
nano .env

# 修改为：
ASR_MAX_CONCURRENT=1
ASR_MAX_RETRIES=3
ASR_RETRY_DELAY=10

# 重启服务
docker-compose restart backend
```

### 第2步：测试验证

```bash
# 单个转录测试
# 在前端录音并观察

# 并发测试（模拟2个用户同时转录）
# 开两个浏览器窗口，同时录音
```

### 第3步：监控观察（1-3天）

```bash
# 每天检查统计
curl -H "Authorization: Bearer TOKEN" \
  http://your-domain/api/recordings/stats/asr-concurrency

# 关注指标：
# - oom_errors：OOM次数
# - success_rate：成功率
# - rejected_tasks：被拒绝任务数
```

### 第4步：调优

根据监控数据：
- **成功率>95% 且无排队**：配置合适 ✅
- **成功率>95% 但排队多**：可提高并发 ⬆️
- **成功率<90%**：必须降低并发 ⬇️
- **频繁OOM**：立即降到1 ⚠️

---

## 💡 最佳实践

### 1. 渐进式调优
```
Week 1: ASR_MAX_CONCURRENT=1（观察基线）
Week 2: ASR_MAX_CONCURRENT=2（如果稳定）
Week 3: 评估是否继续提升
```

### 2. 监控告警

设置告警规则：
```python
if oom_errors > 5 in last_hour:
    send_alert("ASR OOM频繁，建议降低并发")

if rejected_tasks > 10 in last_hour:
    send_alert("ASR队列频繁满载，建议提高并发")
```

### 3. 定期检查

每周检查：
- GPU显存使用趋势
- OOM错误频率
- 用户反馈

### 4. 文档化配置

记录配置变更：
```
2025-01-29: ASR_MAX_CONCURRENT=1 → 2
原因：系统稳定运行1周，无OOM
结果：待观察
```

---

## ❓ 常见问题

### Q1: 为什么有20GB空闲还是OOM？

A: Whisper服务报告的显存和系统看到的可能不一致，原因：
1. Whisper服务缓存未清理
2. CUDA上下文未释放
3. 显存碎片化

**解决**：通过降低并发避免问题

### Q2: 并发数=1还是OOM？

A: 说明Whisper服务本身有问题：
1. 重启Whisper服务
2. 检查Whisper服务日志
3. 联系Whisper服务管理员

### Q3: 如何判断最优并发数？

A: 运行压力测试：
```bash
# 模拟10个用户同时转录
# 观察：
# - 哪个并发数成功率最高
# - 哪个并发数平均延迟最低
```

### Q4: 能否动态调整并发数？

A: 当前不支持，但可以手动调整后重启。
未来可以实现自适应并发控制。

---

## 📞 获取帮助

如果仍然遇到问题：

1. **收集信息**：
   ```bash
   nvidia-smi > gpu_status.txt
   curl http://your-domain/api/recordings/stats/asr-concurrency > asr_stats.json
   docker logs backend --tail 500 > backend.log
   ```

2. **提供给管理员**：
   - GPU状态
   - ASR统计
   - Backend日志
   - 错误截图

3. **临时缓解**：
   - 降低并发到1
   - 重启服务
   - 错峰使用

---

## 📝 总结

**核心原则**：
1. ✅ **从保守开始**：并发=1
2. ✅ **数据驱动**：监控后调整
3. ✅ **稳定优先**：宁可慢，不可错
4. ✅ **持续优化**：渐进式提升

**期望效果**：
- OOM错误率 <5%
- 转录成功率 >95%
- 用户等待时间 <10秒

**立即行动**：
```bash
# 1. 修改配置
echo "ASR_MAX_CONCURRENT=1" >> .env

# 2. 重启服务
docker-compose restart backend

# 3. 测试转录

# 4. 监控1-3天

# 5. 根据数据调整
```


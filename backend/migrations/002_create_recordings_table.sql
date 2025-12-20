-- 创建录音记录表
CREATE TABLE IF NOT EXISTS voice_recordings (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    
    -- 基础信息
    title VARCHAR(255),
    filename VARCHAR(255),
    duration INTEGER,  -- 秒
    file_size BIGINT,  -- 字节
    audio_format VARCHAR(20),  -- webm, mp3, wav, m4a
    
    -- 转写内容
    transcript TEXT NOT NULL,
    word_count INTEGER,
    language VARCHAR(10) DEFAULT 'zh',  -- 检测到的语言
    
    -- 知识库关联
    kb_id VARCHAR(36),  -- NULL 表示未入库
    doc_id VARCHAR(36),  -- 对应的文档ID
    import_status VARCHAR(20) DEFAULT 'pending',
    -- 'pending' (待处理), 'importing' (导入中), 'imported' (已入库), 'failed' (失败)
    
    -- 元数据
    tags TEXT[],  -- 标签数组
    category VARCHAR(50),  -- 文档分类
    notes TEXT,  -- 备注
    
    -- 音频文件（可选保留）
    audio_path VARCHAR(500),  -- 音频文件存储路径
    keep_audio BOOLEAN DEFAULT FALSE,  -- 是否保留音频
    
    -- 时间戳信息（如果启用）
    has_timestamps BOOLEAN DEFAULT FALSE,
    timestamps_data JSONB,  -- 时间戳详细数据
    
    -- 时间记录
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    imported_at TIMESTAMP,  -- 导入知识库的时间
    deleted_at TIMESTAMP,  -- 软删除
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE SET NULL,
    CONSTRAINT check_import_status CHECK (
        import_status IN ('pending', 'importing', 'imported', 'failed')
    )
);

-- 创建索引
CREATE INDEX idx_recordings_user ON voice_recordings(user_id);
CREATE INDEX idx_recordings_kb ON voice_recordings(kb_id);
CREATE INDEX idx_recordings_status ON voice_recordings(import_status);
CREATE INDEX idx_recordings_created ON voice_recordings(created_at DESC);
CREATE INDEX idx_recordings_deleted ON voice_recordings(deleted_at) WHERE deleted_at IS NULL;

-- 全文搜索索引（转写内容）
CREATE INDEX idx_recordings_transcript_search ON voice_recordings 
USING gin(to_tsvector('english', transcript));

-- 触发器：自动更新 updated_at
CREATE OR REPLACE FUNCTION update_recording_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_recordings_updated_at
    BEFORE UPDATE ON voice_recordings
    FOR EACH ROW
    EXECUTE FUNCTION update_recording_updated_at();

-- 录音统计视图
CREATE OR REPLACE VIEW recording_stats AS
SELECT 
    user_id,
    COUNT(*) as total_recordings,
    COUNT(CASE WHEN import_status = 'imported' THEN 1 END) as imported_count,
    COUNT(CASE WHEN import_status = 'pending' THEN 1 END) as pending_count,
    SUM(duration) as total_duration_seconds,
    SUM(file_size) as total_file_size_bytes,
    MAX(created_at) as last_recording_at
FROM voice_recordings
WHERE deleted_at IS NULL
GROUP BY user_id;

-- 注释说明
COMMENT ON TABLE voice_recordings IS '录音记录表：存储所有录音的转写结果和元数据';
COMMENT ON COLUMN voice_recordings.import_status IS '导入状态：pending(待处理), importing(导入中), imported(已入库), failed(失败)';
COMMENT ON COLUMN voice_recordings.keep_audio IS '是否保留原始音频文件（默认不保留，仅保存转写文字）';


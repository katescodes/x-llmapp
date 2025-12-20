-- 创建语音转文本API配置表
CREATE TABLE IF NOT EXISTS asr_configs (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    api_url VARCHAR(500) NOT NULL,
    api_key VARCHAR(255),
    model_name VARCHAR(100) DEFAULT 'whisper',
    response_format VARCHAR(50) DEFAULT 'verbose_json',
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    
    -- 其他配置参数（JSON格式）
    extra_params JSONB DEFAULT '{}'::jsonb,
    
    -- 测试状态
    last_test_at TIMESTAMP,
    last_test_status VARCHAR(20),  -- 'success', 'failed'
    last_test_message TEXT,
    
    -- 使用统计
    usage_count INTEGER DEFAULT 0,
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_test_status CHECK (
        last_test_status IS NULL OR last_test_status IN ('success', 'failed')
    )
);

-- 创建索引
CREATE INDEX idx_asr_configs_active ON asr_configs(is_active);
CREATE INDEX idx_asr_configs_default ON asr_configs(is_default);

-- 触发器：确保只有一个默认配置
CREATE OR REPLACE FUNCTION ensure_single_default_asr()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_default = TRUE THEN
        -- 将其他配置的默认状态设为 false
        UPDATE asr_configs
        SET is_default = FALSE
        WHERE id != NEW.id AND is_default = TRUE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_single_default_asr
    BEFORE INSERT OR UPDATE ON asr_configs
    FOR EACH ROW
    WHEN (NEW.is_default = TRUE)
    EXECUTE FUNCTION ensure_single_default_asr();

-- 触发器：自动更新 updated_at
CREATE OR REPLACE FUNCTION update_asr_config_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_asr_configs_updated_at
    BEFORE UPDATE ON asr_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_asr_config_updated_at();

-- 插入默认配置（基于您提供的API）
INSERT INTO asr_configs (id, name, api_url, model_name, response_format, is_active, is_default)
VALUES (
    'asr-default-001',
    '默认语音转文本API',
    'https://ai.yglinker.com:6399/v1/audio/transcriptions',
    'whisper',
    'verbose_json',
    TRUE,
    TRUE
)
ON CONFLICT (id) DO NOTHING;

-- 注释说明
COMMENT ON TABLE asr_configs IS 'ASR API配置表：存储语音转文本API的配置信息';
COMMENT ON COLUMN asr_configs.is_default IS '是否为默认配置（同时只能有一个默认配置）';
COMMENT ON COLUMN asr_configs.extra_params IS '额外参数（JSON格式），如 {"language": "zh", "temperature": 0}';


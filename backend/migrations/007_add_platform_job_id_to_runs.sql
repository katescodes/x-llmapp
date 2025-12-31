-- Migration: Add platform_job_id to tender_runs
-- Purpose: GOAL-2 统一状态源 - platform job 为事实源

-- Add platform_job_id column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'tender_runs' AND column_name = 'platform_job_id'
    ) THEN
        ALTER TABLE tender_runs ADD COLUMN platform_job_id TEXT NULL;
        CREATE INDEX IF NOT EXISTS idx_tender_runs_platform_job_id ON tender_runs(platform_job_id);
    END IF;
END $$;

-- Add comment
COMMENT ON COLUMN tender_runs.platform_job_id IS 'Related platform job ID for unified status tracking';







/**
 * 录音相关类型定义
 */

export type RecordingStatus = 'pending' | 'importing' | 'imported' | 'failed';

export interface Recording {
  id: string;
  user_id: string;
  title: string;
  filename: string;
  duration: number;
  file_size: number;
  audio_format: string;
  transcript: string;
  word_count: number;
  language: string;
  kb_id?: string;
  kb_name?: string;
  doc_id?: string;
  import_status: RecordingStatus;
  tags?: string[];
  category?: string;
  notes?: string;
  created_at: string;
  imported_at?: string;
  audio_path?: string;
  keep_audio?: boolean;
}

export interface RecordingListResponse {
  items: Recording[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ImportRecordingRequest {
  kb_id?: string;
  new_kb_name?: string;
  title?: string;
  category?: string;
  tags?: string[];
  notes?: string;
}


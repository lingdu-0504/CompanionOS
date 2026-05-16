/**
 * 小说创作相关类型定义
 */

export interface NovelProject {
  id: string;
  name: string;
  description: string;
  genre: string;
  target_word_count: number;
  current_word_count: number;
  progress: number;
  chapter_count: number;
  created_at: string;
  updated_at: string;
  config: Record<string, any>;
  metadata: Record<string, any>;
}

export interface NovelChapter {
  id: string;
  number: number;
  title: string;
  content: string;
  word_count: number;
  created_at: string;
  updated_at: string;
  status: 'draft' | 'reviewing' | 'published';
  metadata: Record<string, any>;
}

export interface GenerationTask {
  id: string;
  project_id: string;
  type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
  result?: Record<string, any>;
}

export interface PlatformConfig {
  platform: string;
  username: string;
  password: string;
  auto_publish: boolean;
  publish_schedule?: string;
}

export interface WordCountPlan {
  target: number;
  min: number;
  max: number;
  tolerance: number;
  tolerance_percent: number;
}

export interface ConsistencyReport {
  is_consistent: boolean;
  conflicts: Array<{
    fact_id: string;
    fact_content: string;
    fact_type: string;
    source_chapter: number;
    confidence: number;
  }>;
  warnings: any[];
  fact_count: number;
}

export interface GenerationResult {
  success: boolean;
  project_id: string;
  chapter_number: number;
  title: string;
  content: string;
  word_count: number;
  target_word_count: number;
  consistency_report: ConsistencyReport;
}


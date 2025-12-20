/**
 * LLM Orchestrator 相关类型定义
 */

export type DetailLevel = 'brief' | 'normal' | 'detailed';

export interface ChatSection {
  id: string;
  title: string;
  markdown: string;
  collapsed: boolean;
}

export interface OrchestratedResponse {
  sections: ChatSection[];
  followups?: string[];
  meta?: {
    intent?: string;
    detail_level?: DetailLevel;
    blueprint_modules?: string[];
    assumptions?: string[];
  };
}


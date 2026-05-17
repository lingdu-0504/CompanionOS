/**
 * 小说创作API服务
 */
import type { NovelProject, NovelChapter, GenerationTask, GenerationResult } from '../types/novel';

const API_BASE = 'http://localhost:18080/api';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.statusText}`);
  }

  return response.json();
}

// 项目管理
export const novelApi = {
  // 获取所有项目
  getProjects: async (): Promise<NovelProject[]> => {
    return request<NovelProject[]>('/novel/projects');
  },

  // 获取单个项目
  getProject: async (projectId: string): Promise<NovelProject> => {
    return request<NovelProject>(`/novel/projects/${projectId}`);
  },

  // 创建项目
  createProject: async (data: {
    name: string;
    description?: string;
    genre?: string;
    target_word_count?: number;
    config?: Record<string, any>;
  }): Promise<NovelProject> => {
    return request<NovelProject>('/novel/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 更新项目
  updateProject: async (projectId: string, data: Partial<NovelProject>): Promise<NovelProject> => {
    return request<NovelProject>(`/novel/projects/${projectId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  // 删除项目
  deleteProject: async (projectId: string): Promise<void> => {
    return request(`/novel/projects/${projectId}`, {
      method: 'DELETE',
    });
  },

  // 获取项目章节
  getChapters: async (projectId: string): Promise<NovelChapter[]> => {
    return request<NovelChapter[]>(`/novel/projects/${projectId}/chapters`);
  },

  // 获取单个章节
  getChapter: async (projectId: string, chapterNumber: number): Promise<NovelChapter> => {
    return request<NovelChapter>(`/novel/projects/${projectId}/chapters/${chapterNumber}`);
  },

  // 创建/更新章节
  saveChapter: async (projectId: string, data: {
    number: number;
    title: string;
    content?: string;
  }): Promise<NovelChapter> => {
    return request<NovelChapter>(`/novel/projects/${projectId}/chapters`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 生成章节
  generateChapter: async (projectId: string, data: {
    chapter_number: number;
    title: string;
    target_words?: number;
  }): Promise<GenerationResult> => {
    return request<GenerationResult>(`/novel/projects/${projectId}/generate`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 获取任务
  getTasks: async (projectId?: string): Promise<GenerationTask[]> => {
    const query = projectId ? `?project_id=${projectId}` : '';
    return request<GenerationTask[]>(`/novel/tasks${query}`);
  },

  // 获取任务状态
  getTaskStatus: async (taskId: string): Promise<GenerationTask> => {
    return request<GenerationTask>(`/novel/tasks/${taskId}`);
  },

  // 取消任务
  cancelTask: async (taskId: string): Promise<void> => {
    return request(`/novel/tasks/${taskId}/cancel`, {
      method: 'POST',
    });
  },

  // 发布章节
  publishChapter: async (projectId: string, data: {
    chapter_number: number;
    platform: string;
    config?: Record<string, any>;
  }): Promise<{ success: boolean; message?: string }> => {
    return request(`/novel/projects/${projectId}/publish`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 获取支持的平台
  getPlatforms: async (): Promise<Array<{ id: string; name: string; base_url: string }>> => {
    return request('/novel/platforms');
  },

  // 风格管理
  getStyles: async (): Promise<any[]> => {
    const result = await request<{ styles: any[] }>('/novel/styles');
    return result.styles;
  },

  getStyle: async (styleId: string): Promise<any> => {
    return request(`/novel/styles/${styleId}`);
  },

  createStyle: async (data: {
    name: string;
    description?: string;
    writing_style?: string;
    tone_style?: string;
    narrative_mode?: string;
    features?: Record<string, any>;
    keywords?: string[];
    examples?: string[];
  }): Promise<any> => {
    return request('/novel/styles', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  updateStyle: async (styleId: string, data: Record<string, any>): Promise<any> => {
    return request(`/novel/styles/${styleId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  deleteStyle: async (styleId: string): Promise<{ success: boolean }> => {
    return request(`/novel/styles/${styleId}`, {
      method: 'DELETE',
    });
  },

  analyzeTextStyle: async (text: string): Promise<{ analysis: any }> => {
    return request('/novel/styles/analyze', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
  },

  generateStylePrompt: async (styleId: string, context?: Record<string, any>): Promise<{ prompt: string }> => {
    return request(`/novel/styles/${styleId}/prompt`, {
      method: 'POST',
      body: JSON.stringify(context),
    });
  },

  applyStyleToProject: async (projectId: string, styleId: string): Promise<{ success: boolean }> => {
    return request(`/novel/projects/${projectId}/style`, {
      method: 'POST',
      body: JSON.stringify({ style_id: styleId }),
    });
  },

  // 智能创作
  createCreationPlan: async (projectId: string, data: {
    total_chapters?: number;
    start_chapter?: number;
    words_per_chapter?: number;
    narrative_arc?: string;
    auto_publish?: boolean;
    publish_platform?: string;
    publish_schedule?: Record<string, any>;
  }): Promise<{ success: boolean; plan: any }> => {
    return request(`/novel/projects/${projectId}/plan`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  getCreationPlan: async (projectId: string): Promise<any> => {
    return request(`/novel/projects/${projectId}/plan`);
  },

  executeCreationPlan: async (projectId: string, startChapter?: number, endChapter?: number): Promise<{ success: boolean; result: any }> => {
    return request(`/novel/projects/${projectId}/plan/execute`, {
      method: 'POST',
      body: JSON.stringify({ start_chapter: startChapter, end_chapter: endChapter }),
    });
  },

  addChapterOutline: async (projectId: string, data: {
    number: number;
    title: string;
    summary?: string;
    key_events?: string[];
    character_arcs?: Record<string, any>;
    word_count?: number;
  }): Promise<{ success: boolean; outline: any }> => {
    return request(`/novel/projects/${projectId}/outlines`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  getChapterOutlines: async (projectId: string): Promise<{ outlines: any[] }> => {
    return request(`/novel/projects/${projectId}/outlines`);
  },

  analyzeCreationQuality: async (projectId: string): Promise<{ success: boolean; quality: any }> => {
    return request(`/novel/projects/${projectId}/quality`);
  },

  getAutomationLevels: async (): Promise<any> => {
    return request('/novel/automation-levels');
  },
};


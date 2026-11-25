import type { ChatResponse, HealthResponse } from '../types/chat';

const rawBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const API_BASE_URL = rawBaseUrl.replace(/\/+$/, '');

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data?.detail === 'string' && data.detail.trim()) {
      return data.detail;
    }
  } catch {
    // Ignore non-JSON error body
  }
  return `Request failed with status ${response.status}`;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response));
  }
  return (await response.json()) as HealthResponse;
}

export interface SendChatParams {
  sessionId: string;
  message: string;
  systemPrompt?: string;
}

export async function sendChatMessage(params: SendChatParams): Promise<ChatResponse> {
  const body: Record<string, string> = {
    session_id: params.sessionId,
    message: params.message,
  };
  const trimmedPrompt = params.systemPrompt?.trim();
  if (trimmedPrompt) {
    body.system_prompt = trimmedPrompt;
  }

  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as ChatResponse;
}

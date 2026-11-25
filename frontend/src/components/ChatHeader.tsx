import type { HealthResponse } from '../types/chat';

interface ChatHeaderProps {
  sessionId: string;
  health: HealthResponse | null;
  healthStatus: 'checking' | 'online' | 'offline';
  isSystemPromptOpen: boolean;
  hasCustomSystemPrompt: boolean;
  onToggleSystemPrompt: () => void;
  onNewSession: () => void;
}

export function ChatHeader({
  sessionId,
  health,
  healthStatus,
  isSystemPromptOpen,
  hasCustomSystemPrompt,
  onToggleSystemPrompt,
  onNewSession,
}: ChatHeaderProps) {
  return (
    <header className="chat-header">
      <div className="header-brand">
        <div className="brand-mark" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 2L14.8 9.2L22 12L14.8 14.8L12 22L9.2 14.8L2 12L9.2 9.2L12 2Z"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <div>
          <h1 className="brand-title">Lyftr AI Chat</h1>
          <p className="brand-subtitle">Resilient LLM Gateway</p>
        </div>
      </div>

      <div className="header-controls">
        <div
          className={`status-pill status-${healthStatus}`}
          title={
            health
              ? `Keys configured: ${health.keys_configured} | Cache: ${health.cache_enabled ? 'enabled' : 'disabled'}`
              : 'Gateway status'
          }
        >
          <span className="status-dot" aria-hidden="true" />
          <span>
            {healthStatus === 'online' && health
              ? `Gateway OK · ${health.keys_configured} keys${health.cache_enabled ? ' · Cache' : ''}`
              : healthStatus === 'checking'
                ? 'Connecting…'
                : 'Gateway Unavailable'}
          </span>
        </div>

        <span className="session-pill" title={`Current session: ${sessionId}`}>
          Session: <code>{sessionId.slice(0, 12)}</code>
        </span>

        <button
          type="button"
          className={`btn-ghost ${isSystemPromptOpen ? 'active' : ''}`}
          onClick={onToggleSystemPrompt}
          aria-expanded={isSystemPromptOpen}
        >
          System Prompt
          {hasCustomSystemPrompt && <span className="dot-indicator" aria-label="Configured" />}
        </button>

        <button type="button" className="btn-secondary" onClick={onNewSession}>
          New Session
        </button>
      </div>
    </header>
  );
}

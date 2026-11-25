interface EmptyStateProps {
  onSelectPrompt: (prompt: string) => void;
}

const STARTER_PROMPTS = [
  'What is the capital of France?',
  'Explain key failover and response caching in 3 bullet points.',
  'My favorite programming language is Python.',
];

export function EmptyState({ onSelectPrompt }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="empty-badge">LiteLLM · SQLite Persistence · Multi-Key Failover</div>
      <h2 className="empty-title">Start a resilient conversation</h2>
      <p className="empty-description">
        Every turn reconstructs context from SQLite, routes across configured API keys with
        automatic 429/5xx failover, and caches identical prompt chains via LiteLLM.
      </p>

      <div className="feature-grid">
        <div className="feature-card">
          <div className="feature-label">LIVE_INFERENCE</div>
          <p>Fresh provider completion with active key attribution and fallback telemetry.</p>
        </div>
        <div className="feature-card">
          <div className="feature-label">LLM_CACHE</div>
          <p>Zero-provider-cost cache hits keyed by model + full message list.</p>
        </div>
        <div className="feature-card">
          <div className="feature-label">Multi-Turn Memory</div>
          <p>Backend-managed conversation history isolated per session ID.</p>
        </div>
      </div>

      <div className="starter-prompts">
        <span className="starter-label">Try a prompt:</span>
        <div className="starter-list">
          {STARTER_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              className="starter-chip"
              onClick={() => onSelectPrompt(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

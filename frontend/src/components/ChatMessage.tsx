import { useState } from 'react';
import type { UIMessage } from '../types/chat';

interface ChatMessageProps {
  message: UIMessage;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard unavailable in restricted contexts
    }
  };

  if (message.role === 'user') {
    return (
      <div className="message-row message-row-user">
        <div className="message-bubble message-user">
          <div className="message-role-label">You</div>
          <div className="message-content">{message.content}</div>
        </div>
      </div>
    );
  }

  if (message.role === 'error') {
    return (
      <div className="message-row message-row-assistant" role="alert">
        <div className="message-bubble message-error">
          <div className="message-role-label error-label">Gateway Notice</div>
          <div className="message-content">{message.content}</div>
        </div>
      </div>
    );
  }

  const meta = message.metadata;
  const isCached = meta?.resolution_source === 'LLM_CACHE';

  return (
    <div className="message-row message-row-assistant" data-testid="assistant-message">
      <div className="message-bubble message-assistant">
        <div className="assistant-header">
          <span className="message-role-label">Assistant</span>
          <button
            type="button"
            className="copy-btn"
            onClick={handleCopy}
            aria-label="Copy assistant response"
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>

        <div className="message-content">{message.content}</div>

        {meta && (
          <div className="metadata-bar" aria-label="Response telemetry">
            <span
              data-testid="meta-source"
              className={`meta-badge ${isCached ? 'badge-cache' : 'badge-live'}`}
            >
              {meta.resolution_source}
            </span>

            <span className="meta-chip" title="LiteLLM model">
              <span className="meta-key">model</span>
              <span data-testid="meta-model" className="meta-val">
                {meta.model}
              </span>
            </span>

            <span className="meta-chip" title="Server processing latency">
              <span data-testid="meta-latency" className="meta-val">
                {meta.latency_ms} ms
              </span>
            </span>

            <span className="meta-chip" title="Prompt tokens for this request">
              <span className="meta-key">in</span>
              <span data-testid="meta-input-tokens" className="meta-val">
                {meta.input_tokens}
              </span>
            </span>

            <span className="meta-chip" title="Completion tokens generated">
              <span className="meta-key">out</span>
              <span data-testid="meta-output-tokens" className="meta-val">
                {meta.output_tokens}
              </span>
            </span>

            <span className="meta-chip" title="API key slot used">
              <span className="meta-key">key</span>
              <span className="meta-val">{meta.key_id ?? 'cache'}</span>
            </span>

            <span className="meta-chip" title="Failed key attempts before success">
              <span className="meta-key">fallbacks</span>
              <span className="meta-val">{meta.fallback_attempts}</span>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

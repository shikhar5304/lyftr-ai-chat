import type { KeyboardEvent } from 'react';

interface ChatInputProps {
  value: string;
  isLoading: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

const MAX_CHARS = 4000;

export function ChatInput({ value, isLoading, onChange, onSubmit }: ChatInputProps) {
  const trimmedLength = value.trim().length;
  const rawLength = value.length;
  const isOverLimit = trimmedLength > MAX_CHARS;
  const canSubmit = !isLoading && trimmedLength > 0 && !isOverLimit;

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (canSubmit) {
        onSubmit();
      }
    }
  };

  return (
    <form
      className="chat-input-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (canSubmit) {
          onSubmit();
        }
      }}
    >
      <div className={`input-wrapper ${isOverLimit ? 'input-error' : ''}`}>
        <textarea
          data-testid="chat-input"
          className="chat-textarea"
          rows={2}
          placeholder="Ask anything… (Enter to send, Shift+Enter for new line)"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          aria-label="Chat message input"
        />
        <div className="input-footer">
          <span className={`char-counter ${isOverLimit ? 'over-limit' : ''}`}>
            {rawLength} / {MAX_CHARS}
            {isOverLimit ? ' (exceeds 4000-character limit)' : ''}
          </span>
          <button
            type="submit"
            data-testid="send-button"
            className="send-button"
            disabled={!canSubmit}
          >
            {isLoading ? 'Sending…' : 'Send'}
          </button>
        </div>
      </div>
    </form>
  );
}

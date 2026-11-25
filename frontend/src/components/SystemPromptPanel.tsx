interface SystemPromptPanelProps {
  isOpen: boolean;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
  onClear: () => void;
}

export function SystemPromptPanel({
  isOpen,
  value,
  disabled,
  onChange,
  onClear,
}: SystemPromptPanelProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <section className="system-prompt-panel" aria-label="System prompt settings">
      <div className="system-prompt-header">
        <div>
          <label htmlFor="system-prompt-textarea" className="system-prompt-label">
            System Prompt Override
          </label>
          <p className="system-prompt-hint">
            Optional instruction applied consistently to this session and included in cache keys.
          </p>
        </div>
        {value.trim() && (
          <button
            type="button"
            className="btn-text"
            onClick={onClear}
            disabled={disabled}
          >
            Reset to default
          </button>
        )}
      </div>
      <textarea
        id="system-prompt-textarea"
        data-testid="system-prompt-input"
        className="system-prompt-textarea"
        rows={2}
        maxLength={4000}
        placeholder="e.g., You are a concise senior distributed systems engineer."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      />
    </section>
  );
}

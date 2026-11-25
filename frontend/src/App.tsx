import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, fetchHealth, sendChatMessage } from './api/client';
import { ChatHeader } from './components/ChatHeader';
import { ChatInput } from './components/ChatInput';
import { ChatMessage } from './components/ChatMessage';
import { EmptyState } from './components/EmptyState';
import { SystemPromptPanel } from './components/SystemPromptPanel';
import type { HealthResponse, UIMessage } from './types/chat';

function createSessionId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `s-${crypto.randomUUID()}`;
  }
  return `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function createMessageId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function formatErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 503) {
      return 'All AI providers are temporarily unavailable. Please try again.';
    }
    if (err.status === 422) {
      return `Validation error: ${err.detail}`;
    }
    return err.detail;
  }
  return 'Unable to reach the AI gateway. Please verify the backend is running and try again.';
}

export function App() {
  const [sessionId, setSessionId] = useState<string>(() => createSessionId());
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [isSystemPromptOpen, setIsSystemPromptOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthStatus, setHealthStatus] = useState<'checking' | 'online' | 'offline'>('checking');

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inflightRef = useRef(false);

  useEffect(() => {
    let active = true;
    const loadHealth = async () => {
      try {
        const data = await fetchHealth();
        if (active) {
          setHealth(data);
          setHealthStatus('online');
        }
      } catch {
        if (active) {
          setHealth(null);
          setHealthStatus('offline');
        }
      }
    };

    void loadHealth();
    const timer = window.setInterval(() => {
      void loadHealth();
    }, 30000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = useCallback(
    async (overrideMessage?: string) => {
      const candidate = (overrideMessage ?? inputValue).trim();
      if (!candidate || inflightRef.current) {
        return;
      }

      inflightRef.current = true;
      setIsLoading(true);
      if (overrideMessage === undefined) {
        setInputValue('');
      }

      const userMsg: UIMessage = {
        id: createMessageId(),
        role: 'user',
        content: candidate,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);

      try {
        const response = await sendChatMessage({
          sessionId,
          message: candidate,
          systemPrompt,
        });

        const assistantMsg: UIMessage = {
          id: createMessageId(),
          role: 'assistant',
          content: response.reply,
          metadata: response.metadata,
          createdAt: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (err) {
        const errorMsg: UIMessage = {
          id: createMessageId(),
          role: 'error',
          content: formatErrorMessage(err),
          createdAt: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        inflightRef.current = false;
        setIsLoading(false);
      }
    },
    [inputValue, sessionId, systemPrompt]
  );

  const handleNewSession = () => {
    if (isLoading) return;
    setSessionId(createSessionId());
    setMessages([]);
    setInputValue('');
  };

  return (
    <div className="app-shell">
      <div className="chat-container">
        <ChatHeader
          sessionId={sessionId}
          health={health}
          healthStatus={healthStatus}
          isSystemPromptOpen={isSystemPromptOpen}
          hasCustomSystemPrompt={systemPrompt.trim().length > 0}
          onToggleSystemPrompt={() => setIsSystemPromptOpen((open) => !open)}
          onNewSession={handleNewSession}
        />

        <SystemPromptPanel
          isOpen={isSystemPromptOpen}
          value={systemPrompt}
          disabled={isLoading}
          onChange={setSystemPrompt}
          onClear={() => setSystemPrompt('')}
        />

        <main className="chat-messages" aria-live="polite">
          {messages.length === 0 ? (
            <EmptyState
              onSelectPrompt={(prompt) => {
                void handleSend(prompt);
              }}
            />
          ) : (
            <div className="messages-stack">
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
              {isLoading && (
                <div className="message-row message-row-assistant">
                  <div className="message-bubble message-loading" aria-label="Generating response">
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="loading-text">Routing via LiteLLM…</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </main>

        <footer className="chat-footer">
          <ChatInput
            value={inputValue}
            isLoading={isLoading}
            onChange={setInputValue}
            onSubmit={() => {
              void handleSend();
            }}
          />
        </footer>
      </div>
    </div>
  );
}

export default App;

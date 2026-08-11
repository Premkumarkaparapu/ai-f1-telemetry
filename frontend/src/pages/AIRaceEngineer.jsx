import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../api';

/* ── Evidence Card ───────────────────────────────────────────────── */
function EvidenceCard({ evidence }) {
  if (!evidence || Object.keys(evidence).length === 0) return null;
  return (
    <div className="ai-evidence-panel">
      <div className="ai-evidence-title">📊 Pitwall Evidence Board</div>
      <div className="ai-evidence-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '8px', marginTop: '6px' }}>
        {Object.entries(evidence).map(([k, v]) => (
          <div key={k} className="ai-evidence-metric" style={{ background: 'rgba(255,255,255,0.04)', padding: '6px 10px', borderRadius: '4px', borderLeft: '3px solid #ff8000', display: 'flex', flexDirection: 'column' }}>
            <span className="ai-metric-label" style={{ fontSize: '10px', color: '#888', textTransform: 'uppercase' }}>{k.replace(/_/g, ' ')}</span>
            <span className="ai-metric-value" style={{ fontSize: '14px', fontWeight: 'bold', color: '#fff', marginTop: '2px' }}>
              {typeof v === 'number' 
                ? (Number.isInteger(v) ? v.toLocaleString() : v.toFixed(3)) 
                : String(v)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Sources Badge ───────────────────────────────────────────────── */
function SourcesBadge({ sources }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="ai-sources">
      <span className="ai-sources-label">📚 Sources:</span>
      {sources.map((s, i) => (
        <span key={i} className="ai-source-badge">{s}</span>
      ))}
    </div>
  );
}

/* ── Message Bubble ──────────────────────────────────────────────── */
function MessageBubble({ msg }) {
  return (
    <div className={`ai-message ai-message-${msg.role}`}>
      <div className="ai-message-avatar">
        {msg.role === 'user' ? '👤' : '🏎️'}
      </div>
      <div className="ai-message-content">
        <div className="ai-message-text">{msg.text}</div>
        {msg.tools_used && msg.tools_used.length > 0 && (
          <div className="ai-tools-used">
            {msg.tools_used.map((t, i) => (
              <span key={i} className="ai-tool-badge">{t.replace(/_/g, ' ')}</span>
            ))}
          </div>
        )}
        {msg.intent && (
          <span className="ai-intent-badge">{msg.intent}</span>
        )}
        <EvidenceCard evidence={msg.evidence} />
        <SourcesBadge sources={msg.sources} />
        {msg.latency_ms != null && (
          <div className="ai-latency">{msg.latency_ms}ms</div>
        )}
      </div>
    </div>
  );
}

/* ── Suggested Questions ─────────────────────────────────────────── */
function SuggestedQuestions({ questions, onSelect, disabled }) {
  if (!questions || questions.length === 0) return null;
  return (
    <div className="ai-suggestions">
      {questions.map((q, i) => (
        <button key={i} className="ai-suggestion-btn" onClick={() => onSelect(q)} disabled={disabled}>
          {q}
        </button>
      ))}
    </div>
  );
}

/* ── Main Page ───────────────────────────────────────────────────── */
export default function AIRaceEngineer() {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState('');
  const [driverCode, setDriverCode] = useState('');
  const [drivers, setDrivers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [aiHealth, setAiHealth] = useState(null);
  const [error, setError] = useState(null);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  // Load sessions on mount
  useEffect(() => {
    api.getSessions().then(s => {
      setSessions(s);
      if (s.length > 0) setSessionId(String(s[0].session_id));
    }).catch(() => {});
    api.aiHealth().then(setAiHealth).catch(() => setAiHealth({ status: 'offline', provider: 'none', provider_class: 'Unavailable' }));
  }, []);

  // Load drivers when session changes
  useEffect(() => {
    if (!sessionId) return;
    api.getDrivers(sessionId).then(d => {
      setDrivers(d);
      setDriverCode('');
    }).catch(() => setDrivers([]));
    api.aiSuggest(sessionId, null).then(r => setSuggestions(r.questions || [])).catch(() => {});
  }, [sessionId]);

  // Update suggestions when driver changes
  useEffect(() => {
    if (!sessionId) return;
    api.aiSuggest(sessionId, driverCode || null).then(r => setSuggestions(r.questions || [])).catch(() => {});
  }, [driverCode, sessionId]);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = useCallback(async (question) => {
    const q = (question || input).trim();
    if (!q || !sessionId) return;
    setInput('');
    setError(null);
    setLoading(true);

    // Add user message
    setMessages(prev => [...prev, { role: 'user', text: q }]);

    try {
      const result = await api.aiAsk({
        question: q,
        session_id: parseInt(sessionId),
        driver_code: driverCode || null,
      });

      setMessages(prev => [...prev, {
        role: 'assistant',
        text: result.answer,
        evidence: result.evidence,
        tools_used: result.tools_used,
        intent: result.intent,
        sources: result.sources,
        latency_ms: result.latency_ms,
      }]);
    } catch (err) {
      const errMsg = err.message.includes('422')
        ? 'Please ask a more specific F1 question (e.g. "How was VER\'s pace?")'
        : `Connection error — is the backend running? (${err.message})`;
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: errMsg,
      }]);
    } finally {
      setLoading(false);
      // Re-focus input after response
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [input, sessionId, driverCode]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
  };

  const selectedSession = sessions.find(s => String(s.session_id) === sessionId);

  return (
    <div className="ai-race-engineer">
      {/* Header */}
      <div className="ai-header">
        <div className="ai-header-left">
          <div className="ai-header-icon">🏎️</div>
          <div>
            <h1 className="ai-title">AI Race Engineer</h1>
            <p className="ai-subtitle">
              Ask questions about race data, strategy, and regulations
            </p>
          </div>
        </div>
        <div className="ai-header-right">
          {messages.length > 0 && (
            <button className="ai-clear-btn" onClick={clearChat} title="Clear chat">🗑️</button>
          )}
          {aiHealth && (
            <span className="ai-health-badge" data-status={aiHealth.status}>
              {aiHealth.provider_class} • {aiHealth.status}
            </span>
          )}
        </div>
      </div>

      {/* Context Selectors */}
      <div className="ai-context-bar">
        <div className="ai-context-group">
          <label className="ai-context-label">Session</label>
          <select
            className="ai-select"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
          >
            <option value="">Select a session...</option>
            {sessions.map(s => (
              <option key={s.session_id} value={String(s.session_id)}>
                {s.year} {s.event_name}
              </option>
            ))}
          </select>
        </div>
        <div className="ai-context-group">
          <label className="ai-context-label">Driver (optional)</label>
          <select
            className="ai-select"
            value={driverCode}
            onChange={(e) => setDriverCode(e.target.value)}
          >
            <option value="">All drivers</option>
            {drivers.map(d => (
              <option key={d.driver_id} value={d.code}>
                {d.code} — {d.full_name} ({d.team})
              </option>
            ))}
          </select>
        </div>
        {selectedSession && (
          <div className="ai-context-info">
            <span>📍 {selectedSession.track}</span>
            <span>🏁 {selectedSession.total_laps} laps</span>
          </div>
        )}
      </div>

      {/* Chat Area */}
      <div className="ai-chat-area">
        {messages.length === 0 ? (
          <div className="ai-empty-state">
            <div className="ai-empty-icon">🤖</div>
            <h2>Ask the Race Engineer</h2>
            <p>Select a session and ask about pace, strategy, tire degradation, or anything F1-related.</p>
            <SuggestedQuestions
              questions={suggestions}
              onSelect={handleSend}
              disabled={loading || !sessionId}
            />
          </div>
        ) : (
          <div className="ai-messages">
            {messages.map((msg, i) => (
              <MessageBubble key={i} msg={msg} />
            ))}
            {loading && (
              <div className="ai-message ai-message-assistant">
                <div className="ai-message-avatar">🏎️</div>
                <div className="ai-message-content">
                  <div className="ai-typing">
                    <span></span><span></span><span></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        )}
      </div>

      {/* Suggestion chips (when messages exist) */}
      {messages.length > 0 && !loading && (
        <SuggestedQuestions
          questions={suggestions}
          onSelect={handleSend}
          disabled={loading || !sessionId}
        />
      )}

      {/* Input Bar */}
      <div className="ai-input-bar">
        <input
          ref={inputRef}
          className="ai-input"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={sessionId ? "Ask about pace, strategy, tire deg..." : "Select a session first..."}
          disabled={loading || !sessionId}
          autoFocus
        />
        <button
          className="ai-send-btn"
          onClick={() => handleSend()}
          disabled={loading || !input.trim() || !sessionId}
        >
          {loading ? '⏳' : '🚀'}
        </button>
      </div>
    </div>
  );
}

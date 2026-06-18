import React, { useState, useEffect, useRef } from 'react';
import { sendChat, fetchSessions, fetchChatHistory } from './api';
import './styles.css';

// ----------------------------------------------------------------------
// 1. Data Visualization Components
// ----------------------------------------------------------------------

function DataVisualizer({ data }) {
  if (!data || !data.rows || data.rows.length === 0) return null;
  
  if (data.columns.includes("Passed Students") && data.columns.includes("Total Students")) {
    return <StatCards data={data} />;
  }
  if (data.columns.includes("Roll No") && data.columns.includes("Average Marks") && data.columns.length <= 6) {
    return <Leaderboard data={data} />;
  }
  
  return <DataTable data={data} />;
}

function StatCards({ data }) {
  const row = data.rows[0];
  const passedIdx = data.columns.indexOf("Passed Students");
  const failedIdx = data.columns.indexOf("Failed Students");
  const totalIdx = data.columns.indexOf("Total Students");

  return (
    <div className="stat-cards-container">
      <div className="stat-cards">
        {totalIdx !== -1 && (
          <div className="stat-card">
            <div className="stat-value">{row[totalIdx]}</div>
            <div className="stat-label">Total</div>
          </div>
        )}
        {passedIdx !== -1 && (
          <div className="stat-card success">
            <div className="stat-value">{row[passedIdx]}</div>
            <div className="stat-label">Passed</div>
          </div>
        )}
        {failedIdx !== -1 && (
          <div className="stat-card danger">
            <div className="stat-value">{row[failedIdx]}</div>
            <div className="stat-label">Failed</div>
          </div>
        )}
      </div>
    </div>
  );
}

function Leaderboard({ data }) {
  return (
    <div className="leaderboard-container">
      <div className="leaderboard-list">
        {data.rows.slice(0, 5).map((row, idx) => {
          const name = row[data.columns.indexOf("Name")] || row[data.columns.indexOf("Student Name")];
          const roll = row[data.columns.indexOf("Roll No")] || row[data.columns.indexOf("Roll Number")];
          const score = row[data.columns.indexOf("Average Marks")] || row[data.columns.indexOf("Marks")];
          return (
            <div key={idx} className="leaderboard-item">
              <div className="leader-rank">#{idx + 1}</div>
              <div className="leader-info">
                <div className="leader-name">{name}</div>
                <div className="leader-roll">{roll}</div>
              </div>
              <div className="leader-score">{score}{String(score).includes('%') ? '' : '%'}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DataTable({ data }) {
  const [page, setPage] = useState(0);
  const pageSize = 10;
  const totalPages = Math.ceil(data.rows.length / pageSize);

  const downloadCSV = () => {
    const csv = [data.columns.join(',')]
      .concat(data.rows.map(r => r.map(String).map(s => '"' + s.replace(/"/g, '""') + '"').join(',')))
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'export.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="data-table-container">
      <div className="table-responsive">
        <table>
          <thead>
            <tr>{data.columns.map(c => <th key={c}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {data.rows.slice(page * pageSize, (page + 1) * pageSize).map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => <td key={j}>{String(cell)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="data-footer">
        <button className="btn-csv" onClick={downloadCSV}>
          <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
          CSV
        </button>
        {totalPages > 1 && (
          <div className="pagination">
            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>Prev</button>
            <span>{page + 1} / {totalPages}</span>
            <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page + 1 >= totalPages}>Next</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------
// 2. Chat Icons & Components
// ----------------------------------------------------------------------
const UserIcon = () => (
  <svg className="avatar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
    <circle cx="12" cy="7" r="4"></circle>
  </svg>
);

const SpeedAIIcon = () => (
  <svg className="avatar-icon bot-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
  </svg>
);

function ReasoningPanel({ m }) {
  const [expanded, setExpanded] = useState(false);
  
  // Don't show for conversational responses unless they have specific RAG contexts
  if (m.source === "conversational" && !m.data?.context_used) return null;
  
  const ctx = m.data?.context_used || {};
  
  return (
    <div className="reasoning-panel">
      <button className="reasoning-toggle" onClick={() => setExpanded(!expanded)}>
        <svg style={{transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)', transition: '0.2s'}} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6"/></svg>
        How SPEED AI Found This Answer
      </button>
      {expanded && (
        <div className="reasoning-content">
          <div className="reasoning-row">
            <span className="reasoning-label">Source</span>
            <span className="reasoning-value">{m.source}</span>
          </div>
          <div className="reasoning-row">
            <span className="reasoning-label">Confidence</span>
            <span className="reasoning-value">{m.confidence ? (m.confidence * 100).toFixed(1) + '%' : 'N/A'}</span>
          </div>
          {ctx["Execution Time (ms)"] && (
            <div className="reasoning-row">
              <span className="reasoning-label">Execution Time</span>
              <span className="reasoning-value">{ctx["Execution Time (ms)"]}</span>
            </div>
          )}
          {ctx["Provider Used"] && (
            <div className="reasoning-row">
              <span className="reasoning-label">Provider</span>
              <span className="reasoning-value" style={{textTransform: 'capitalize'}}>{ctx["Provider Used"]}</span>
            </div>
          )}
          {ctx["Fallback Depth"] !== undefined && (
            <div className="reasoning-row">
              <span className="reasoning-label">Fallback Used</span>
              <span className="reasoning-value">{ctx["Fallback Depth"] > 0 ? `Yes (Depth ${ctx["Fallback Depth"]})` : 'No'}</span>
            </div>
          )}
          {ctx["Latency"] && (
            <div className="reasoning-row">
              <span className="reasoning-label">LLM Latency</span>
              <span className="reasoning-value">{ctx["Latency"]}</span>
            </div>
          )}
          {ctx["Retrieved Schema Count"] !== undefined && (
            <div className="reasoning-row">
              <span className="reasoning-label">Schema Tables Ret.</span>
              <span className="reasoning-value">{ctx["Retrieved Schema Count"]}</span>
            </div>
          )}
          {ctx["Retrieved Rule Count"] !== undefined && (
            <div className="reasoning-row">
              <span className="reasoning-label">Business Rules Ret.</span>
              <span className="reasoning-value">{ctx["Retrieved Rule Count"]}</span>
            </div>
          )}
          {m.data?.generated_sql && (
            <div className="reasoning-row stack">
              <span className="reasoning-label">Generated SQL</span>
              <pre className="reasoning-code">{m.data.generated_sql}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------
// 3. Main Application
// ----------------------------------------------------------------------
export default function App() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [sessionsList, setSessionsList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [darkMode, setDarkMode] = useState(true);
  const [demoMode, setDemoMode] = useState(false);
  const [activeFilters, setActiveFilters] = useState({});
  
  const textareaRef = useRef(null);
  const messagesEndRef = useRef(null);

  const loadSessions = async () => {
    try {
      const data = await fetchSessions();
      setSessionsList(data || []);
    } catch (err) {
      console.error("Failed to fetch sessions", err);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const loadChat = async (sid) => {
    setLoading(true);
    try {
      const data = await fetchChatHistory(sid);
      const formattedMessages = data.messages.map(m => ({
        role: m.role,
        content: m.content,
        data: m.structured_data,
        timestamp: new Date(m.created_at + 'Z').toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
      }));
      setMessages(formattedMessages);
      setSessionId(sid);
      setActiveFilters(data.active_filters || {});
    } catch (err) {
      console.error("Failed to load chat history", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    if (darkMode) {
      document.body.classList.add('dark');
    } else {
      document.body.classList.remove('dark');
    }
  }, [darkMode]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleInput = (e) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
  };

  const handleSend = async (textToSubmit = input) => {
    if (!textToSubmit.trim() || loading) return;
    
    const userMsg = { role: 'user', content: textToSubmit, timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setLoading(true);

    try {
      const res = await sendChat(textToSubmit, sessionId);
      if (!sessionId) {
        setSessionId(res.session_id);
        loadSessions(); // refresh the list when a new session is created
      }
      const assistantMsg = {
        role: 'assistant',
        content: res.text,
        data: res.data,
        source: res.source,
        confidence: res.confidence,
        context_used: res.context_used,
        clarification_options: res.clarification_options,
        timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
      };
      setMessages(prev => [...prev, assistantMsg]);
      if (res.active_filters) {
        setActiveFilters(res.active_filters);
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered a network error. Is the server running?', timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }]);
    }
    setLoading(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const startNewChat = () => {
    setSessionId(null);
    setMessages([]);
    setActiveFilters({});
    loadSessions();
  };

  const removeFilter = async (key) => {
    if (!sessionId) return;
    try {
      await fetch('/api/chat/remove_filter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, filter_key: key })
      });
      setActiveFilters(prev => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    } catch (err) {
      console.error('Failed to remove filter', err);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className={`app-root ${darkMode ? 'dark-mode' : 'light-mode'}`}>
      
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <button className="btn-new-chat" onClick={startNewChat}>
            <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14"/></svg>
            New chat
          </button>
        </div>
        
        <div className="sidebar-content">
          <div className="sidebar-section">
            <h3>Recent Chats</h3>
            <ul className="feature-list recent-chats">
              {sessionsList.length > 0 ? (
                sessionsList.map(s => (
                  <li 
                    key={s.session_id} 
                    onClick={() => loadChat(s.session_id)}
                    className={s.session_id === sessionId ? 'active-chat' : ''}
                    style={{ cursor: 'pointer', padding: '8px', borderRadius: '4px', background: s.session_id === sessionId ? 'rgba(255,255,255,0.1)' : 'transparent', marginBottom: '4px' }}
                  >
                    {s.conversation_summary || `Chat from ${new Date(s.created_at + 'Z').toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'})}`}
                  </li>
                ))
              ) : (
                <li style={{opacity: 0.5}}>No previous chats found.</li>
              )}
            </ul>
          </div>
        </div>
        
        <div className="sidebar-footer">
          <label className="toggle-label btn-theme">
            <span>
               <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" style={{marginRight: 10}}><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"></path></svg>
               Demo Mode
            </span>
            <input type="checkbox" checked={demoMode} onChange={(e) => setDemoMode(e.target.checked)} />
            <span className="toggle-switch"></span>
          </label>
          <button className="btn-theme" onClick={() => setDarkMode(!darkMode)} style={{marginTop: 8}}>
            {darkMode ? (
              <><svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg> Light Mode</>
            ) : (
              <><svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg> Dark Mode</>
            )}
          </button>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="main-chat">
        
        {Object.keys(activeFilters).length > 0 && (
          <div className="active-filters-container">
            <span className="filters-label">Active Filters:</span>
            <div className="filter-chips">
              {Object.entries(activeFilters).map(([k, v]) => (
                <div key={k} className="filter-chip">
                  <span className="filter-chip-text">{k}: {v}</span>
                  <button className="filter-chip-remove" onClick={() => removeFilter(k)}>×</button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="chat-feed">
          {messages.length === 0 ? (
            <div className="landing-experience">
              <div className="landing-icon"><SpeedAIIcon /></div>
              <h1>SPEED AI</h1>
              <p className="landing-sub">Academic Intelligence Assistant<br/>Natural language access to academic data.</p>
              
              <div className="onboarding-container">
                <div className="onboarding-intro">
                  <h3>What SPEED AI Can Help With</h3>
                </div>
                <div className="onboarding-grid">
                  <div className="onboarding-section">
                    <h4>🎓 Student Discovery</h4>
                    <ul>
                      <li>Find students by department</li>
                      <li>Filter by year or city</li>
                      <li>Lookup by roll number</li>
                    </ul>
                  </div>
                  <div className="onboarding-section">
                    <h4>📚 Academic Records</h4>
                    <ul>
                      <li>View full transcripts</li>
                      <li>Check subject marks</li>
                      <li>Review semester performance</li>
                    </ul>
                  </div>
                  <div className="onboarding-section">
                    <h4>🏆 Performance Analysis</h4>
                    <ul>
                      <li>Discover department toppers</li>
                      <li>Identify high performers</li>
                      <li>View pass/fail statistics</li>
                    </ul>
                  </div>
                  <div className="onboarding-section">
                    <h4>📊 Analytics & Insights</h4>
                    <ul>
                      <li>Compare department averages</li>
                      <li>Analyze subject difficulty</li>
                      <li>Identify academic trends</li>
                    </ul>
                  </div>
                </div>
                
                <div className="starter-prompts-title">
                  Not sure what to ask? Try exploring:
                </div>
                <div className="suggestions-grid">
                  <button className="suggestion-card" onClick={() => handleSend("Find all Computer Science students")}>
                    <span className="sugg-category">Student Search</span>
                    <span className="sugg-text">Find all Computer Science students</span>
                  </button>
                  <button className="suggestion-card" onClick={() => handleSend("Show transcript for 2025-CSE-001")}>
                    <span className="sugg-category">Academic Records</span>
                    <span className="sugg-text">Show transcript for 2025-CSE-001</span>
                  </button>
                  <button className="suggestion-card" onClick={() => handleSend("Who are the toppers in IT?")}>
                    <span className="sugg-category">Performance Analysis</span>
                    <span className="sugg-text">Who are the toppers in IT?</span>
                  </button>
                  <button className="suggestion-card" onClick={() => handleSend("Compare departments by average marks")}>
                    <span className="sugg-category">Analytics</span>
                    <span className="sugg-text">Compare departments by average marks</span>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="messages-container">
              {messages.map((m, idx) => (
                <div key={idx} className={`message-row ${m.role}`}>
                  <div className="message-container-inner">
                    <div className="avatar-wrapper">
                      {m.role === 'user' ? <UserIcon /> : <SpeedAIIcon />}
                    </div>
                    <div className="message-content">
                      <div className="message-meta">
                        <strong>{m.role === 'user' ? 'You' : 'SPEED AI'}</strong>
                      </div>
                      
                      {/* Context Inherited Indicator Removed - Belongs only in Demo Mode */}
                      
                      <div className="message-text">{m.content}</div>
                      
                      {/* Clarification Options */}
                      {m.clarification_options && m.clarification_options.length > 0 && (
                        <div className="clarification-options">
                          {m.clarification_options.map((opt, i) => (
                            <button key={i} className="clarification-pill" onClick={() => handleSend(opt)}>
                              {opt}
                            </button>
                          ))}
                        </div>
                      )}
                      
                      {/* Render visual data ONLY if this is the assistant and data exists */}
                      {m.role === 'assistant' && m.data && m.data.rows?.length > 0 && (
                        <div className="data-results-block">
                          <DataVisualizer data={m.data} />
                        </div>
                      )}
                      
                      {/* Reasoning Panel (Demo Mode) */}
                      {m.role === 'assistant' && demoMode && (
                        <ReasoningPanel m={m} />
                      )}
                      
                      <div className="message-actions">
                        <button className="action-btn" onClick={() => copyToClipboard(m.content)} title="Copy">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              
              {loading && (
                <div className="message-row assistant">
                  <div className="message-container-inner">
                    <div className="avatar-wrapper"><SpeedAIIcon /></div>
                    <div className="message-content">
                      <div className="message-meta">
                        <strong>SPEED AI</strong>
                      </div>
                      <div className="thinking-indicator">
                        <svg className="spinner" viewBox="0 0 50 50">
                          <circle className="path" cx="25" cy="25" r="20" fill="none" strokeWidth="4"></circle>
                        </svg>
                        <span>SPEED AI is thinking...</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} style={{height: 1}} />
            </div>
          )}
        </div>

        <div className="composer-container">
          <div className="composer-box">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder="Message SPEED AI..."
              rows={1}
              disabled={loading}
            />
            <button className="btn-send-modern" onClick={() => handleSend()} disabled={!input.trim() || loading}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            </button>
          </div>
          <div className="composer-footer">
            SPEED AI can make mistakes. Check important academic data.
          </div>
        </div>

      </div>
    </div>
  );
}

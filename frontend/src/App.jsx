import React, { useState, useEffect } from 'react'
import { sendQuestion, getSampleQuestions } from './api'

export default function App() {
  const [q, setQ] = useState('')
  const [result, setResult] = useState(null)
  const [samples, setSamples] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(0)
  const pageSize = 20
  const [history, setHistory] = useState([])

  useEffect(() => {
    getSampleQuestions().then(setSamples)
    try {
      const raw = localStorage.getItem('query_history')
      if (raw) setHistory(JSON.parse(raw))
    } catch (e) {}
  }, [])

  async function ask(question) {
    if (!question.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await sendQuestion(question)
      setResult(res)
      setPage(0)
      try {
        const next = [question].concat(history).filter(Boolean).slice(0, 10)
        setHistory(next)
        localStorage.setItem('query_history', JSON.stringify(next))
      } catch (e) {}
    } catch (err) {
      setError(err.message || 'Request failed. Is the backend running?')
      setResult(null)
    }
    setLoading(false)
  }

  function handleKey(e) {
    if (e.key === 'Enter') ask(q)
  }

  function downloadCSV() {
    const csv = [result.columns.join(',')]
      .concat(result.rows.map(r =>
        r.map(String).map(s => '"' + s.replace(/"/g, '""') + '"').join(',')
      ))
      .join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'query_result.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const totalPages = result ? Math.ceil(result.rows.length / pageSize) : 0

  return (
    <div className="app-root">
      <div className="app-header">
        <h2>Engineering Student Database</h2>
      </div>

      <div className="app-container">

        {/* Input */}
        <div className="input-row">
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            onKeyDown={handleKey}
            placeholder="e.g. Show toppers in Computer Science"
          />
          <button className="btn-ask" onClick={() => ask(q)} disabled={!q || loading}>
            {loading ? 'Loading…' : 'Ask'}
          </button>
        </div>

        {/* Sample questions */}
        <div className="section-label">Sample questions</div>
        <div className="chips-wrap">
          {samples.map(s => (
            <button key={s} className="chip" onClick={() => { setQ(s); ask(s) }}>
              {s}
            </button>
          ))}
        </div>

        {/* Recent history */}
        {history.length > 0 && (
          <>
            <div className="section-label">Recent queries</div>
            <div className="history-list">
              {history.map(h => (
                <div key={h} className="history-item" onClick={() => { setQ(h); ask(h) }}>
                  {h}
                </div>
              ))}
            </div>
          </>
        )}

        {/* Error */}
        {error && <div className="error-msg">{error}</div>}

        {/* Result */}
        {result && (
          <div className="result-box">
            <div className="result-title">
              {result.title}
              {result.source && (
                <span className={`source-badge source-badge--${result.source}`}>
                  {result.source === 'ai' ? 'AI'
                    : result.source === 'semantic' ? 'Semantic'
                    : result.source === 'text-to-sql' ? 'SQL'
                    : 'Rule'}
                </span>
              )}
            </div>
            {result.generated_sql && (
              <details className="sql-details">
                <summary className="sql-summary">Generated SQL</summary>
                <pre className="sql-block">{result.generated_sql}</pre>
              </details>
            )}
            {result.summary && <div className="result-summary">{result.summary}</div>}

            {result.columns && result.rows && (
              <>
                <div className="result-actions">
                  <button className="btn-sm" onClick={downloadCSV}>Download CSV</button>
                  <button className="btn-sm" onClick={() => navigator.clipboard.writeText(JSON.stringify(result)).catch(() => {})}>
                    Copy JSON
                  </button>
                  <span className="row-count">{result.rows.length} rows</span>
                </div>

                <div className="result-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        {result.columns.map(c => <th key={c}>{c}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {result.rows.slice(page * pageSize, (page + 1) * pageSize).map((r, i) => (
                        <tr key={i}>
                          {r.map((c, j) => <td key={j}>{String(c)}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {totalPages > 1 && (
                  <div className="pagination">
                    <button className="btn-sm" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>
                      ← Prev
                    </button>
                    <span>Page {page + 1} of {totalPages}</span>
                    <button className="btn-sm" onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page + 1 >= totalPages}>
                      Next →
                    </button>
                  </div>
                )}
              </>
            )}

            {result.note && <div className="result-note">{result.note}</div>}
          </div>
        )}
      </div>
    </div>
  )
}

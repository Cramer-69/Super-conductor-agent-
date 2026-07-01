import { useEffect, useRef, useState } from 'react'
import * as api from './api'
import './App.css'

function getOrCreateUserId() {
  let id = localStorage.getItem('semantic_wall_user_id')
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem('semantic_wall_user_id', id)
  }
  return id
}

function newSessionId() {
  return crypto.randomUUID()
}

export default function App() {
  const [userId] = useState(getOrCreateUserId)
  const [sessionId, setSessionId] = useState(newSessionId)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [health, setHealth] = useState(null)
  const [checkinDue, setCheckinDue] = useState(false)
  const [checkinAnswers, setCheckinAnswers] = useState(null)
  const scrollRef = useRef(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  function startNewSession() {
    setSessionId(newSessionId())
    setMessages([])
    setCheckinDue(false)
  }

  async function send() {
    const query = draft.trim()
    if (!query || sending) return

    setMessages((m) => [...m, { role: 'user', text: query }])
    setDraft('')
    setSending(true)

    try {
      const result = await api.chat({ userId, sessionId, query })
      setMessages((m) => [...m, { role: 'assistant', text: result.response }])
      setCheckinDue(result.checkin_due)
      if (result.checkin_due) {
        setCheckinAnswers({
          completionConfirmation: null,
          qualityRating: 3,
          improvementNote: '',
          usedInRealWork: null,
          willingnessToPay: 'maybe',
        })
      }
    } catch (err) {
      setMessages((m) => [...m, { role: 'system', text: `Error: ${err.message}` }])
    } finally {
      setSending(false)
    }
  }

  async function submitCheckin() {
    if (!checkinAnswers || checkinAnswers.improvementNote.trim().length < 10) return
    try {
      await api.submitCheckin({ userId, sessionId, answers: checkinAnswers })
      setCheckinDue(false)
      setCheckinAnswers(null)
    } catch (err) {
      setMessages((m) => [...m, { role: 'system', text: `Check-in error: ${err.message}` }])
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <button className="new-session-btn" onClick={startNewSession}>
          ＋ New session
        </button>
        <p className="sidebar-note">Session: {sessionId.slice(0, 8)}</p>
        <div className="sidebar-footer">
          <div className="status-strip">
            {health ? (
              <>
                <span>
                  <Dot on={health.providers?.length > 0} />
                  LLM: {health.providers?.length ? health.providers.join(', ') : 'none'}
                </span>
                <span>
                  <Dot on={health.memory_configured} />
                  Memory
                </span>
              </>
            ) : (
              <span>
                <Dot on={false} />
                Backend unreachable
              </span>
            )}
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="main-header">
          <h1>Semantic Wall — Strategist</h1>
        </header>

        <div className="chat-scroll" ref={scrollRef}>
          <div className="messages">
            {messages.length === 0 && (
              <div className="empty-state">
                <p className="empty-title">👋 Hi there!</p>
                <p className="empty-sub">
                  Every message here is remembered — ask something, come back later, and the agent
                  will still have context.
                </p>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`message ${m.role}`}>
                {m.text}
              </div>
            ))}
          </div>
        </div>

        {checkinDue && checkinAnswers && (
          <CheckinPanel answers={checkinAnswers} onChange={setCheckinAnswers} onSubmit={submitCheckin} />
        )}

        <div className="composer">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder="Message the Strategist agent..."
            disabled={sending}
          />
          <button onClick={send} disabled={sending || !draft.trim()}>
            Send
          </button>
        </div>
      </main>
    </div>
  )
}

function Dot({ on }) {
  return <span className={`status-dot ${on ? 'on' : 'off'}`} />
}

function CheckinPanel({ answers, onChange, onSubmit }) {
  const noteTooShort = answers.improvementNote.trim().length < 10

  return (
    <div className="checkin-panel">
      <p className="checkin-title">Quick 5-question check-in (this keeps the session honest and free)</p>

      <label>Did the agent complete the task you assigned?</label>
      <BoolButtons value={answers.completionConfirmation} onChange={(v) => onChange({ ...answers, completionConfirmation: v })} />

      <label>Quality of the output (1–5)</label>
      <input
        type="range"
        min={1}
        max={5}
        value={answers.qualityRating}
        onChange={(e) => onChange({ ...answers, qualityRating: Number(e.target.value) })}
      />
      <span className="rating-value">{answers.qualityRating}</span>

      <label>What would have made that output better? (min 10 characters)</label>
      <textarea
        value={answers.improvementNote}
        onChange={(e) => onChange({ ...answers, improvementNote: e.target.value })}
      />

      <label>Did you use that output in actual work?</label>
      <BoolButtons value={answers.usedInRealWork} onChange={(v) => onChange({ ...answers, usedInRealWork: v })} />

      <label>Would you pay for this specific capability?</label>
      <select
        value={answers.willingnessToPay}
        onChange={(e) => onChange({ ...answers, willingnessToPay: e.target.value })}
      >
        <option value="yes">Yes</option>
        <option value="no">No</option>
        <option value="maybe">Maybe</option>
      </select>

      <button
        className="checkin-submit"
        disabled={answers.completionConfirmation === null || answers.usedInRealWork === null || noteTooShort}
        onClick={onSubmit}
      >
        Submit check-in
      </button>
    </div>
  )
}

function BoolButtons({ value, onChange }) {
  return (
    <div className="bool-buttons">
      <button className={value === true ? 'active' : ''} onClick={() => onChange(true)}>
        Yes
      </button>
      <button className={value === false ? 'active' : ''} onClick={() => onChange(false)}>
        No
      </button>
    </div>
  )
}

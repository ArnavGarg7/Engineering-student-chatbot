export async function sendChat(message, session_id = null) {
  const res = await fetch('http://127.0.0.1:8000/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id })
  });
  if (!res.ok) throw new Error('API error');
  return res.json();
}

export async function getSampleQuestions() {
  const res = await fetch('http://127.0.0.1:8000/api/sample_questions');
  if (!res.ok) return [];
  return res.json();
}

export async function fetchSessions() {
  const res = await fetch('http://127.0.0.1:8000/api/sessions');
  if (!res.ok) return [];
  return res.json();
}

export async function fetchChatHistory(sessionId) {
  const res = await fetch(`http://127.0.0.1:8000/api/chat/${sessionId}/history`);
  if (!res.ok) throw new Error('API error');
  return res.json();
}

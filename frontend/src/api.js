export async function sendQuestion(question){
  const res = await fetch('http://127.0.0.1:8000/api/query',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({question})
  })
  if(!res.ok) throw new Error('API error')
  return res.json()
}

export async function getSampleQuestions(){
  const res = await fetch('http://127.0.0.1:8000/api/sample_questions')
  if(!res.ok) return []
  return res.json()
}

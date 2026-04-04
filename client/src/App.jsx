import { useState } from 'react';

const SECTIONS = [
  'THESIS HEALTH',
  'MANAGEMENT CREDIBILITY',
  'STUMBLE CLASSIFICATION',
  'THREAT MECHANISM TEST',
  'MITIGATION ARGUMENT TEST',
  'POSITION TYPE',
  'POSITION SIZING RECOMMENDATION',
  'RECOMMENDATION',
  'FRESH MONEY TEST',
  'FICTIONAL DETAIL CHECK',
];

function parseAnalysis(text) {
  const sections = [];
  const lines = text.split('\n');
  let current = null;

  for (const line of lines) {
    const headerMatch = line.match(/^##\s+(.+)/);
    if (headerMatch) {
      if (current) sections.push(current);
      current = { title: headerMatch[1].trim(), body: [] };
    } else if (current) {
      current.body.push(line);
    }
  }
  if (current) sections.push(current);

  // If parsing yielded nothing, return raw text as single block
  if (sections.length === 0) {
    return [{ title: null, body: text.split('\n') }];
  }
  return sections;
}

function scoreColor(title, body) {
  const text = body.join(' ').toLowerCase();
  if (title === 'THESIS HEALTH') {
    if (text.includes('strengthening')) return '#22c55e';
    if (text.includes('intact')) return '#86efac';
    if (text.includes('weakening')) return '#f59e0b';
    if (text.includes('broken')) return '#ef4444';
  }
  if (title === 'RECOMMENDATION') {
    if (text.includes('exit')) return '#ef4444';
    if (text.includes('trim')) return '#f59e0b';
    if (text.includes('add')) return '#22c55e';
    if (text.includes('hold')) return '#94a3b8';
  }
  return null;
}

function Section({ title, body }) {
  const accent = scoreColor(title, body);
  const bodyText = body.join('\n').trim();

  return (
    <div style={{
      background: '#1e2330',
      border: `1px solid ${accent || '#2d3748'}`,
      borderRadius: 8,
      padding: '16px 20px',
      marginBottom: 12,
    }}>
      {title && (
        <div style={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.08em',
          color: accent || '#64748b',
          textTransform: 'uppercase',
          marginBottom: 8,
        }}>
          {title}
        </div>
      )}
      <div style={{
        fontSize: 14,
        lineHeight: 1.7,
        color: '#cbd5e1',
        whiteSpace: 'pre-wrap',
      }}>
        {bodyText}
      </div>
    </div>
  );
}

export default function App() {
  const [transcript, setTranscript] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  function handleClear() {
    setTranscript('');
    setAnalysis(null);
    setError(null);
  }

  async function handleAnalyze() {
    if (!transcript.trim()) return;
    setLoading(true);
    setError(null);
    setAnalysis(null);

    try {
      const res = await fetch('http://localhost:3001/api/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setAnalysis(data.analysis);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const sections = analysis ? parseAnalysis(analysis) : [];

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 24px' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4, color: '#f1f5f9' }}>
        Earnings Call Evaluator
      </h1>
      <p style={{ fontSize: 13, color: '#64748b', marginBottom: 24 }}>
        Paste a transcript below and click Analyze.
      </p>

      <textarea
        value={transcript}
        onChange={e => setTranscript(e.target.value)}
        placeholder="Paste earnings call transcript here…"
        style={{
          width: '100%',
          height: 360,
          padding: '14px 16px',
          background: '#1e2330',
          border: '1px solid #2d3748',
          borderRadius: 8,
          color: '#e2e8f0',
          fontSize: 13,
          lineHeight: 1.6,
          resize: 'vertical',
          outline: 'none',
          fontFamily: 'inherit',
        }}
      />

      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <button
          onClick={handleAnalyze}
          disabled={loading || !transcript.trim()}
          style={{
            padding: '10px 28px',
            background: loading || !transcript.trim() ? '#334155' : '#3b82f6',
            color: loading || !transcript.trim() ? '#64748b' : '#fff',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: loading || !transcript.trim() ? 'not-allowed' : 'pointer',
            transition: 'background 0.15s',
          }}
        >
          {loading ? 'Analyzing…' : 'Analyze'}
        </button>
        <button
          onClick={handleClear}
          disabled={loading}
          style={{
            padding: '10px 20px',
            background: 'transparent',
            color: loading ? '#334155' : '#64748b',
            border: `1px solid ${loading ? '#334155' : '#2d3748'}`,
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'color 0.15s, border-color 0.15s',
          }}
        >
          Clear
        </button>
      </div>

      {loading && (
        <div style={{ marginTop: 32, color: '#64748b', fontSize: 14 }}>
          Running evaluation — this takes 15–30 seconds…
        </div>
      )}

      {error && (
        <div style={{
          marginTop: 24,
          padding: '14px 16px',
          background: '#2d1515',
          border: '1px solid #7f1d1d',
          borderRadius: 8,
          color: '#fca5a5',
          fontSize: 13,
        }}>
          Error: {error}
        </div>
      )}

      {sections.length > 0 && (
        <div style={{ marginTop: 32 }}>
          <div style={{ fontSize: 13, color: '#64748b', marginBottom: 16 }}>Analysis</div>
          {sections.map((s, i) => (
            <Section key={i} title={s.title} body={s.body} />
          ))}
        </div>
      )}
    </div>
  );
}

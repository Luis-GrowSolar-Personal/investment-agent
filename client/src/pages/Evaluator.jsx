import { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';

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

const inputStyle = {
  width: '100%',
  padding: '9px 12px',
  background: '#1e2330',
  border: '1px solid #2d3748',
  borderRadius: 6,
  color: '#e2e8f0',
  fontSize: 13,
  outline: 'none',
  fontFamily: 'inherit',
};

const labelStyle = {
  display: 'block',
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: '0.06em',
  color: '#64748b',
  textTransform: 'uppercase',
  marginBottom: 5,
};

export default function Evaluator() {
  const { getToken } = useAuth();
  const [transcript, setTranscript] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [tickerSymbol, setTickerSymbol] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [callDate, setCallDate] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [savedIds, setSavedIds] = useState(null);

  function handleClear() {
    setTranscript('');
    setAnalysis(null);
    setTickerSymbol('');
    setCompanyName('');
    setCallDate('');
    setLoading(false);
    setError(null);
    setSaving(false);
    setSaveError(null);
    setSavedIds(null);
  }

  async function handleAnalyze() {
    if (loading || !transcript.trim()) return;
    setLoading(true);
    setError(null);
    setAnalysis(null);
    setSavedIds(null);
    setSaveError(null);

    try {
      const token = await getToken();
      const res = await fetch('http://localhost:3001/api/evaluate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ transcript }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setAnalysis(data.analysis);
      if (data.tickerSymbol) setTickerSymbol(prev => prev.trim() ? prev : data.tickerSymbol);
      if (data.companyName)  setCompanyName(prev => prev.trim() ? prev : data.companyName);
      if (data.callDate)     setCallDate(prev => prev.trim() ? prev : data.callDate);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (saving || savedIds) return;
    setSaving(true);
    setSaveError(null);

    try {
      const token = await getToken();
      const res = await fetch('http://localhost:3001/api/save', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          transcript,
          tickerSymbol,
          tickerName: companyName,
          callDate,
          analysis,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setSavedIds({
        tickerId: data.tickerId,
        transcriptId: data.transcriptId,
        analysisId: data.analysisId,
      });
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const sections = analysis ? parseAnalysis(analysis) : [];
  const canAnalyze = !loading && transcript.trim().length > 0;
  const canSave = !saving && !savedIds && !!analysis && tickerSymbol.trim().length > 0;

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 24px' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4, color: '#f1f5f9' }}>
        Earnings Call Evaluator
      </h1>
      <p style={{ fontSize: 13, color: '#64748b', marginBottom: 24 }}>
        Paste a transcript and click Analyze. Review results, then Save.
      </p>

      {/* Metadata panel */}
      <div style={{
        padding: '20px',
        background: '#161b27',
        border: '1px solid #2d3748',
        borderRadius: 8,
        marginBottom: 16,
      }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: '#64748b', textTransform: 'uppercase', marginBottom: 14 }}>
          Save to database
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr 1fr', gap: 12, marginBottom: 14 }}>
          <div>
            <label style={labelStyle}>Ticker Symbol *</label>
            <input
              type="text"
              value={tickerSymbol}
              onChange={e => setTickerSymbol(e.target.value.toUpperCase())}
              placeholder="AMPX"
              maxLength={10}
              disabled={!!savedIds}
              style={{ ...inputStyle, opacity: savedIds ? 0.5 : 1 }}
            />
          </div>
          <div>
            <label style={labelStyle}>Company Name</label>
            <input
              type="text"
              value={companyName}
              onChange={e => setCompanyName(e.target.value)}
              placeholder="Amprius Technologies"
              disabled={!!savedIds}
              style={{ ...inputStyle, opacity: savedIds ? 0.5 : 1 }}
            />
          </div>
          <div>
            <label style={labelStyle}>Call Date</label>
            <input
              type="date"
              value={callDate}
              onChange={e => setCallDate(e.target.value)}
              disabled={!!savedIds}
              style={{ ...inputStyle, colorScheme: 'dark', opacity: savedIds ? 0.5 : 1 }}
            />
          </div>
        </div>

        {!savedIds ? (
          <button
            onClick={handleSave}
            disabled={!canSave}
            style={{
              padding: '9px 24px',
              background: canSave ? '#16a34a' : '#334155',
              color: canSave ? '#fff' : '#64748b',
              border: 'none',
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 600,
              cursor: canSave ? 'pointer' : 'not-allowed',
              transition: 'background 0.15s',
            }}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        ) : (
          <div style={{
            padding: '10px 14px',
            background: '#0f2a1a',
            border: '1px solid #166534',
            borderRadius: 6,
            color: '#86efac',
            fontSize: 12,
          }}>
            Saved — Ticker #{savedIds.tickerId}, Transcript #{savedIds.transcriptId}, Analysis #{savedIds.analysisId}
          </div>
        )}

        {saveError && (
          <div style={{ marginTop: 10, color: '#fca5a5', fontSize: 12 }}>
            Save failed: {saveError}
          </div>
        )}
      </div>

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
          disabled={!canAnalyze}
          style={{
            padding: '10px 28px',
            background: canAnalyze ? '#3b82f6' : '#334155',
            color: canAnalyze ? '#fff' : '#64748b',
            border: 'none',
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: canAnalyze ? 'pointer' : 'not-allowed',
            transition: 'background 0.15s',
          }}
        >
          {loading ? 'Analyzing…' : 'Analyze'}
        </button>
        <button
          onClick={handleClear}
          disabled={loading || saving}
          style={{
            padding: '10px 20px',
            background: 'transparent',
            color: (loading || saving) ? '#334155' : '#64748b',
            border: `1px solid ${(loading || saving) ? '#334155' : '#2d3748'}`,
            borderRadius: 6,
            fontSize: 14,
            fontWeight: 600,
            cursor: (loading || saving) ? 'not-allowed' : 'pointer',
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

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@clerk/clerk-react';

// API origin: dev reads from .env.development (http://localhost:3001).
// Prod reads from .env.production (empty string → same-origin, since the
// server static-serves the SPA in prod).
const API_URL = import.meta.env.VITE_API_URL || '';

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

  const filtered = sections.filter(s => s.title?.toUpperCase() !== 'FICTIONAL DETAIL CHECK');
  if (filtered.length === 0) {
    return [{ title: null, body: text.split('\n') }];
  }
  return filtered;
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
  const [structuredScore, setStructuredScore] = useState(null);
  const [tickerSymbol, setTickerSymbol] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [callDate, setCallDate] = useState('');
  const [shortName, setShortName] = useState('');
  const [fiscalQuarter, setFiscalQuarter] = useState(null);
  const [fiscalYear, setFiscalYear] = useState(null);
  const [formerSymbol, setFormerSymbol] = useState('');
  const [title, setTitle] = useState('');
  const prevGeneratedTitleRef = useRef('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [savedIds, setSavedIds] = useState(null);
  const [transcriptCount, setTranscriptCount] = useState(null); // live count from DB
  const [tickerStatus, setTickerStatus] = useState(null); // 'watchlist' | 'portfolio' | null
  const [justCleared, setJustCleared] = useState(false);

  const fetchTranscriptCount = useCallback(async (symbol) => {
    if (!symbol.trim()) { setTranscriptCount(null); setTickerStatus(null); return; }
    try {
      const token = await getToken();
      const res = await fetch(
        `${API_URL}/api/radar/tickers/by-symbol/${encodeURIComponent(symbol.trim())}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );
      const data = await res.json();
      setTranscriptCount(data ? data.transcriptCount : null);
      setTickerStatus(data ? data.status : null);
    } catch {
      setTranscriptCount(null);
      setTickerStatus(null);
    }
  }, [getToken]);

  // Debounced fetch whenever ticker symbol changes
  useEffect(() => {
    setTranscriptCount(null);
    if (!tickerSymbol.trim()) return;
    const timer = setTimeout(() => fetchTranscriptCount(tickerSymbol), 400);
    return () => clearTimeout(timer);
  }, [tickerSymbol, fetchTranscriptCount]);

  // Refresh count after a save so the number is always current
  useEffect(() => {
    if (savedIds && tickerSymbol.trim()) fetchTranscriptCount(tickerSymbol);
  }, [savedIds, tickerSymbol, fetchTranscriptCount]);

  // Auto-generate title from formula; respect manual edits
  useEffect(() => {
    // Prefer fiscalQuarter/fiscalYear extracted from transcript header by Claude;
    // fall back to deriving from callDate only if both are missing.
    let q = fiscalQuarter;
    let y = fiscalYear;
    if ((!q || !y) && callDate) {
      const d = new Date(callDate + 'T12:00:00'); // noon local to avoid UTC-offset day shift
      if (!q) q = Math.floor(d.getMonth() / 3) + 1;
      if (!y) y = d.getFullYear();
    }
    const gen = (shortName && tickerSymbol && q && y)
      ? `${shortName} (${tickerSymbol}) Q${q} ${y} Earnings Call Transcript`
      : '';
    const prevGen = prevGeneratedTitleRef.current; // capture before mutating
    prevGeneratedTitleRef.current = gen;
    setTitle(prev => prev === prevGen ? gen : prev);
  }, [shortName, tickerSymbol, callDate, fiscalQuarter, fiscalYear]);

  function handleClear() {
    setJustCleared(true);
    setTimeout(() => setJustCleared(false), 1500);
    setTranscript('');
    setAnalysis(null);
    setStructuredScore(null);
    setTickerSymbol('');
    setCompanyName('');
    setCallDate('');
    setShortName('');
    setFiscalQuarter(null);
    setFiscalYear(null);
    setFormerSymbol('');
    setTitle('');
    prevGeneratedTitleRef.current = '';
    setLoading(false);
    setError(null);
    setSaving(false);
    setSaveError(null);
    setSavedIds(null);
    setTranscriptCount(null);
    setTickerStatus(null);
  }

  async function handleAnalyze() {
    if (loading || !transcript.trim()) return;
    setLoading(true);
    setError(null);
    setAnalysis(null);
    setStructuredScore(null);
    setSavedIds(null);
    setSaveError(null);

    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/api/evaluate`, {
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
      setStructuredScore(data.structuredScore ?? null);
      if (data.tickerSymbol)   setTickerSymbol(prev => prev.trim() ? prev : data.tickerSymbol);
      if (data.companyName)    setCompanyName(prev => prev.trim() ? prev : data.companyName);
      if (data.callDate)       setCallDate(prev => prev.trim() ? prev : data.callDate);
      if (data.shortName)      setShortName(prev => prev.trim() ? prev : data.shortName);
      if (data.fiscalQuarter)  setFiscalQuarter(data.fiscalQuarter);
      if (data.fiscalYear)     setFiscalYear(data.fiscalYear);
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
      const res = await fetch(`${API_URL}/api/save`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          transcript,
          tickerSymbol,
          tickerName: companyName,
          shortName,
          callDate,
          title,
          analysis,
          structuredScore,
          formerSymbol: formerSymbol.trim() || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setSavedIds({
        tickerId: data.tickerId,
        transcriptId: data.transcriptId,
        analysisId: data.analysisId,
      });
      window.dispatchEvent(new Event('radar:refresh'));
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const sections = analysis ? parseAnalysis(analysis) : [];
  const canAnalyze = !loading && !analysis && transcript.trim().length > 0;
  const canSave = !saving && !savedIds && !!analysis && tickerSymbol.trim().length > 0;
  const canClear = !loading && !saving && !justCleared && (!!transcript.trim() || !!analysis);

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 24px' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4, color: '#f1f5f9' }}>
        Stock Analyst
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
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 14 }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: '#64748b', textTransform: 'uppercase' }}>
            Save to database
          </span>
          {transcriptCount !== null && (
            <span style={{ fontSize: 12, color: '#475569' }}>
              {transcriptCount}{tickerStatus === 'watchlist' ? '/6' : ''} transcript{transcriptCount !== 1 ? 's' : ''} on file for {tickerSymbol}
              {tickerStatus === 'watchlist' && transcriptCount >= 6 && (
                <span style={{ color: '#f59e0b', marginLeft: 6 }}>— oldest will be removed on save</span>
              )}
            </span>
          )}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 2fr 1fr', gap: 12, marginBottom: 10 }}>
          <div>
            <label style={labelStyle}>Ticker Symbol *</label>
            <input
              type="text"
              value={tickerSymbol}
              onChange={e => setTickerSymbol(e.target.value.toUpperCase())}
              placeholder="SPWR"
              maxLength={10}
              disabled={!!savedIds}
              style={{ ...inputStyle, opacity: savedIds ? 0.5 : 1 }}
            />
          </div>
          <div>
            <label style={{ ...labelStyle, color: '#475569' }}>Formerly (if renamed)</label>
            <input
              type="text"
              value={formerSymbol}
              onChange={e => setFormerSymbol(e.target.value.toUpperCase())}
              placeholder="CSLR"
              maxLength={10}
              disabled={!!savedIds}
              style={{ ...inputStyle, opacity: savedIds ? 0.5 : 1, borderColor: formerSymbol.trim() ? '#f59e0b' : '#2d3748', color: formerSymbol.trim() ? '#fcd34d' : '#e2e8f0' }}
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
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12, marginBottom: 14 }}>
          <div>
            <label style={labelStyle}>Short Name</label>
            <input
              type="text"
              value={shortName}
              onChange={e => setShortName(e.target.value)}
              placeholder="Amprius"
              disabled={!!savedIds}
              style={{ ...inputStyle, opacity: savedIds ? 0.5 : 1 }}
            />
          </div>
          <div>
            <label style={labelStyle}>Title</label>
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Auto-generated from Short Name, Ticker, and Date"
              disabled={!!savedIds}
              style={{ ...inputStyle, opacity: savedIds ? 0.5 : 1 }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Analyze */}
          <button
            onClick={handleAnalyze}
            disabled={loading || !!analysis}
            style={{
              padding: '9px 24px',
              background: loading ? '#1d4ed8'
                        : analysis ? '#15803d'
                        : canAnalyze ? '#3b82f6'
                        : '#334155',
              color: (loading || analysis || canAnalyze) ? '#fff' : '#64748b',
              border: 'none',
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 600,
              cursor: (loading || !!analysis) ? 'default' : canAnalyze ? 'pointer' : 'not-allowed',
              transition: 'background 0.2s',
            }}
          >
            {loading ? 'Analyzing…' : analysis ? 'Analyzed ✓' : 'Analyze'}
          </button>

          {/* Save */}
          <button
            onClick={handleSave}
            disabled={!canSave && !savedIds}
            style={{
              padding: '9px 24px',
              background: saving ? '#1d4ed8'
                        : savedIds ? '#15803d'
                        : canSave ? '#3b82f6'
                        : '#334155',
              color: (saving || savedIds || canSave) ? '#fff' : '#64748b',
              border: 'none',
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 600,
              cursor: savedIds ? 'default' : canSave ? 'pointer' : 'not-allowed',
              transition: 'background 0.2s',
            }}
          >
            {saving ? 'Saving…' : savedIds ? 'Saved to RADAR ✓' : 'Save'}
          </button>

          {/* Clear */}
          <button
            onClick={handleClear}
            disabled={!canClear && !justCleared}
            style={{
              padding: '9px 20px',
              background: justCleared ? '#15803d'
                        : canClear ? '#3b82f6'
                        : '#334155',
              color: (justCleared || canClear) ? '#fff' : '#64748b',
              border: 'none',
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 600,
              cursor: canClear ? 'pointer' : 'default',
              transition: 'background 0.2s',
            }}
          >
            {justCleared ? 'Cleared ✓' : 'Clear'}
          </button>
        </div>

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

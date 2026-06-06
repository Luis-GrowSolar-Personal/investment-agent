/**
 * Admin.jsx — Per-owner portfolio configuration (merged with Users)
 *
 * One collapsible card per owner. Card header shows portfolio value,
 * goal progress, and account count. Four config sections per card:
 *   1. Identity & Capital  — display name, min position $, max positions, cash reserve, goal
 *   2. Risk Profile        — years to goal, barbell ratio, risk tolerance
 *   3. Tax & Account       — tax sensitivity, account purpose, benchmark
 *   4. Domain & Universe   — domains of interest, rebalancing behavior
 *
 * Page-level: + New Owner button, delete per card.
 */

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
// Full industry catalog. IDs are stable — stored in DB domainsOfInterest.
// The first 5 (solar → crypto) are Luis's existing circle of competence.
const DOMAIN_CATALOG = [
  // Clean Energy
  { id: 'solar',            label: 'Solar Energy',           group: 'Clean Energy' },
  { id: 'energy_storage',   label: 'Energy Storage',         group: 'Clean Energy' },
  { id: 'nuclear',          label: 'Nuclear Energy',         group: 'Clean Energy' },
  { id: 'utilities',        label: 'Utilities',              group: 'Clean Energy' },
  // Technology
  { id: 'semiconductors',   label: 'Semiconductors',         group: 'Technology' },
  { id: 'it_cloud',         label: 'IT / Cloud / Software',  group: 'Technology' },
  { id: 'ai_ml',            label: 'AI / Machine Learning',  group: 'Technology' },
  { id: 'crypto',           label: 'Crypto (mass adoption)', group: 'Technology' },
  { id: 'ev_mobility',      label: 'Electric Vehicles',      group: 'Technology' },
  { id: 'robotics',         label: 'Robotics / Automation',  group: 'Technology' },
  { id: 'space',            label: 'Space / Aerospace',      group: 'Technology' },
  // Healthcare
  { id: 'biotech',          label: 'Biotechnology',          group: 'Healthcare' },
  { id: 'pharma',           label: 'Pharmaceuticals',        group: 'Healthcare' },
  { id: 'medtech',          label: 'Medical Devices',        group: 'Healthcare' },
  { id: 'healthtech',       label: 'Digital Health',         group: 'Healthcare' },
  // Financials
  { id: 'fintech',          label: 'Fintech',                group: 'Financials' },
  { id: 'banking',          label: 'Banking / Finance',      group: 'Financials' },
  { id: 'insurance',        label: 'Insurance',              group: 'Financials' },
  // Consumer
  { id: 'ecommerce',        label: 'E-commerce / Retail',    group: 'Consumer' },
  { id: 'consumer_staples', label: 'Consumer Staples',       group: 'Consumer' },
  { id: 'food_bev',         label: 'Food & Beverage',        group: 'Consumer' },
  { id: 'media',            label: 'Media / Entertainment',  group: 'Consumer' },
  // Industrial
  { id: 'defense',          label: 'Defense',                group: 'Industrial' },
  { id: 'industrial',       label: 'Industrial / Mfg',       group: 'Industrial' },
  { id: 'logistics',        label: 'Logistics / Supply Chain', group: 'Industrial' },
  { id: 'infrastructure',   label: 'Infrastructure',         group: 'Industrial' },
  // Energy
  { id: 'oil_gas',          label: 'Oil & Gas',              group: 'Energy' },
  // Materials & Other
  { id: 'mining',           label: 'Mining / Metals',        group: 'Materials' },
  { id: 'chemicals',        label: 'Chemicals',              group: 'Materials' },
  { id: 'real_estate',      label: 'Real Estate / REITs',    group: 'Real Estate' },
  { id: 'telecom',          label: 'Telecom',                group: 'Communication' },
];

// Unique group order for rendering
const DOMAIN_GROUPS = [...new Set(DOMAIN_CATALOG.map(d => d.group))];

const DEFAULTS = {
  minPositionDollar: 1500,
  maxPositions:      15,
  cashReservePct:    5,
  estSpecRatio:      60,
  riskTolerance:     'moderate',
  taxSensitivity:    'moderate',
  accountPurpose:    'growth',
  benchmarkBaseline: 'QQQ',
  specExitSpeed:     'normal',
  newMoneyBehavior:  'highest_conviction',
};

function specCeiling(years) {
  if (years == null) return null;
  if (years >= 30) return 50;
  if (years >= 20) return 40;
  if (years >= 10) return 25;
  if (years >= 5)  return 15;
  return 5;
}

function effectiveMaxPositions(portfolioValue, minPosDollar, hardMax) {
  if (!portfolioValue || !minPosDollar) return hardMax ?? DEFAULTS.maxPositions;
  const computed = Math.floor(portfolioValue / minPosDollar);
  return Math.min(computed, hardMax ?? DEFAULTS.maxPositions);
}

function fmt(n) {
  if (n == null) return '—';
  return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

// ---------------------------------------------------------------------------
// Shared UI primitives
// ---------------------------------------------------------------------------
function SectionHeader({ title, subtitle }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{title}</div>
      {subtitle && <div style={{ fontSize: 11, color: '#334155', marginTop: 2 }}>{subtitle}</div>}
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 5, fontWeight: 500 }}>{label}</label>
      {children}
      {hint && <div style={{ fontSize: 11, color: '#334155', marginTop: 4 }}>{hint}</div>}
    </div>
  );
}

function TextInput({ value, onChange, placeholder, type = 'text', prefix, suffix, width = 180 }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      {prefix && <span style={{ fontSize: 12, color: '#475569' }}>{prefix}</span>}
      <input
        type={type}
        value={value ?? ''}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          width,
          background: '#0f1117',
          border: '1px solid #2d3748',
          borderRadius: 6,
          color: '#f1f5f9',
          fontSize: 13,
          padding: '7px 10px',
          outline: 'none',
        }}
      />
      {suffix && <span style={{ fontSize: 12, color: '#475569' }}>{suffix}</span>}
    </div>
  );
}

function SegmentedControl({ value, onChange, options }) {
  return (
    <div style={{ display: 'flex', gap: 0, borderRadius: 6, overflow: 'hidden', border: '1px solid #2d3748', width: 'fit-content' }}>
      {options.map((o, i) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          style={{
            padding: '6px 14px',
            fontSize: 12,
            fontWeight: value === o.value ? 700 : 400,
            background: value === o.value ? '#1e2330' : 'transparent',
            color: value === o.value ? '#f1f5f9' : '#475569',
            border: 'none',
            borderLeft: i > 0 ? '1px solid #2d3748' : 'none',
            cursor: 'pointer',
            transition: 'all 0.15s',
          }}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function ComputedBadge({ label, value, color = '#60a5fa' }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      background: color + '11', border: `1px solid ${color}33`,
      borderRadius: 6, padding: '5px 10px', marginTop: 6,
    }}>
      <span style={{ fontSize: 11, color: '#64748b' }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 700, color }}>{value}</span>
    </div>
  );
}

function DomainCheckbox({ domain, checked, onChange }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', marginBottom: 5 }}>
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(domain.id, e.target.checked)}
        style={{ accentColor: '#3b82f6', width: 13, height: 13, flexShrink: 0 }}
      />
      <span style={{ fontSize: 12, color: checked ? '#f1f5f9' : '#64748b' }}>{domain.label}</span>
    </label>
  );
}

// ---------------------------------------------------------------------------
// New Owner Modal
// ---------------------------------------------------------------------------
function NewOwnerModal({ onClose, onCreated }) {
  const { getToken } = useAuth();
  const [owner, setOwner]               = useState('');
  const [displayName, setDisplayName]   = useState('');
  const [enoughNumber, setEnoughNumber] = useState('');
  const [saving, setSaving]             = useState(false);
  const [err, setErr]                   = useState('');

  const handleCreate = async () => {
    if (!owner.trim()) { setErr('Owner name is required'); return; }
    setSaving(true); setErr('');
    try {
      const token = await getToken();
      const r = await fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          owner:        owner.trim(),
          displayName:  displayName.trim() || null,
          enoughNumber: enoughNumber ? Number(enoughNumber) : null,
        }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Create failed');
      onCreated(data);
      onClose();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={modalOverlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={modalBox}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: '#f1f5f9' }}>New Owner</span>
          <button onClick={onClose} style={ghostBtn}>✕</button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <label style={labelStyle}>
            Owner key <span style={{ color: '#f87171' }}>*</span>
            <input value={owner} onChange={e => setOwner(e.target.value)}
              placeholder="e.g. luis.morales" style={modalInputStyle} autoFocus />
            <span style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>Unique identifier, lowercase. Cannot be changed.</span>
          </label>
          <label style={labelStyle}>
            Display name
            <input value={displayName} onChange={e => setDisplayName(e.target.value)}
              placeholder="e.g. Luis" style={modalInputStyle} />
          </label>
          <label style={labelStyle}>
            Investment goal ($)
            <input type="number" value={enoughNumber} onChange={e => setEnoughNumber(e.target.value)}
              placeholder="e.g. 6000000" style={modalInputStyle} />
          </label>
        </div>

        {err && <div style={{ color: '#f87171', fontSize: 12, marginTop: 12 }}>{err}</div>}

        <div style={{ display: 'flex', gap: 10, marginTop: 22, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={cancelBtn}>Cancel</button>
          <button onClick={handleCreate} disabled={saving} style={saveBtn}>
            {saving ? 'Creating…' : 'Create owner'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Owner admin card
// ---------------------------------------------------------------------------
function OwnerAdminCard({ profile: initialProfile, portfolioValue, accountCount, onDelete }) {
  const { getToken } = useAuth();
  const [open, setOpen]       = useState(true);
  const [profile, setProfile] = useState(initialProfile);
  const [draft, setDraft]     = useState(null);
  const [saving, setSaving]   = useState(false);
  const [saved, setSaved]     = useState(false);
  const [err, setErr]         = useState('');

  // Convert DB values (0.0–1.0 ratios) → UI display values (0–100)
  function toUI(p) {
    return {
      ...p,
      // Ratio fields: scale 0.0–1.0 → 0–100 for display
      cashReservePct:    p.cashReservePct != null ? Math.round(p.cashReservePct * 100) : '',
      estSpecRatio:      p.estSpecRatio   != null ? Math.round(p.estSpecRatio * 100)   : '',
      // Numeric fields: normalize null → '' so !== '' guards work correctly
      minPositionDollar: p.minPositionDollar ?? '',
      maxPositions:      p.maxPositions      ?? '',
      enoughNumber:      p.enoughNumber      ?? '',
      yearsToGoal:       p.yearsToGoal       ?? '',
      displayName:       p.displayName       ?? '',
      domainsOfInterest: p.domainsOfInterest ?? [],
    };
  }

  function fromUI(d) {
    return {
      ...d,
      cashReservePct:    d.cashReservePct === '' ? null : Number(d.cashReservePct) / 100,
      estSpecRatio:      d.estSpecRatio   === '' ? null : Number(d.estSpecRatio)   / 100,
      minPositionDollar: d.minPositionDollar === '' ? null : Number(d.minPositionDollar),
      maxPositions:      d.maxPositions      === '' ? null : Number(d.maxPositions),
      enoughNumber:      d.enoughNumber      === '' ? null : Number(d.enoughNumber),
      yearsToGoal:       d.yearsToGoal       === '' ? null : Number(d.yearsToGoal),
      displayName:       d.displayName.trim() || null,
      domainsOfInterest: d.domainsOfInterest.length > 0 ? d.domainsOfInterest : null,
    };
  }

  const startEdit = () => setDraft(toUI(profile));
  const cancelEdit = () => { setDraft(null); setErr(''); };

  // Auto-initialize draft from profile if not already editing
  const set = (key, val) => setDraft(d => ({ ...(d ?? toUI(profile)), [key]: val }));

  const toggleDomain = (id, checked) => {
    setDraft(d => {
      const base = d ?? toUI(profile);
      return {
        ...base,
        domainsOfInterest: checked
          ? [...(base.domainsOfInterest ?? []), id]
          : (base.domainsOfInterest ?? []).filter(x => x !== id),
      };
    });
  };

  const save = async () => {
    setSaving(true); setErr('');
    try {
      const token = await getToken();
      const body  = fromUI(draft);
      const r = await fetch(`/api/users/${encodeURIComponent(profile.owner)}`, {
        method:  'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body:    JSON.stringify(body),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Save failed');
      setProfile(data);
      setDraft(null);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  const p = draft ?? toUI(profile);

  // Computed helpers
  const specCeil   = specCeiling(p.yearsToGoal !== '' ? Number(p.yearsToGoal) : null);
  const estRatio   = p.estSpecRatio !== '' ? Number(p.estSpecRatio) : null;
  const effSpecPct = estRatio != null ? 100 - estRatio : null;
  const effMax     = effectiveMaxPositions(
    portfolioValue,
    p.minPositionDollar !== '' ? Number(p.minPositionDollar) : DEFAULTS.minPositionDollar,
    p.maxPositions      !== '' ? Number(p.maxPositions)      : DEFAULTS.maxPositions,
  );

  // Goal progress (use saved profile value, not draft)
  const savedGoal = profile.enoughNumber;
  const goalPct   = savedGoal && portfolioValue
    ? Math.min(100, (portfolioValue / savedGoal) * 100)
    : null;
  const goalColor = goalPct == null ? '#3b82f6' : goalPct >= 100 ? '#4ade80' : goalPct >= 60 ? '#fbbf24' : '#3b82f6';

  const displayName = profile.displayName || profile.owner;

  return (
    <div style={{ border: '1px solid #1e2330', borderRadius: 10, marginBottom: 20, overflow: 'hidden' }}>
      {/* ── Card Header ── */}
      <div
        style={{ background: '#0f1117', padding: '14px 20px', cursor: 'pointer' }}
        onClick={() => setOpen(o => !o)}
      >
        {/* Top row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ color: '#94a3b8', fontSize: 13 }}>{open ? '▼' : '▶'}</span>
          <span style={{ fontWeight: 700, fontSize: 15, color: '#f1f5f9' }}>{displayName}</span>
          {profile.displayName && (
            <span style={{ fontSize: 11, color: '#475569' }}>{profile.owner}</span>
          )}

          {/* Account count pill */}
          {accountCount != null && (
            <span style={{
              fontSize: 11, fontWeight: 600, padding: '1px 7px', borderRadius: 4,
              background: '#1e293b', border: '1px solid #334155', color: '#94a3b8',
            }}>
              {accountCount} acct{accountCount !== 1 ? 's' : ''}
            </span>
          )}

          {portfolioValue != null && (
            <span style={{ fontSize: 12, color: '#64748b' }}>
              Portfolio: <strong style={{ color: '#94a3b8' }}>{fmt(portfolioValue)}</strong>
            </span>
          )}

          {saved && <span style={{ fontSize: 12, color: '#4ade80' }}>✓ Saved</span>}

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            {!draft ? (
              <button onClick={e => { e.stopPropagation(); startEdit(); }} style={editBtn}>✎ Edit</button>
            ) : (
              <>
                <button onClick={e => { e.stopPropagation(); save(); }} disabled={saving} style={saveBtn}>
                  {saving ? 'Saving…' : 'Save'}
                </button>
                <button onClick={e => { e.stopPropagation(); cancelEdit(); }} style={cancelBtn}>Cancel</button>
              </>
            )}
            <button
              onClick={e => { e.stopPropagation(); onDelete(profile.owner, displayName); }}
              title="Delete owner"
              style={deleteBtn}
            >✕</button>
          </div>
        </div>

        {/* Goal progress bar */}
        {goalPct != null && (
          <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ flex: 1, maxWidth: 300, height: 3, background: '#1e2330', borderRadius: 2 }}>
              <div style={{ width: `${goalPct}%`, height: '100%', background: goalColor, borderRadius: 2, transition: 'width 0.3s' }} />
            </div>
            <span style={{ fontSize: 11, color: '#64748b' }}>
              {fmt(portfolioValue)} / {fmt(savedGoal)}
              <span style={{ marginLeft: 6, color: goalColor, fontWeight: 600 }}>{goalPct.toFixed(1)}%</span>
            </span>
          </div>
        )}
        {goalPct == null && savedGoal && (
          <div style={{ marginTop: 6, fontSize: 11, color: '#475569' }}>
            Goal: {fmt(savedGoal)} — no portfolio data yet
          </div>
        )}
      </div>

      {/* ── Card Body ── */}
      {open && (
        <div style={{ background: '#0d1018', padding: '24px 28px' }}>
          {err && <div style={{ color: '#f87171', fontSize: 12, marginBottom: 16 }}>{err}</div>}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '28px 48px' }}>

            {/* ── Section 1: Identity & Capital ── */}
            <div>
              <SectionHeader
                title="Identity & Capital"
                subtitle="Owner display name, position count, and minimum meaningful investment size."
              />

              <Field label="Display name" hint="Friendly name shown in the UI. Leave blank to use the owner key.">
                <TextInput
                  value={p.displayName}
                  onChange={v => set('displayName', v)}
                  placeholder={profile.owner}
                  width={200}
                />
              </Field>

              <Field
                label="Minimum position size"
                hint="Positions smaller than this don't move the needle. Drives max position count."
              >
                <TextInput
                  value={p.minPositionDollar}
                  onChange={v => set('minPositionDollar', v)}
                  placeholder={String(DEFAULTS.minPositionDollar)}
                  type="number"
                  prefix="$"
                  width={140}
                />
                {portfolioValue != null && p.minPositionDollar !== '' && (
                  <ComputedBadge
                    label="Implied max from portfolio value:"
                    value={`${Math.floor(portfolioValue / Number(p.minPositionDollar))} positions`}
                    color="#60a5fa"
                  />
                )}
              </Field>

              <Field
                label="Hard cap on positions"
                hint="Even with a large portfolio, never exceed this many tickers."
              >
                <TextInput
                  value={p.maxPositions}
                  onChange={v => set('maxPositions', v)}
                  placeholder={String(DEFAULTS.maxPositions)}
                  type="number"
                  suffix="tickers max"
                  width={80}
                />
                {portfolioValue != null && (
                  <ComputedBadge
                    label="Effective max (binding constraint):"
                    value={`${effMax} positions`}
                    color="#a78bfa"
                  />
                )}
              </Field>

              <Field label="Cash reserve" hint="Keep this % as dry powder for new opportunities.">
                <TextInput
                  value={p.cashReservePct}
                  onChange={v => set('cashReservePct', v)}
                  placeholder={String(DEFAULTS.cashReservePct)}
                  type="number"
                  suffix="% of portfolio"
                  width={80}
                />
              </Field>

              <Field label="Investment goal">
                <TextInput
                  value={p.enoughNumber}
                  onChange={v => set('enoughNumber', v)}
                  placeholder="e.g. 6000000"
                  type="number"
                  prefix="$"
                  width={160}
                />
              </Field>
            </div>

            {/* ── Section 2: Risk Profile ── */}
            <div>
              <SectionHeader
                title="Risk Profile"
                subtitle="Sets the barbell ratio between established platforms and speculative names."
              />

              <Field
                label="Years to goal"
                hint="Automatically sets the maximum speculative allocation ceiling."
              >
                <TextInput
                  value={p.yearsToGoal}
                  onChange={v => set('yearsToGoal', v)}
                  placeholder="e.g. 25"
                  type="number"
                  suffix="years"
                  width={80}
                />
                {specCeil != null && (
                  <ComputedBadge
                    label="Speculative ceiling from time horizon:"
                    value={`${specCeil}%`}
                    color="#f59e0b"
                  />
                )}
              </Field>

              <Field
                label="Established / speculative split"
                hint="Barbell ratio. The speculative weight is limited by the ceiling above."
              >
                <TextInput
                  value={p.estSpecRatio}
                  onChange={v => set('estSpecRatio', v)}
                  placeholder={String(DEFAULTS.estSpecRatio)}
                  type="number"
                  suffix="% established"
                  width={80}
                />
                {estRatio != null && (
                  <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
                    <div style={{ display: 'flex', height: 8, width: 200, borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{ width: `${estRatio}%`, background: '#60a5fa' }} />
                      <div style={{ width: `${100 - estRatio}%`, background: '#f59e0b' }} />
                    </div>
                    <span style={{ fontSize: 11, color: '#60a5fa', fontWeight: 600 }}>{estRatio}% EST</span>
                    <span style={{ fontSize: 11, color: '#f59e0b', fontWeight: 600 }}>{100 - estRatio}% SPEC</span>
                  </div>
                )}
                {specCeil != null && effSpecPct != null && effSpecPct > specCeil && (
                  <div style={{ marginTop: 6, fontSize: 11, color: '#f87171' }}>
                    ⚠ Requested spec {effSpecPct}% exceeds time-horizon ceiling of {specCeil}% — allocator will cap at {specCeil}%
                  </div>
                )}
              </Field>

              <Field label="Risk tolerance">
                <SegmentedControl
                  value={p.riskTolerance || DEFAULTS.riskTolerance}
                  onChange={v => set('riskTolerance', v)}
                  options={[
                    { value: 'conservative', label: 'Conservative' },
                    { value: 'moderate',     label: 'Moderate' },
                    { value: 'aggressive',   label: 'Aggressive' },
                  ]}
                />
              </Field>
            </div>

            {/* ── Section 3: Tax & Account ── */}
            <div>
              <SectionHeader
                title="Tax & Account"
                subtitle="Controls how aggressively the allocator harvests losses and routes trims."
              />

              <Field
                label="Tax sensitivity"
                hint={
                  p.taxSensitivity === 'aggressive'
                    ? 'Harvest losses freely. Realise gains when better opportunities exist.'
                    : p.taxSensitivity === 'conservative'
                    ? 'Avoid realising gains. Prefer holding even at cap.'
                    : 'Balance tax cost against opportunity cost.'
                }
              >
                <SegmentedControl
                  value={p.taxSensitivity || DEFAULTS.taxSensitivity}
                  onChange={v => set('taxSensitivity', v)}
                  options={[
                    { value: 'aggressive',   label: 'Aggressive' },
                    { value: 'moderate',     label: 'Moderate' },
                    { value: 'conservative', label: 'Conservative' },
                  ]}
                />
              </Field>

              <Field label="Account purpose">
                <SegmentedControl
                  value={p.accountPurpose || DEFAULTS.accountPurpose}
                  onChange={v => set('accountPurpose', v)}
                  options={[
                    { value: 'growth',       label: 'Growth' },
                    { value: 'income',       label: 'Income' },
                    { value: 'preservation', label: 'Preservation' },
                  ]}
                />
              </Field>

              <Field
                label="Performance benchmark"
                hint="What 'beating the market' means for this portfolio."
              >
                <SegmentedControl
                  value={p.benchmarkBaseline || DEFAULTS.benchmarkBaseline}
                  onChange={v => set('benchmarkBaseline', v)}
                  options={[
                    { value: 'SPY',  label: 'SPY' },
                    { value: 'QQQ',  label: 'QQQ' },
                    { value: 'TMFC', label: 'TMFC' },
                  ]}
                />
              </Field>
            </div>

            {/* ── Section 4: Domain & Rebalancing ── */}
            <div>
              <SectionHeader
                title="Domain & Universe"
                subtitle="Filters the opportunity scanner and watchlist to your circle of competence."
              />

              <div style={{ marginBottom: 18 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <label style={{ fontSize: 12, color: '#94a3b8', fontWeight: 500 }}>
                    Domains of interest
                  </label>
                  <span style={{ fontSize: 11, color: '#475569' }}>
                    {(p.domainsOfInterest ?? []).length} selected
                  </span>
                </div>
                {/* Scrollable grouped picker */}
                <div style={{
                  border: '1px solid #2d3748', borderRadius: 6,
                  background: '#0f1117',
                  maxHeight: 280, overflowY: 'auto',
                  padding: '8px 12px',
                }}>
                  {DOMAIN_GROUPS.map((group, gi) => (
                    <div key={group} style={{ marginBottom: gi < DOMAIN_GROUPS.length - 1 ? 12 : 0 }}>
                      <div style={{
                        fontSize: 10, fontWeight: 700, color: '#334155',
                        letterSpacing: '0.07em', textTransform: 'uppercase',
                        marginBottom: 5, paddingBottom: 3,
                        borderBottom: '1px solid #1e2330',
                      }}>{group}</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px 4px' }}>
                        {DOMAIN_CATALOG.filter(d => d.group === group).map(d => (
                          <DomainCheckbox
                            key={d.id}
                            domain={d}
                            checked={(p.domainsOfInterest ?? []).includes(d.id)}
                            onChange={toggleDomain}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <SectionHeader
                title="Rebalancing"
                subtitle="Controls how the allocator behaves when new signals arrive."
              />

              <Field
                label="Speculative exit speed"
                hint={
                  p.specExitSpeed === 'fast'
                    ? 'Exit spec positions after 1 quarter of weakening. Barbell discipline.'
                    : p.specExitSpeed === 'patient'
                    ? 'Allow 2–3 quarters before escalating. More tolerance for short-term noise.'
                    : 'Standard graduated ratchet (3 quarters to full exit).'
                }
              >
                <SegmentedControl
                  value={p.specExitSpeed || DEFAULTS.specExitSpeed}
                  onChange={v => set('specExitSpeed', v)}
                  options={[
                    { value: 'fast',    label: 'Fast' },
                    { value: 'normal',  label: 'Normal' },
                    { value: 'patient', label: 'Patient' },
                  ]}
                />
              </Field>

              <Field
                label="New money behavior"
                hint="When fresh cash arrives, deploy to the highest-conviction Add, or spread across all underweight positions."
              >
                <SegmentedControl
                  value={p.newMoneyBehavior || DEFAULTS.newMoneyBehavior}
                  onChange={v => set('newMoneyBehavior', v)}
                  options={[
                    { value: 'highest_conviction', label: 'Top pick first' },
                    { value: 'distribute',          label: 'Distribute' },
                  ]}
                />
              </Field>
            </div>

          </div>

          {/* Save row */}
          {draft && (
            <div style={{ marginTop: 24, paddingTop: 20, borderTop: '1px solid #1e2330', display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              {err && <span style={{ fontSize: 12, color: '#f87171', alignSelf: 'center' }}>{err}</span>}
              <button onClick={cancelEdit} style={cancelBtn}>Cancel</button>
              <button onClick={save} disabled={saving} style={saveBtn}>
                {saving ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function Admin() {
  const { getToken } = useAuth();
  const [profiles, setProfiles]           = useState([]);
  const [portfolioValues, setPortfolioValues] = useState({});
  const [accountCounts, setAccountCounts] = useState({});
  const [loading, setLoading]             = useState(true);
  const [showNew, setShowNew]             = useState(false);
  const [deleteErr, setDeleteErr]         = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const token = await getToken();
      const [usersRes, dashRes] = await Promise.all([
        fetch('/api/users',     { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/dashboard', { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      const users = await usersRes.json();
      const dash  = await dashRes.json();

      const pvMap = {}, acMap = {};
      for (const d of (Array.isArray(dash) ? dash : [])) {
        pvMap[d.owner] = d.totalPortfolioValue;
      }
      // accountCount comes from /api/users enrichment
      for (const u of (Array.isArray(users) ? users : [])) {
        acMap[u.owner] = u.accountCount ?? 0;
      }

      if (usersRes.ok) setProfiles(users);
      setPortfolioValues(pvMap);
      setAccountCounts(acMap);
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (owner, displayName) => {
    setDeleteErr('');
    if (!window.confirm(`Delete owner "${displayName}"? This cannot be undone.`)) return;
    const token = await getToken();
    const r = await fetch(`/api/users/${encodeURIComponent(owner)}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await r.json();
    if (!r.ok) { setDeleteErr(data.error || 'Delete failed'); return; }
    setProfiles(prev => prev.filter(p => p.owner !== owner));
  };

  const handleCreated = (profile) => {
    setProfiles(prev => [...prev, { ...profile, accountCount: 0, totalPortfolioValue: 0 }]);
    setAccountCounts(prev => ({ ...prev, [profile.owner]: 0 }));
    setPortfolioValues(prev => ({ ...prev, [profile.owner]: 0 }));
  };

  return (
    <div style={{ maxWidth: 1000, margin: '32px auto', padding: '0 24px' }}>
      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>Admin</h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>
            Per-owner portfolio configuration. These settings drive the allocator, recommended moves, and opportunity scanner.
          </p>
        </div>
        <button onClick={() => setShowNew(true)} style={saveBtn}>+ New Owner</button>
      </div>

      {deleteErr && (
        <div style={{ background: '#450a0a', border: '1px solid #991b1b', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#f87171', fontSize: 13 }}>
          {deleteErr}
        </div>
      )}

      {loading ? (
        <div style={{ color: '#475569', fontSize: 13 }}>Loading…</div>
      ) : profiles.length === 0 ? (
        <div style={{ color: '#475569', fontSize: 13 }}>
          No owners found. Create one with the button above.
        </div>
      ) : (
        profiles.map(p => (
          <OwnerAdminCard
            key={p.owner}
            profile={p}
            portfolioValue={portfolioValues[p.owner] ?? null}
            accountCount={accountCounts[p.owner] ?? null}
            onDelete={handleDelete}
          />
        ))
      )}

      {showNew && (
        <NewOwnerModal onClose={() => setShowNew(false)} onCreated={handleCreated} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Style tokens
// ---------------------------------------------------------------------------
const editBtn = {
  background: 'transparent',
  border: '1px solid #2d3748',
  borderRadius: 6,
  color: '#94a3b8',
  cursor: 'pointer',
  fontSize: 12,
  padding: '5px 12px',
};
const saveBtn = {
  background: '#2563eb',
  border: 'none',
  borderRadius: 6,
  color: '#fff',
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 600,
  padding: '7px 18px',
};
const cancelBtn = {
  background: 'transparent',
  border: '1px solid #2d3748',
  borderRadius: 6,
  color: '#94a3b8',
  cursor: 'pointer',
  fontSize: 13,
  padding: '7px 14px',
};
const deleteBtn = {
  background: 'transparent',
  border: '1px solid #2d3748',
  borderRadius: 6,
  color: '#475569',
  cursor: 'pointer',
  fontSize: 13,
  padding: '5px 10px',
  transition: 'color 0.15s',
};
const ghostBtn = {
  background: 'transparent',
  border: 'none',
  color: '#475569',
  cursor: 'pointer',
  fontSize: 16,
  padding: '2px 6px',
};
const labelStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
  fontSize: 12,
  color: '#94a3b8',
};
const modalInputStyle = {
  background: '#0f1117',
  border: '1px solid #2d3748',
  borderRadius: 6,
  color: '#f1f5f9',
  fontSize: 13,
  padding: '7px 10px',
  outline: 'none',
  width: '100%',
  boxSizing: 'border-box',
};
const modalOverlay = {
  position: 'fixed', inset: 0,
  background: 'rgba(0,0,0,0.6)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 200,
};
const modalBox = {
  background: '#0f1117',
  border: '1px solid #1e2330',
  borderRadius: 10,
  padding: 24,
  width: 420,
  maxWidth: '90vw',
};

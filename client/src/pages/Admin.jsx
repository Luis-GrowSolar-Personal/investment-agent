/**
 * Admin.jsx — Per-owner portfolio configuration
 *
 * One collapsible card per owner. Each card has four sections:
 *   1. Capital & Sizing       — min position $, max positions, cash reserve
 *   2. Risk Profile           — years to goal, barbell ratio, risk tolerance
 *   3. Tax & Account          — tax sensitivity, account purpose, benchmark
 *   4. Domain & Universe      — domains of interest, rebalancing behavior
 *
 * All values feed directly into the allocator and recommended-moves engine.
 * Computed helpers (spec ceiling, effective max positions) shown inline.
 */

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const DOMAINS = [
  { id: 'solar',           label: 'Solar Energy',         tier: 1 },
  { id: 'energy_storage',  label: 'Energy Storage',       tier: 1 },
  { id: 'semiconductors',  label: 'Semiconductors',       tier: 1 },
  { id: 'it_cloud',        label: 'IT / Cloud / Software', tier: 2 },
  { id: 'crypto',          label: 'Crypto (mass adoption)', tier: 2 },
];

const DEFAULTS = {
  minPositionDollar: 1500,
  maxPositions:      15,
  cashReservePct:    5,       // stored as 0-100 in UI, 0.0-1.0 in DB
  estSpecRatio:      60,      // stored as 0-100 in UI, 0.0-1.0 in DB
  riskTolerance:     'moderate',
  taxSensitivity:    'moderate',
  accountPurpose:    'growth',
  benchmarkBaseline: 'QQQ',
  specExitSpeed:     'normal',
  newMoneyBehavior:  'highest_conviction',
};

// Spec ceiling from years to goal
function specCeiling(years) {
  if (years == null) return null;
  if (years >= 30) return 50;
  if (years >= 20) return 40;
  if (years >= 10) return 25;
  if (years >= 5)  return 15;
  return 5;
}

// Effective max positions from portfolio value and min position dollar
function effectiveMaxPositions(portfolioValue, minPosDollar, hardMax) {
  if (!portfolioValue || !minPosDollar) return hardMax ?? DEFAULTS.maxPositions;
  const computed = Math.floor(portfolioValue / minPosDollar);
  return Math.min(computed, hardMax ?? DEFAULTS.maxPositions);
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

function Select({ value, onChange, options, width = 200 }) {
  return (
    <select
      value={value ?? ''}
      onChange={e => onChange(e.target.value)}
      style={{
        width,
        background: '#0f1117',
        border: '1px solid #2d3748',
        borderRadius: 6,
        color: value ? '#f1f5f9' : '#475569',
        fontSize: 13,
        padding: '7px 10px',
        outline: 'none',
        cursor: 'pointer',
      }}
    >
      <option value="">— not set —</option>
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
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
  const tierColors = { 1: '#34d399', 2: '#60a5fa' };
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 8 }}>
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(domain.id, e.target.checked)}
        style={{ accentColor: tierColors[domain.tier], width: 14, height: 14 }}
      />
      <span style={{ fontSize: 13, color: '#f1f5f9' }}>{domain.label}</span>
      <span style={{
        fontSize: 10, fontWeight: 700, padding: '1px 5px', borderRadius: 3,
        background: tierColors[domain.tier] + '22', color: tierColors[domain.tier],
        border: `1px solid ${tierColors[domain.tier]}44`,
      }}>T{domain.tier}</span>
    </label>
  );
}

// ---------------------------------------------------------------------------
// Owner admin card
// ---------------------------------------------------------------------------
function OwnerAdminCard({ profile: initialProfile, portfolioValue }) {
  const { getToken } = useAuth();
  const [open, setOpen]       = useState(true);
  const [profile, setProfile] = useState(initialProfile);
  const [draft, setDraft]     = useState(null);   // null = not editing
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
      domainsOfInterest: p.domainsOfInterest ?? [],
    };
  }

  // Convert UI values back to DB format
  function fromUI(d) {
    return {
      ...d,
      cashReservePct: d.cashReservePct === '' ? null : Number(d.cashReservePct) / 100,
      estSpecRatio:   d.estSpecRatio   === '' ? null : Number(d.estSpecRatio)   / 100,
      domainsOfInterest: d.domainsOfInterest.length > 0 ? d.domainsOfInterest : null,
    };
  }

  const startEdit = () => setDraft(toUI(profile));
  const cancelEdit = () => { setDraft(null); setErr(''); };

  // If draft is null when a field changes, auto-initialize from profile
  // so every field is populated before applying the delta.
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

  const p = draft ?? toUI(profile);   // always render from draft if editing

  // Computed helpers
  const specCeil    = specCeiling(p.yearsToGoal !== '' ? Number(p.yearsToGoal) : null);
  const estRatio    = p.estSpecRatio !== '' ? Number(p.estSpecRatio) : null;
  const effSpecPct  = estRatio != null ? 100 - estRatio : null;
  const effMax      = effectiveMaxPositions(
    portfolioValue,
    p.minPositionDollar !== '' ? Number(p.minPositionDollar) : DEFAULTS.minPositionDollar,
    p.maxPositions !== '' ? Number(p.maxPositions) : DEFAULTS.maxPositions,
  );

  const displayName = profile.displayName || profile.owner;

  return (
    <div style={{ border: '1px solid #1e2330', borderRadius: 10, marginBottom: 20, overflow: 'hidden' }}>
      {/* Header */}
      <div
        style={{ background: '#0f1117', padding: '14px 20px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12 }}
        onClick={() => setOpen(o => !o)}
      >
        <span style={{ color: '#94a3b8', fontSize: 13 }}>{open ? '▼' : '▶'}</span>
        <span style={{ fontWeight: 700, fontSize: 15, color: '#f1f5f9' }}>{displayName}</span>
        {portfolioValue != null && (
          <span style={{ fontSize: 12, color: '#64748b' }}>
            Portfolio: <strong style={{ color: '#94a3b8' }}>${portfolioValue.toLocaleString('en-US', { maximumFractionDigits: 0 })}</strong>
          </span>
        )}
        {saved && <span style={{ fontSize: 12, color: '#4ade80', marginLeft: 8 }}>✓ Saved</span>}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          {!draft ? (
            <button
              onClick={e => { e.stopPropagation(); startEdit(); }}
              style={editBtn}
            >✎ Edit</button>
          ) : (
            <>
              <button onClick={e => { e.stopPropagation(); save(); }} disabled={saving} style={saveBtn}>
                {saving ? 'Saving…' : 'Save'}
              </button>
              <button onClick={e => { e.stopPropagation(); cancelEdit(); }} style={cancelBtn}>Cancel</button>
            </>
          )}
        </div>
      </div>

      {open && (
        <div style={{ background: '#0d1018', padding: '24px 28px' }}>
          {err && <div style={{ color: '#f87171', fontSize: 12, marginBottom: 16 }}>{err}</div>}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '28px 48px' }}>

            {/* ── Section 1: Capital & Sizing ── */}
            <div>
              <SectionHeader
                title="Capital & Sizing"
                subtitle="Controls position count and minimum meaningful investment size."
              />

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
                {portfolioValue != null && p.minPositionDollar && (
                  <ComputedBadge
                    label="Implied max positions from portfolio value:"
                    value={`${Math.floor(portfolioValue / Number(p.minPositionDollar))} positions`}
                    color="#60a5fa"
                  />
                )}
              </Field>

              <Field
                label="Hard cap on positions"
                hint="Even with large portfolio, never exceed this many tickers."
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

              <Field
                label="Cash reserve"
                hint="Keep this % as dry powder for new opportunities."
              >
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
                  value={p.enoughNumber ?? ''}
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
                  value={p.yearsToGoal ?? ''}
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
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <TextInput
                    value={p.estSpecRatio}
                    onChange={v => set('estSpecRatio', v)}
                    placeholder={String(DEFAULTS.estSpecRatio)}
                    type="number"
                    suffix="% established"
                    width={80}
                  />
                </div>
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

              <Field label="Domains of interest">
                {DOMAINS.map(d => (
                  <DomainCheckbox
                    key={d.id}
                    domain={d}
                    checked={(p.domainsOfInterest ?? []).includes(d.id)}
                    onChange={toggleDomain}
                  />
                ))}
              </Field>

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
                    { value: 'fast',   label: 'Fast' },
                    { value: 'normal', label: 'Normal' },
                    { value: 'patient', label: 'Patient' },
                  ]}
                />
              </Field>

              <Field
                label="New money behavior"
                hint="When fresh cash arrives, deploy it to the highest-conviction Add, or spread across all underweight positions."
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

          </div>{/* end grid */}

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
  const [profiles, setProfiles]       = useState([]);
  const [portfolioValues, setPortfolioValues] = useState({});
  const [loading, setLoading]         = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        const [usersRes, dashRes] = await Promise.all([
          fetch('/api/users',     { headers: { Authorization: `Bearer ${token}` } }),
          fetch('/api/dashboard', { headers: { Authorization: `Bearer ${token}` } }),
        ]);
        const users = await usersRes.json();
        const dash  = await dashRes.json();

        // Build portfolio value lookup by owner
        const pvMap = {};
        for (const d of (Array.isArray(dash) ? dash : [])) {
          pvMap[d.owner] = d.totalPortfolioValue;
        }

        if (usersRes.ok) setProfiles(users);
        setPortfolioValues(pvMap);
      } finally {
        setLoading(false);
      }
    })();
  }, [getToken]);

  return (
    <div style={{ maxWidth: 1000, margin: '32px auto', padding: '0 24px' }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>Admin</h1>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>
          Per-owner portfolio configuration. These settings drive the allocator, recommended moves, and opportunity scanner.
        </p>
      </div>

      {loading ? (
        <div style={{ color: '#475569', fontSize: 13 }}>Loading…</div>
      ) : profiles.length === 0 ? (
        <div style={{ color: '#475569', fontSize: 13 }}>
          No owners found. Add owners in the <strong style={{ color: '#94a3b8' }}>Users</strong> tab first.
        </div>
      ) : (
        profiles.map(p => (
          <OwnerAdminCard
            key={p.owner}
            profile={p}
            portfolioValue={portfolioValues[p.owner] ?? null}
          />
        ))
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Button styles
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

/**
 * PortfolioManager.jsx — Actionable rebalancing plan (Moves engine).
 *
 * Coming next: per-account buy/sell plan with specific $ amounts,
 * capital flow routing, and tax-aware ordering.
 */

export default function PortfolioManager() {
  return (
    <div style={{ maxWidth: 900, margin: '64px auto', padding: '0 24px', textAlign: 'center' }}>
      <div style={{ fontSize: 32, marginBottom: 16 }}>📋</div>
      <h1 style={{ margin: '0 0 10px', fontSize: 22, fontWeight: 700, color: '#f1f5f9' }}>
        Portfolio Manager
      </h1>
      <p style={{ margin: '0 0 32px', fontSize: 14, color: '#64748b', maxWidth: 480, margin: '0 auto 32px' }}>
        Your actionable rebalancing plan — specific buy/sell amounts per account,
        capital flow routing, and tax-aware ordering. Coming next.
      </p>

      <div style={{
        display: 'inline-flex', flexDirection: 'column', gap: 12,
        background: '#0f1117', border: '1px solid #1e2330',
        borderRadius: 10, padding: '24px 32px', textAlign: 'left',
      }}>
        {[
          'Trim 47 shares SPWR from Taxable → $680 freed, $0 tax (loss position)',
          'Buy $680 META — Add signal, improving trajectory, Type B',
          'TSLA at 38% — over Type B cap of 35%, flag for 48h review',
        ].map((line, i) => (
          <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <span style={{ color: '#334155', fontSize: 12, marginTop: 1, flexShrink: 0 }}>{i + 1}.</span>
            <span style={{ fontSize: 13, color: '#475569' }}>{line}</span>
          </div>
        ))}
        <div style={{ marginTop: 8, fontSize: 11, color: '#334155', fontStyle: 'italic' }}>
          Preview of what's coming — not yet live
        </div>
      </div>
    </div>
  );
}

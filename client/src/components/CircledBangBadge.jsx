/**
 * Small circled "!" indicator — a low-noise "needs your attention" marker that
 * sits inline beside text without competing with it.
 *
 * Extracted from Radar.jsx's StaleTranscriptBadge (which was the only instance)
 * when the Moves tab needed the same visual for pending-execution. The visual is
 * generic; the meaning is not — callers own the colour and the tooltip.
 *
 * Props:
 *  - color: border + glyph colour (callers pass a semantic token, e.g. amber for
 *    "attention", red for "overdue")
 *  - title: hover tooltip text. Always pass one — the badge is meaningless
 *    without it, since the glyph alone says nothing about what's wrong.
 */
export default function CircledBangBadge({ color, title }) {
  return (
    <span
      title={title}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 14,
        height: 14,
        borderRadius: '50%',
        border: `1.5px solid ${color}`,
        color,
        fontSize: 9,
        fontWeight: 800,
        marginLeft: 4,
        cursor: 'help',
        lineHeight: 1,
        flexShrink: 0,
      }}
    >
      !
    </span>
  );
}

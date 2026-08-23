import { useRef } from 'react';

/**
 * Horizontally scrollable container with click-and-drag panning.
 *
 * Extracted verbatim from Radar.jsx (where it had been the only usage) so
 * Portfolio's positions table and PortfolioManager's Recommended Moves grid
 * can share one proven implementation instead of each growing its own.
 *
 * Props:
 *  - style: merged OVER the functional defaults (overflowX/cursor). Radar's
 *    card chrome (background/border/radius/padding) used to be hardcoded in
 *    here; it now comes from the caller, so this component stays neutral in
 *    layouts that don't want a card around their content.
 *  - suppressClickAfterDrag: when true, a click that lands after the pointer
 *    moved past the 5px threshold is swallowed in the capture phase. Needed
 *    wherever rows/cells carry their own onClick (Portfolio's <tr> toggles
 *    expand; MoveRow's cells do too) — without it, panning the table also
 *    toggles whatever you dragged across. Defaults to false so Radar, whose
 *    content has no such handlers, behaves exactly as it always has.
 */
export default function DragScrollContainer({ children, style, suppressClickAfterDrag = false }) {
  const ref = useRef(null);
  const drag = useRef({ active: false, startX: 0, scrollLeft: 0, moved: false });

  function onMouseDown(e) {
    // Only initiate on the container itself or non-interactive children.
    // closest() rather than a bare tagName check so buttons whose content is an
    // icon still count as interactive — a press on Portfolio's rename <svg>
    // reports tagName 'svg'/'path' and would otherwise start a drag.
    if (e.target.closest?.('button, a, input, select, textarea')) {
      // Clear the flag even on this early return. A drag that ended via
      // onMouseLeave (pointer released outside) leaves moved === true with no
      // click having fired to clear it, so without this the next click on an
      // interactive element gets eaten by onClickCapture.
      drag.current.moved = false;
      return;
    }
    const el = ref.current;
    drag.current = { active: true, startX: e.pageX - el.offsetLeft, scrollLeft: el.scrollLeft, moved: false };
    el.style.cursor = 'grabbing';
    el.style.userSelect = 'none';
  }

  function onMouseMove(e) {
    if (!drag.current.active) return;
    const el = ref.current;
    const x = e.pageX - el.offsetLeft;
    const delta = x - drag.current.startX;
    if (Math.abs(delta) > 5) drag.current.moved = true;
    if (drag.current.moved) {
      e.preventDefault();
      el.scrollLeft = drag.current.scrollLeft - delta;
    }
  }

  function onMouseUp() {
    if (!ref.current) return;
    drag.current.active = false;
    ref.current.style.cursor = 'grab';
    ref.current.style.userSelect = '';
  }

  // Capture phase so this runs before any child's onClick.
  function onClickCapture(e) {
    if (!suppressClickAfterDrag) return;
    if (!drag.current.moved) return;
    drag.current.moved = false;
    e.stopPropagation();
    e.preventDefault();
  }

  return (
    <div
      ref={ref}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
      onClickCapture={onClickCapture}
      style={{
        overflowX: 'auto',
        cursor: 'grab',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

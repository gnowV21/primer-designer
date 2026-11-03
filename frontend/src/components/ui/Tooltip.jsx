import { useState, useRef } from 'react';
import { createPortal } from 'react-dom';

const SHOW_DELAY = 250; // ms — avoids flash when moving cursor past icon rows

export default function Tooltip({ text }) {
  const [visible, setVisible] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0, side: 'right' });
  const btnRef  = useRef(null);
  const timerRef = useRef(null);

  function computePosition() {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    const side = window.innerWidth - rect.right < 290 ? 'left' : 'right';
    setCoords({
      top:  rect.top + rect.height / 2,
      left: side === 'right' ? rect.right + 10 : rect.left - 10,
      side,
    });
  }

  function handleShow() {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      computePosition();
      setVisible(true);
    }, SHOW_DELAY);
  }

  function handleHide() {
    clearTimeout(timerRef.current);
    setVisible(false);
  }

  return (
    <div className="relative inline-flex items-center shrink-0">
      <span
        ref={btnRef}
        role="button"
        tabIndex={0}
        onMouseEnter={handleShow}
        onMouseLeave={handleHide}
        onFocus={handleShow}
        onBlur={handleHide}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setVisible(v => !v)}
        className="w-4 h-4 rounded-full bg-slate-200 text-slate-500 text-xs font-bold flex items-center justify-center hover:bg-teal-100 hover:text-teal-700 focus:outline-none focus:ring-2 focus:ring-teal-200 transition-colors cursor-default select-none"
        aria-label="More information"
      >
        ?
      </span>

      {visible && createPortal(
        <div
          role="tooltip"
          style={{
            position: 'fixed',
            top: coords.top,
            transform: 'translateY(-50%)',
            ...(coords.side === 'right'
              ? { left: coords.left }
              : { right: window.innerWidth - coords.left }),
            zIndex: 9999,
            maxWidth: '17rem',
          }}
          className="px-3 py-2.5 rounded-xl bg-white border border-slate-200 text-slate-700 text-xs leading-relaxed shadow-xl pointer-events-none"
        >
          {/* Arrow */}
          <span
            style={{
              position: 'absolute',
              top: '50%',
              transform: 'translateY(-50%)',
              ...(coords.side === 'right'
                ? { left: '-6px', borderRight: '6px solid white' }
                : { right: '-6px', borderLeft: '6px solid white' }),
              borderTop: '5px solid transparent',
              borderBottom: '5px solid transparent',
            }}
          />
          {text}
        </div>,
        document.body
      )}
    </div>
  );
}

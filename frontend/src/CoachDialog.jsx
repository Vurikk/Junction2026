import React, { useEffect, useRef, useState } from 'react';

export default function CoachDialog({ open, onClose, children }) {
  const dialog = useRef(null);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    if (!open) return;
    const node = dialog.current;
    const trigger = document.activeElement;
    const scrollY = window.scrollY;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    node.showModal();
    const viewport = window.visualViewport;
    const resize = () => {
      node.style.setProperty('--coach-height', `${viewport?.height || window.innerHeight}px`);
      node.style.setProperty('--coach-top', `${viewport?.offsetTop || 0}px`);
    };
    resize();
    viewport?.addEventListener('resize', resize);
    viewport?.addEventListener('scroll', resize);
    return () => {
      viewport?.removeEventListener('resize', resize);
      viewport?.removeEventListener('scroll', resize);
      node.close();
      document.body.style.overflow = previousOverflow;
      window.scrollTo(0, scrollY);
      if (trigger?.isConnected) trigger.focus({ preventScroll: true });
    };
  }, [open]);
  function trapFocus(event) {
    if (event.key !== 'Tab') return;
    const items = [...dialog.current.querySelectorAll('button, input, select, summary, [tabindex="0"]')]
      .filter(item => !item.disabled && item.getClientRects().length);
    const target = event.shiftKey ? items.at(-1) : items[0];
    if (document.activeElement === (event.shiftKey ? items[0] : items.at(-1))) {
      event.preventDefault(); target?.focus();
    }
  }
  return <dialog ref={dialog} className={`coach-dialog${expanded ? ' expanded' : ''}`}
    aria-labelledby="coach-title" aria-modal="true"
    onKeyDown={trapFocus}
    onCancel={event => { event.preventDefault(); onClose(); }}>
    <div className="coach-dialog-heading"><h2 id="coach-title">Coach <small>Financial explanations</small></h2>
      <button type="button" className="coach-expand" aria-label={expanded ? 'Collapse Coach' : 'Expand Coach'}
        aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? '⌄' : '⌃'}</button>
      <button type="button" aria-label="Close Coach" autoFocus onClick={onClose}>×</button></div>
    {children}
  </dialog>;
}

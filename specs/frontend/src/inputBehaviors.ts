import type { FocusEvent, KeyboardEvent } from 'react';

// Enter confirms the current field and jumps to the next focusable field on the page,
// mirroring how engineers tab through the paper form top-to-bottom, left-to-right.
export function focusNextOnEnter(e: KeyboardEvent<HTMLInputElement | HTMLSelectElement>) {
  if (e.key !== 'Enter') return;
  e.preventDefault();
  const target = e.currentTarget;
  const focusable = Array.from(document.querySelectorAll<HTMLElement>(
    'input:not([type=checkbox]):not(:disabled), select:not(:disabled)',
  )).filter(el => el.tabIndex !== -1 && el.offsetParent !== null);
  const next = focusable[focusable.indexOf(target) + 1];
  if (next) {
    next.focus();
    if (next instanceof HTMLInputElement) next.select();
  } else {
    target.blur();
  }
}

// Selecting the whole value on focus lets a click/tab jump straight into overwriting
// it, without reaching for Delete first.
export function selectOnFocus(e: FocusEvent<HTMLInputElement>) {
  e.target.select();
}

// Fixed 2-decimal display once the engineer leaves the field; typing itself stays free-form.
export function roundTo2(value: string): string {
  if (value.trim() === '') return value;
  const num = Number(value);
  return Number.isNaN(num) ? value : num.toFixed(2);
}

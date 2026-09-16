import { useMemo, useRef, useState } from 'react';

export type SearchableOption = { value: string; label: string; search?: string };

const MAX_SHOWN = 300;

export function SearchableSelect({ options, value, onChange, placeholder = 'Hledat podle kódu nebo názvu…',
  disabled, emptyLabel = 'Nic nenalezeno.' }: {
  options: SearchableOption[]; value: string; onChange: (value: string) => void;
  placeholder?: string; disabled?: boolean; emptyLabel?: string;
}) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return options;
    return options.filter(o => (o.search ?? o.label.toLowerCase()).includes(q));
  }, [options, query]);

  const selected = options.find(o => o.value === value);
  const shown = filtered.slice(0, MAX_SHOWN);

  return (
    <div className="searchable-select" ref={wrapRef}
      onBlur={e => { if (!wrapRef.current?.contains(e.relatedTarget as Node)) setOpen(false); }}>
      <div className="searchable-select-field">
        <input type="text" autoComplete="off" disabled={disabled}
          placeholder={selected && !open ? selected.label : placeholder}
          value={open ? query : ''}
          onFocus={() => { setOpen(true); setQuery(''); }}
          onChange={e => { setQuery(e.target.value); setOpen(true); }} />
        <span className="searchable-select-count">
          {filtered.length !== options.length ? `${filtered.length} / ${options.length}` : options.length}
        </span>
      </div>
      {!open && selected && <div className="searchable-select-selected">
        Vybráno: <b>{selected.label}</b>
        {!disabled && <button type="button" onClick={() => onChange('')}>zrušit</button>}
      </div>}
      {open && <div className="searchable-select-list">
        {shown.map(o => <button type="button" key={o.value}
          className={`searchable-select-option ${o.value === value ? 'selected' : ''}`}
          onMouseDown={e => e.preventDefault()}
          onClick={() => { onChange(o.value); setOpen(false); setQuery(''); }}>{o.label}</button>)}
        {!shown.length && <div className="searchable-select-empty">{emptyLabel}</div>}
        {filtered.length > MAX_SHOWN && <div className="searchable-select-empty">
          Zobrazeno prvních {MAX_SHOWN} z {filtered.length}. Zpřesni hledání.
        </div>}
      </div>}
    </div>
  );
}

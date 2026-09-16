import { useState, type ReactNode } from 'react';
import type { Definition } from './types';
import { focusNextOnEnter, selectOnFocus, roundTo2 } from './inputBehaviors';

export type SheetRow = {
  key: string; definition_id: number; position_key: string; position_label: string;
  numeric_target: string; numeric_min: string; numeric_max: string;
  text_value: string; boolean_value: boolean; note: string; unit: string;
};

type Ctx = {
  rowByKey: Map<string, SheetRow>;
  updateRow: (key: string, patch: Partial<SheetRow>) => void;
  updateUnit: (definitionId: number, unit: string) => void;
};

// Mirrors the two-column layout of the ENGEL sheet in backend/app/pdf.py.
// Different presses reuse the same fixed layout, just with different units per field.
const LEFT_CATEGORIES = ['Zavření, otevření, výstřik', 'Vyhazovače', 'Hydraulické jádro', 'Poznámky'];
const HEADER_CATEGORY = 'Základní údaje';
const SEQUENCE_UNIT_OPTIONS = ['mm', 's', 'cm3'];
const ABSOLUTE_UNITS: Record<string, string> = {
  INJECTION_POSITION: 'cm3', INJECTION_SPEED: 'cm3/s', MAX_INJECTION_PRESSURE: 'bars abs',
  TRANSFER_PRESSURE: 'bars abs', PEAK_PRESSURE: 'bars abs', HOLDING_PRESSURE: 'bars abs', DOSING_SPEED: 'ot/min',
};
const RELATIVE_UNITS: Record<string, string> = {
  INJECTION_POSITION: 'mm', INJECTION_SPEED: 'mm/s', MAX_INJECTION_PRESSURE: 'bars',
  TRANSFER_PRESSURE: 'bars', PEAK_PRESSURE: 'bars', HOLDING_PRESSURE: 'bars', DOSING_SPEED: '%',
};

function byCode(definitions: Definition[], code: string) {
  return definitions.find(d => d.code === code);
}

function rowFor(ctx: Ctx, definition: Definition, position: { key: string; label: string }) {
  return ctx.rowByKey.get(`template-${definition.id}-${position.key || 'single'}`);
}

function maxFilledIndex(ctx: Ctx, definition: Definition | undefined): number {
  if (!definition) return 0;
  let max = 0;
  for (const position of definition.positions) {
    const row = rowFor(ctx, definition, position);
    const filled = row && (row.numeric_target !== '' || row.text_value !== '' || row.boolean_value);
    if (filled) {
      const index = Number(position.key);
      if (!Number.isNaN(index) && index > max) max = index;
    }
  }
  return max;
}

function numberInput(ctx: Ctx, row: SheetRow, field: 'numeric_target' | 'numeric_min' | 'numeric_max', placeholder?: string) {
  return <input type="number" step="any" value={row[field]} placeholder={placeholder}
    onFocus={selectOnFocus} onKeyDown={focusNextOnEnter}
    onChange={e => ctx.updateRow(row.key, { [field]: e.target.value } as Partial<SheetRow>)}
    onBlur={e => ctx.updateRow(row.key, { [field]: roundTo2(e.target.value) } as Partial<SheetRow>)} />;
}

function unitControl(ctx: Ctx, definition: Definition, row: SheetRow, options?: string[]) {
  if (options) return <select className="sheet-unit" value={row.unit || definition.unit}
    onChange={e => ctx.updateUnit(definition.id, e.target.value)}>
    {options.map(option => <option key={option} value={option}>{option}</option>)}
  </select>;
  return <input className="sheet-unit" value={row.unit} placeholder={definition.unit || 'jednotka'}
    title="Jednotka pro tento parametr" onChange={e => ctx.updateUnit(definition.id, e.target.value)} />;
}

function fieldBlock(ctx: Ctx, definition: Definition, unitOptions?: string[]) {
  const slots = definition.positions.length ? definition.positions : [{ key: '', label: '' }];
  const isTolerance = definition.code.endsWith('_TOLERANCE');
  const isNote = definition.code === 'SPECIAL_NOTE';
  const isMaterial = definition.code === 'RAW_MATERIAL';
  const anyRow = rowFor(ctx, definition, slots[0]);
  if (!anyRow) return null;
  return <div key={definition.id} className={`sheet-field ${slots.length > 1 ? 'sequence' : ''} ${isNote ? 'note' : ''}`}>
    <div className="sheet-field-head">
      <span>{definition.name}</span>
      {definition.value_type === 'NUMERIC' && unitControl(ctx, definition, anyRow, unitOptions)}
    </div>
    <div className="sheet-field-cells">
      {slots.map(position => {
        const row = rowFor(ctx, definition, position);
        if (!row) return null;
        if (isNote) return <textarea key={row.key} className="sheet-note-area" rows={4} value={row.text_value}
          placeholder="Volná poznámka k procesu" onChange={e => ctx.updateRow(row.key, { text_value: e.target.value })} />;
        if (isMaterial) return <label key={row.key} className="sheet-cell wide">
          <input list="sheet-materials" value={row.text_value} onFocus={selectOnFocus} onKeyDown={focusNextOnEnter}
            onChange={e => ctx.updateRow(row.key, { text_value: e.target.value })} placeholder="Vyber nebo napiš materiál" />
        </label>;
        if (definition.value_type === 'TEXT') return <label key={row.key} className="sheet-cell">
          {slots.length > 1 && <small>{position.label}</small>}
          <input value={row.text_value} onFocus={selectOnFocus} onKeyDown={focusNextOnEnter}
            onChange={e => ctx.updateRow(row.key, { text_value: e.target.value })} />
        </label>;
        if (definition.value_type === 'BOOLEAN') return <label key={row.key} className="sheet-cell checkbox">
          <input type="checkbox" checked={row.boolean_value}
            onChange={e => ctx.updateRow(row.key, { boolean_value: e.target.checked })} /> Ano
        </label>;
        if (isTolerance) return <label key={row.key} className="sheet-cell tolerance">
          {slots.length > 1 && <small>{position.label}</small>}
          <div className="sheet-minmax">{numberInput(ctx, row, 'numeric_min', 'min')}{numberInput(ctx, row, 'numeric_max', 'max')}</div>
        </label>;
        return <label key={row.key} className="sheet-cell">
          {slots.length > 1 && <small>{position.label}</small>}
          {numberInput(ctx, row, 'numeric_target')}
        </label>;
      })}
    </div>
  </div>;
}

function ToggleGate({ label, enabled, onChange, children }: {
  label: string; enabled: boolean; onChange: (value: boolean) => void; children: ReactNode;
}) {
  return <div className="sheet-gate">
    <div className="sheet-gate-toggle">
      <span>{label}</span>
      <div className="sheet-toggle-buttons">
        <button type="button" className={enabled ? 'active' : ''} onClick={() => onChange(true)}>Ano</button>
        <button type="button" className={!enabled ? 'active' : ''} onClick={() => onChange(false)}>Ne</button>
      </div>
    </div>
    {enabled && children}
  </div>;
}

function EjectorSection({ definitions, ctx }: { definitions: Definition[]; ctx: Ctx }) {
  const [enabled, setEnabled] = useState(true);
  const items = definitions.filter(d => d.category === 'Vyhazovače');
  return <ToggleGate label="Má forma vyhazovače?" enabled={enabled} onChange={setEnabled}>
    <div className="sheet-fields">{items.map(d => fieldBlock(ctx, d))}</div>
  </ToggleGate>;
}

const CORE_ROW_DEFS: [string, string][] = [
  ['Číslo jádra', 'CORE_NUMBER'], ['Název jádra', 'CORE_TITLE'],
  ['Priorita vyjeto', 'CORE_PRIORITY_OUT'], ['Priorita najeto', 'CORE_PRIORITY_IN'],
  ['Pozice vyjeto', 'CORE_POSITION_OUT'], ['Pozice najeto', 'CORE_POSITION_IN'],
  ['Rychlost vyjeto', 'CORE_SPEED_OUT'], ['Rychlost najeto', 'CORE_SPEED_IN'],
  ['Tlak vyjeto', 'CORE_PRESSURE_OUT'], ['Tlak najeto', 'CORE_PRESSURE_IN'],
];

function CoreSection({ definitions, ctx }: { definitions: Definition[]; ctx: Ctx }) {
  const coreDefinitions = definitions.filter(d => d.category === 'Hydraulické jádro');
  const number = byCode(coreDefinitions, 'CORE_NUMBER');
  const positions = number?.positions ?? [];
  const defaultCount = Math.max(...coreDefinitions.map(d => maxFilledIndex(ctx, d)), 0);
  const [enabled, setEnabled] = useState(defaultCount > 0);
  const [count, setCount] = useState(defaultCount || positions.length);
  if (!number) return null;
  return <ToggleGate label="Má forma hydraulické jádro?" enabled={enabled} onChange={setEnabled}>
    <label className="sheet-count">Počet jader
      <select value={count} onChange={e => setCount(Number(e.target.value))}>
        {positions.map((_, index) => <option key={index} value={index + 1}>{index + 1}</option>)}
      </select>
    </label>
    <div className="sheet-fields">
      {positions.slice(0, count).map(position => <div key={position.key} className="sheet-field core-card">
        <div className="sheet-field-head"><span>Jádro {position.label}</span></div>
        <div className="sheet-core-grid">
          {CORE_ROW_DEFS.map(([label, code]) => {
            const d = byCode(coreDefinitions, code);
            const row = d && rowFor(ctx, d, position);
            if (!d || !row) return null;
            return <label key={d.id} className="sheet-core-row">
              <small>{label}</small>
              {d.value_type === 'TEXT' ? <input value={row.text_value} onFocus={selectOnFocus} onKeyDown={focusNextOnEnter}
                  onChange={e => ctx.updateRow(row.key, { text_value: e.target.value })} />
                : numberInput(ctx, row, 'numeric_target')}
            </label>;
          })}
        </div>
      </div>)}
    </div>
  </ToggleGate>;
}

function HotRunnerSection({ definitions, ctx }: { definitions: Definition[]; ctx: Ctx }) {
  const definition = byCode(definitions, 'HOT_RUNNER_TEMPERATURE');
  const positions = definition?.positions ?? [];
  const defaultCount = Math.max(maxFilledIndex(ctx, definition), Math.min(10, positions.length));
  const [count, setCount] = useState(defaultCount);
  if (!definition) return null;
  const anyRow = rowFor(ctx, definition, positions[0] ?? { key: '', label: '' });
  return <div className="sheet-fields">
    <label className="sheet-count">Počet kanálů
      <select value={count} onChange={e => setCount(Number(e.target.value))}>
        {positions.map((_, index) => <option key={index} value={index + 1}>{index + 1}</option>)}
      </select>
    </label>
    {anyRow && <div className="sheet-field sequence">
      <div className="sheet-field-head"><span>{definition.name}</span>{unitControl(ctx, definition, anyRow)}</div>
      <div className="sheet-field-cells">
        {positions.slice(0, count).map(position => {
          const row = rowFor(ctx, definition, position);
          if (!row) return null;
          return <label key={row.key} className="sheet-cell"><small>{position.label}</small>{numberInput(ctx, row, 'numeric_target')}</label>;
        })}
      </div>
    </div>}
  </div>;
}

const SEQUENCE_CODES = ['SEQ_OPEN_INJECTION', 'SEQ_CLOSE_INJECTION', 'SEQ_OPEN_HOLDING', 'SEQ_CLOSE_HOLDING'];

function SequenceSection({ definitions, ctx }: { definitions: Definition[]; ctx: Ctx }) {
  const seqDefinitions = SEQUENCE_CODES.map(code => byCode(definitions, code)).filter((d): d is Definition => !!d);
  const positions = seqDefinitions[0]?.positions ?? [];
  const defaultCount = Math.max(...seqDefinitions.map(d => maxFilledIndex(ctx, d)), 1);
  const [count, setCount] = useState(Math.min(defaultCount, positions.length));
  if (!seqDefinitions.length) return null;
  return <div className="sheet-fields">
    <label className="sheet-count">Počet kaskád
      <select value={count} onChange={e => setCount(Number(e.target.value))}>
        {positions.map((_, index) => <option key={index} value={index + 1}>{index + 1}</option>)}
      </select>
    </label>
    <div className="sheet-legend">
      {seqDefinitions.map(d => {
        const row = rowFor(ctx, d, positions[0] ?? { key: '', label: '' });
        if (!row) return null;
        return <div key={d.id} className="sheet-legend-item"><span>{d.name}</span>{unitControl(ctx, d, row, SEQUENCE_UNIT_OPTIONS)}</div>;
      })}
    </div>
    {positions.slice(0, count).map(position => <div key={position.key} className="sheet-field core-card">
      <div className="sheet-field-head"><span>Kaskáda {position.label}</span></div>
      <div className="sheet-core-grid">
        {seqDefinitions.map(d => {
          const row = rowFor(ctx, d, position);
          if (!row) return null;
          return <label key={d.id} className="sheet-core-row"><small>{d.name}</small>{numberInput(ctx, row, 'numeric_target')}</label>;
        })}
      </div>
    </div>)}
  </div>;
}

function PairedFields({ title, a, b, ctx, defaultCount }: {
  title: string; a: Definition; b: Definition; ctx: Ctx; defaultCount: number;
}) {
  const positions = a.positions;
  const [count, setCount] = useState(defaultCount);
  return <div className="sheet-paired-group">
    <div className="sheet-field-head"><span>{title}</span></div>
    <label className="sheet-count">Počet políček
      <select value={count} onChange={e => setCount(Number(e.target.value))}>
        {positions.map((_, index) => <option key={index} value={index + 1}>{index + 1}</option>)}
      </select>
    </label>
    {positions.slice(0, count).map(position => {
      const rowA = rowFor(ctx, a, position), rowB = rowFor(ctx, b, position);
      if (!rowA || !rowB) return null;
      return <div key={position.key} className="sheet-field core-card">
        <div className="sheet-field-head"><span>{title} {position.label}</span></div>
        <div className="sheet-core-grid">
          <label className="sheet-core-row"><small>{a.name} {position.label}</small>{numberInput(ctx, rowA, 'numeric_target')}</label>
          <label className="sheet-core-row"><small>{b.name} {position.label}</small>{numberInput(ctx, rowB, 'numeric_target')}</label>
        </div>
      </div>;
    })}
  </div>;
}

const INJECTION_SINGLE_CODES = ['BOOSTING_PRESSURE', 'MAX_INJECTION_PRESSURE', 'TRANSFER_PRESSURE', 'PEAK_PRESSURE',
  'TRANSFER_POSITION', 'CUSHION', 'DOSING_STROKE', 'DECOMP_BEFORE', 'DECOMP_AFTER', 'DECOMP_SPEED', 'DOSING_TIME'];

function InjectionDosingSection({ definitions, ctx }: { definitions: Definition[]; ctx: Ctx }) {
  const speedDef = byCode(definitions, 'INJECTION_SPEED');
  const speedRow = speedDef && rowFor(ctx, speedDef, speedDef.positions[0]);
  const initialMode: 'absolute' | 'relative' = speedRow && speedRow.unit === ABSOLUTE_UNITS.INJECTION_SPEED ? 'absolute' : 'relative';
  const [mode, setMode] = useState<'absolute' | 'relative'>(initialMode);
  function applyMode(next: 'absolute' | 'relative') {
    setMode(next);
    const table = next === 'absolute' ? ABSOLUTE_UNITS : RELATIVE_UNITS;
    for (const [code, unit] of Object.entries(table)) {
      const definition = byCode(definitions, code);
      if (definition) ctx.updateUnit(definition.id, unit);
    }
  }
  const singles = INJECTION_SINGLE_CODES.map(code => byCode(definitions, code)).filter((d): d is Definition => !!d);
  const injectionPos = byCode(definitions, 'INJECTION_POSITION'), injectionSpeed = byCode(definitions, 'INJECTION_SPEED');
  const holdingTime = byCode(definitions, 'HOLDING_TIME_PROFILE'), holdingPressure = byCode(definitions, 'HOLDING_PRESSURE');
  const dosingSpeed = byCode(definitions, 'DOSING_SPEED'), backPressure = byCode(definitions, 'BACK_PRESSURE');
  return <div className="sheet-fields">
    <label className="sheet-count">Jednotky
      <select value={mode} onChange={e => applyMode(e.target.value as 'absolute' | 'relative')}>
        <option value="relative">Relativní (mm, mm/s, bars, %)</option>
        <option value="absolute">Absolutní (cm3, cm3/s, bars abs, ot/min)</option>
      </select>
    </label>
    {singles.map(d => fieldBlock(ctx, d))}
    {injectionPos && injectionSpeed && <PairedFields title="Vstřik" a={injectionPos} b={injectionSpeed} ctx={ctx}
      defaultCount={Math.max(maxFilledIndex(ctx, injectionPos), maxFilledIndex(ctx, injectionSpeed), 1)} />}
    {holdingTime && holdingPressure && <PairedFields title="Dotlak" a={holdingTime} b={holdingPressure} ctx={ctx}
      defaultCount={Math.max(maxFilledIndex(ctx, holdingTime), maxFilledIndex(ctx, holdingPressure), 1)} />}
    {dosingSpeed && backPressure && <PairedFields title="Dávkování" a={dosingSpeed} b={backPressure} ctx={ctx}
      defaultCount={Math.max(maxFilledIndex(ctx, dosingSpeed), maxFilledIndex(ctx, backPressure), 1)} />}
  </div>;
}

export function VisualSheetEditor({ definitions, rowByKey, updateRow, updateUnit, materials }: {
  definitions: Definition[];
  rowByKey: Map<string, SheetRow>;
  updateRow: (key: string, patch: Partial<SheetRow>) => void;
  updateUnit: (definitionId: number, unit: string) => void;
  materials: string[];
}) {
  const ctx: Ctx = { rowByKey, updateRow, updateUnit };
  const categories = Array.from(new Set(definitions.map(d => d.category))).filter(c => c !== HEADER_CATEGORY);
  const left = categories.filter(c => LEFT_CATEGORIES.includes(c));
  const right = categories.filter(c => !LEFT_CATEGORIES.includes(c));

  function sectionBody(category: string) {
    if (category === 'Vyhazovače') return <EjectorSection definitions={definitions} ctx={ctx} />;
    if (category === 'Hydraulické jádro') return <CoreSection definitions={definitions} ctx={ctx} />;
    if (category === 'Teplota horkých vtoků') return <HotRunnerSection definitions={definitions} ctx={ctx} />;
    if (category === 'Sekvence') return <SequenceSection definitions={definitions} ctx={ctx} />;
    if (category === 'Vstřikování, dávka, jednotka') return <InjectionDosingSection definitions={definitions} ctx={ctx} />;
    return <div className="sheet-fields">{definitions.filter(d => d.category === category).map(d => fieldBlock(ctx, d))}</div>;
  }

  const column = (names: string[]) => names.map(category => <section key={category} className="sheet-section">
    <h4>{category}</h4>
    {sectionBody(category)}
  </section>);

  return <div className="sheet">
    <datalist id="sheet-materials">{materials.map(m => <option key={m} value={m} />)}</datalist>
    <section className="sheet-section sheet-header">
      <h4>{HEADER_CATEGORY}</h4>
      <div className="sheet-fields">{definitions.filter(d => d.category === HEADER_CATEGORY).map(d => fieldBlock(ctx, d))}</div>
    </section>
    <div className="sheet-grid">
      <div className="sheet-column">{column(left)}</div>
      <div className="sheet-column">{column(right)}</div>
    </div>
  </div>;
}

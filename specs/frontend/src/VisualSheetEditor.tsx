import type { Definition } from './types';

export type SheetRow = {
  key: string; definition_id: number; position_key: string; position_label: string;
  numeric_target: string; numeric_min: string; numeric_max: string;
  text_value: string; boolean_value: boolean; note: string; unit: string;
};

// Mirrors the two-column layout of the ENGEL sheet in backend/app/pdf.py.
// Different presses reuse the same fixed layout, just with different units per field.
const LEFT_CATEGORIES = ['Zavření, otevření, výstřik', 'Vyhazovače', 'Hydraulické jádro', 'Poznámky'];
const HEADER_CATEGORY = 'Základní údaje';

export function VisualSheetEditor({ definitions, rowByKey, updateRow, updateUnit }: {
  definitions: Definition[];
  rowByKey: Map<string, SheetRow>;
  updateRow: (key: string, patch: Partial<SheetRow>) => void;
  updateUnit: (definitionId: number, unit: string) => void;
}) {
  const categories = Array.from(new Set(definitions.map(d => d.category))).filter(c => c !== HEADER_CATEGORY);
  const left = categories.filter(c => LEFT_CATEGORIES.includes(c));
  const right = categories.filter(c => !LEFT_CATEGORIES.includes(c));

  const rowFor = (definition: Definition, position: { key: string; label: string }) =>
    rowByKey.get(`template-${definition.id}-${position.key || 'single'}`);

  function field(definition: Definition) {
    const slots = definition.positions.length ? definition.positions : [{ key: '', label: '' }];
    const isTolerance = definition.code.endsWith('_TOLERANCE');
    const isNote = definition.code === 'SPECIAL_NOTE';
    const anyRow = rowFor(definition, slots[0]);
    if (!anyRow) return null;
    return <div key={definition.id} className={`sheet-field ${slots.length > 1 ? 'sequence' : ''} ${isNote ? 'note' : ''}`}>
      <div className="sheet-field-head">
        <span>{definition.name}</span>
        {definition.value_type === 'NUMERIC' && <input className="sheet-unit" value={anyRow.unit}
          placeholder={definition.unit || 'jednotka'} title="Jednotka pro tento parametr"
          onChange={e => updateUnit(definition.id, e.target.value)} />}
      </div>
      <div className="sheet-field-cells">
        {slots.map(position => {
          const row = rowFor(definition, position);
          if (!row) return null;
          if (isNote) return <textarea key={row.key} className="sheet-note-area" rows={4} value={row.text_value}
            placeholder="Volná poznámka k procesu" onChange={e => updateRow(row.key, { text_value: e.target.value })} />;
          if (definition.value_type === 'TEXT') return <label key={row.key} className="sheet-cell">
            {slots.length > 1 && <small>{position.label}</small>}
            <input value={row.text_value} onChange={e => updateRow(row.key, { text_value: e.target.value })} />
          </label>;
          if (definition.value_type === 'BOOLEAN') return <label key={row.key} className="sheet-cell checkbox">
            <input type="checkbox" checked={row.boolean_value}
              onChange={e => updateRow(row.key, { boolean_value: e.target.checked })} /> Ano
          </label>;
          if (isTolerance) return <label key={row.key} className="sheet-cell tolerance">
            {slots.length > 1 && <small>{position.label}</small>}
            <div className="sheet-minmax">
              <input type="number" step="any" placeholder="min" value={row.numeric_min}
                onChange={e => updateRow(row.key, { numeric_min: e.target.value })} />
              <input type="number" step="any" placeholder="max" value={row.numeric_max}
                onChange={e => updateRow(row.key, { numeric_max: e.target.value })} />
            </div>
          </label>;
          return <label key={row.key} className="sheet-cell">
            {slots.length > 1 && <small>{position.label}</small>}
            <input type="number" step="any" value={row.numeric_target}
              onChange={e => updateRow(row.key, { numeric_target: e.target.value })} />
          </label>;
        })}
      </div>
    </div>;
  }

  const column = (names: string[]) => names.map(category => <section key={category} className="sheet-section">
    <h4>{category}</h4>
    <div className="sheet-fields">{definitions.filter(d => d.category === category).map(field)}</div>
  </section>);

  return <div className="sheet">
    <section className="sheet-section sheet-header">
      <h4>{HEADER_CATEGORY}</h4>
      <div className="sheet-fields">{definitions.filter(d => d.category === HEADER_CATEGORY).map(field)}</div>
    </section>
    <div className="sheet-grid">
      <div className="sheet-column">{column(left)}</div>
      <div className="sheet-column">{column(right)}</div>
    </div>
  </div>;
}

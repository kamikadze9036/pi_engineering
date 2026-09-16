import { Fragment, useEffect, useMemo, useState } from 'react';
import { api, issuePdf, previewPdf, setSession } from './api';
import type { Definition, MesItem, Parameter, ProcessTemplate, Revision, Spec, Template, User } from './types';
import { SearchableSelect, type SearchableOption } from './SearchableSelect';
import { BugReportWidget } from './BugReportWidget';

type DraftRow = {
  key: string; definition_id: number; position_key: string; position_label: string;
  numeric_target: string; numeric_min: string; numeric_max: string;
  text_value: string; boolean_value: boolean; note: string;
};
type Draft = {
  product_name: string; material_name: string; process_note: string; change_reason: string;
  rows: DraftRow[];
};
type Audit = { id: number; action: string; actor_id: number; reason: string; created_at: string };

const labels: Record<Revision['status'], string> = {
  DRAFT: 'Rozpracováno', IN_REVIEW: 'Čeká na schválení',
  APPROVED: 'Schváleno', CANCELLED: 'Zrušeno',
};
const fromParameter = (p: Parameter, index: number): DraftRow => ({
  key: `${p.definition_id}-${p.position_key}-${index}`,
  definition_id: p.definition_id, position_key: p.position_key, position_label: p.position_label,
  numeric_target: p.numeric_target ?? '', numeric_min: p.numeric_min ?? '', numeric_max: p.numeric_max ?? '',
  text_value: p.text_value ?? '', boolean_value: p.boolean_value ?? false, note: p.note ?? '',
});
const emptyRow = (definition: Definition, position?: { key: string; label: string }): DraftRow => ({
  key: `template-${definition.id}-${position?.key ?? 'single'}`, definition_id: definition.id,
  position_key: position?.key ?? '', position_label: position?.label ?? '', numeric_target: '',
  numeric_min: '', numeric_max: '', text_value: '', boolean_value: false, note: '',
});
const toDraft = (revision: Revision, definitions: Definition[]): Draft => {
  const existing = new Map(revision.parameters.map((parameter, index) =>
    [`${parameter.definition_id}:${parameter.position_key}`, fromParameter(parameter, index)]));
  const rows = definitions.flatMap(definition => {
    const slots = definition.positions.length ? definition.positions : [{ key: '', label: '' }];
    return slots.map(position => {
      const saved = existing.get(`${definition.id}:${position.key}`);
      return saved ? { ...saved, key: `template-${definition.id}-${position.key || 'single'}` }
        : emptyRow(definition, position);
    });
  });
  return { product_name: revision.product_name, material_name: revision.material_name,
    process_note: revision.process_note, change_reason: revision.change_reason, rows };
};
const shownDate = (value: string | null) => value ? new Date(value).toLocaleString('cs-CZ') : '—';
const shownNumber = (value: string | null) => value === null ? '—'
  : new Intl.NumberFormat('cs-CZ', { maximumFractionDigits: 4 }).format(Number(value));

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [specs, setSpecs] = useState<Spec[]>([]);
  const [definitions, setDefinitions] = useState<Definition[]>([]);
  const [machines, setMachines] = useState<MesItem[]>([]);
  const [tools, setTools] = useState<MesItem[]>([]);
  const [processTemplates, setProcessTemplates] = useState<ProcessTemplate[]>([]);
  const [mesMode, setMesMode] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedRevisionId, setSelectedRevisionId] = useState<number | null>(null);
  const [machineRef, setMachineRef] = useState('');
  const [toolRef, setToolRef] = useState('');
  const [processTemplateId, setProcessTemplateId] = useState('');
  const [newTemplateName, setNewTemplateName] = useState('');
  const [newTemplateDescription, setNewTemplateDescription] = useState('');
  const [draft, setDraft] = useState<Draft | null>(null);
  const [returnReason, setReturnReason] = useState('');
  const [audit, setAudit] = useState<Audit[]>([]);
  const [template, setTemplate] = useState<Template | null>(null);
  const [templateForm, setTemplateForm] = useState<Template['settings'] & { title: string } | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<User>('/auth/me').then(current => { setUser(current); setSession(current); })
      .catch(() => { setUser(null); setSession(null); }).finally(() => setLoading(false));
  }, []);

  const selectedSpec = specs.find(s => s.id === selectedId) ?? null;
  const activeRevision = selectedSpec?.revisions.find(r => r.id === selectedRevisionId)
    ?? selectedSpec?.revisions.find(r => r.status === 'DRAFT' || r.status === 'IN_REVIEW')
    ?? selectedSpec?.revisions[0] ?? null;
  const currentRevision = selectedSpec?.revisions.find(r => r.id === selectedSpec.current_approved_revision_id) ?? null;

  useEffect(() => {
    if (!user) return;
    Promise.all([api<Spec[]>('/specs'), api<Definition[]>('/parameter-definitions'),
                 api<ProcessTemplate[]>('/process-templates')])
      .then(([allSpecs, defs, templates]) => {
        setSpecs(allSpecs); setDefinitions(defs); setProcessTemplates(templates);
        setProcessTemplateId(current => current || String(templates[0]?.id ?? ''));
      })
      .catch(e => setError(e.message));
    Promise.all([api<{ mode: string; items: MesItem[] }>('/mes/machines'),
                 api<{ mode: string; items: MesItem[] }>('/mes/tools')])
      .then(([machineResult, toolResult]) => {
        setMachines(machineResult.items); setTools(toolResult.items); setMesMode(machineResult.mode);
      }).catch(e => { setMesMode('NEDOSTUPNÉ MES'); setError(e.message); });
    api<Template>('/pdf-templates/current').then(t => {
      setTemplate(t); setTemplateForm({ title: t.title, ...t.settings });
    }).catch(() => {});
  }, [user]);

  useEffect(() => {
    setDraft(activeRevision?.status === 'DRAFT' && definitions.length > 0 &&
      (user?.role === 'ADMIN' || user?.id === activeRevision.created_by)
      ? toDraft(activeRevision, definitions) : null);
    if (activeRevision && user) {
      api<Audit[]>(`/revisions/${activeRevision.id}/audit`).then(setAudit).catch(() => setAudit([]));
    } else setAudit([]);
  }, [activeRevision?.id, activeRevision?.row_version, user, definitions]);

  const categories = useMemo(() => Array.from(new Set(definitions.map(d => d.category))), [definitions]);
  const definitionById = useMemo(() => new Map(definitions.map(d => [d.id, d])), [definitions]);
  const mesOptions = (items: MesItem[]): SearchableOption[] =>
    items.map(item => ({ value: item.ref, label: `${item.code} · ${item.name}`,
      search: `${item.code} ${item.name}`.toLowerCase() }));
  const machineOptions = useMemo(() => mesOptions(machines), [machines]);
  const toolOptions = useMemo(() => mesOptions(tools), [tools]);

  async function reload() {
    const result = await api<Spec[]>('/specs');
    setSpecs(result);
  }

  async function action(task: () => Promise<void>, success: string) {
    setBusy(true); setError(''); setMessage('');
    try { await task(); setMessage(success); }
    catch (e) { setError(e instanceof Error ? e.message : 'Operace se nepodařila.'); }
    finally { setBusy(false); }
  }

  async function login(event: React.FormEvent) {
    event.preventDefault();
    await action(async () => {
      const current = await api<User>('/auth/login', 'POST', { username, password });
      setSession(current); setUser(current); setPassword('');
    }, 'Přihlášení proběhlo.');
  }

  async function logout() {
    await action(async () => {
      await api('/auth/logout', 'POST');
      setSession(null); setUser(null); setSpecs([]); setSelectedId(null);
    }, 'Odhlášeno.');
  }

  async function createSpec(event: React.FormEvent) {
    event.preventDefault();
    await action(async () => {
      const created = await api<Spec>('/specs', 'POST', {
        machine_ref: machineRef, tool_ref: toolRef, template_id: Number(processTemplateId),
      });
      await reload(); setSelectedId(created.id); setSelectedRevisionId(created.revisions[0].id);
      setMachineRef(''); setToolRef('');
    }, 'Nový předpis a první rozpracovaná revize jsou připravené.');
  }

  async function saveAsProcessTemplate() {
    if (!activeRevision || !newTemplateName.trim()) return;
    await action(async () => {
      await api('/process-templates', 'POST', {
        revision_id: activeRevision.id, name: newTemplateName,
        description: newTemplateDescription,
      });
      const templates = await api<ProcessTemplate[]>('/process-templates');
      setProcessTemplates(templates); setNewTemplateName(''); setNewTemplateDescription('');
    }, 'Schválená revize byla uložena jako výchozí vzor pro nové návodky.');
  }

  function updateRow(key: string, patch: Partial<DraftRow>) {
    setDraft(old => old && { ...old, rows: old.rows.map(r => r.key === key ? { ...r, ...patch } : r) });
  }

  function addRow() {
    setDraft(old => old && { ...old, rows: [...old.rows, {
      key: crypto.randomUUID(), definition_id: 0, position_key: '', position_label: '',
      numeric_target: '', numeric_min: '', numeric_max: '', text_value: '',
      boolean_value: false, note: '',
    }] });
  }

  async function saveDraft() {
    if (!draft || !activeRevision) return;
    await action(async () => {
      const rows = draft.rows.filter(row => {
        const definition = definitionById.get(row.definition_id);
        if (!definition) return false;
        if (definition.value_type === 'NUMERIC') return row.numeric_target !== '';
        if (definition.value_type === 'TEXT') return row.text_value.trim() !== '';
        return true;
      });
      const parameters = rows.map(r => {
        const definition = definitionById.get(r.definition_id)!;
        return {
          definition_id: r.definition_id, position_key: r.position_key,
          position_label: r.position_label, note: r.note,
          numeric_target: definition.value_type === 'NUMERIC' ? (r.numeric_target || null) : null,
          numeric_min: definition.value_type === 'NUMERIC' ? (r.numeric_min || null) : null,
          numeric_max: definition.value_type === 'NUMERIC' ? (r.numeric_max || null) : null,
          text_value: definition.value_type === 'TEXT' ? r.text_value : null,
          boolean_value: definition.value_type === 'BOOLEAN' ? r.boolean_value : null,
        };
      });
      await api(`/revisions/${activeRevision.id}/draft`, 'PUT', {
        row_version: activeRevision.row_version, product_name: draft.product_name,
        material_name: draft.material_name, process_note: draft.process_note,
        change_reason: draft.change_reason, parameters,
      });
      await reload();
    }, 'Draft byl uložen.');
  }

  async function issueRevision() {
    if (!activeRevision) return;
    await action(async () => {
      await api(`/revisions/${activeRevision.id}/issue`, 'POST', { row_version: activeRevision.row_version });
      await issuePdf(activeRevision.id);
      await reload();
    }, 'Revize je vydaná, platná a PDF se otevřelo.');
  }

  function previewRevision() {
    if (!activeRevision) return;
    previewPdf(activeRevision.id);
  }

  async function review(approve: boolean) {
    if (!activeRevision) return;
    await action(async () => {
      await api(`/revisions/${activeRevision.id}/${approve ? 'approve' : 'return'}`, 'POST',
        approve ? { row_version: activeRevision.row_version }
          : { row_version: activeRevision.row_version, reason: returnReason });
      setReturnReason(''); await reload();
    }, approve ? 'Revize je schválená a platná.' : 'Revize byla vrácena k úpravě.');
  }

  async function newRevision() {
    if (!selectedSpec) return;
    await action(async () => {
      const created = await api<Revision>(`/specs/${selectedSpec.id}/revisions`, 'POST');
      await reload(); setSelectedRevisionId(created.id);
    }, 'Nová revize vznikla kopií platného předpisu.');
  }

  async function exportPdf(revision: Revision) {
    await action(() => issuePdf(revision.id), 'PDF bylo vydáno nebo otevřeno z archivu.');
  }

  async function publishTemplate(event: React.FormEvent) {
    event.preventDefault();
    if (!templateForm) return;
    await action(async () => {
      const created = await api<Template>('/pdf-templates', 'POST', templateForm);
      setTemplate(created);
    }, 'Nová verze PDF šablony je aktivní pro další vydané dokumenty.');
  }

  if (loading) return <div className="boot">Načítám předpisy…</div>;
  if (!user) return <main className="login-page">
    <div className="login-art"><span className="eyebrow">Procesní inženýrství</span>
      <h1>Technologické<br /><em>předpisy</em></h1>
      <p>Jeden schválený zdroj technologických hodnot. Historie revizí a operační návodka na jednom místě.</p>
      <div className="login-footer">MVP · interní test</div>
    </div>
    <form className="login-card" onSubmit={login}>
      <span className="eyebrow">Přístup do systému</span><h2>Přihlášení</h2>
      <label>Uživatelské jméno<input autoFocus value={username} onChange={e => setUsername(e.target.value)} required /></label>
      <label>Heslo<input type="password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
      {error && <p className="alert error">{error}</p>}
      <button className="primary full" disabled={busy}>Přihlásit se <span>→</span></button>
      <p className="muted tiny">Testovací účty a spuštění jsou popsané v README ve složce <code>specs</code>.</p>
    </form>
  </main>;

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><span className="brand-mark">TP</span><div><b>Technologické předpisy</b><small>operační návodky · revize · audit</small></div></div>
      <div className="topbar-right"><span className={`source ${mesMode === 'DEMO' ? 'demo' : ''}`}>{mesMode || 'MES…'}</span>
        <span className="user-label"><b>{user.name}</b><small>{user.role}</small></span>
        <button className="ghost" onClick={logout}>Odhlásit</button></div>
    </header>

    <div className="workspace">
      <aside className="sidebar">
        <div className="sidebar-heading"><span className="eyebrow">Evidence</span><h2>Předpisy <i>{specs.length}</i></h2></div>
        <div className="spec-list">
          {specs.map(spec => <button key={spec.id} className={`spec-item ${selectedId === spec.id ? 'selected' : ''}`}
            onClick={() => { setSelectedId(spec.id); setSelectedRevisionId(null); setMessage(''); setError(''); }}>
            <strong>{spec.machine_ref} <span>×</span> {spec.tool_ref}</strong>
            <small>{spec.current_approved_revision_id ? 'Platný předpis' : 'První draft'} · {spec.revisions.length} rev.</small>
            <span className={`dot ${spec.current_approved_revision_id ? 'approved' : 'draft'}`} />
          </button>)}
          {!specs.length && <p className="empty-side">Zatím žádný předpis.<br />Začni výběrem stroje a formy.</p>}
        </div>
        {(user.role === 'ENGINEER' || user.role === 'ADMIN') && <form className="new-spec" onSubmit={createSpec}>
          <span className="eyebrow">Nový předpis</span>
          <label>Stroj <small className="muted tiny">({machines.length})</small>
            <SearchableSelect options={machineOptions} value={machineRef} onChange={setMachineRef} placeholder="Vyber stroj" />
          </label>
          <label>Forma / nástroj <small className="muted tiny">({tools.length})</small>
            <SearchableSelect options={toolOptions} value={toolRef} onChange={setToolRef} placeholder="Vyber formu" />
          </label>
          <label className="template-choice">Výchozí vzor<select value={processTemplateId} onChange={e => setProcessTemplateId(e.target.value)} required>
            <option value="">Vyber vzor</option>{processTemplates.map(item => <option key={item.id} value={item.id}>
              {item.is_system ? 'Systémový' : 'Vlastní'} · {item.name} · {item.parameter_count} hodnot
            </option>)}
          </select><small>{processTemplates.find(item => String(item.id) === processTemplateId)?.description}</small></label>
          <button className="primary full" disabled={busy || !machineRef || !toolRef || !processTemplateId}>+ Založit draft ze vzoru</button>
        </form>}
      </aside>

      <main className="content">
        {message && <div className="alert success">{message}<button onClick={() => setMessage('')}>×</button></div>}
        {error && <div className="alert error">{error}<button onClick={() => setError('')}>×</button></div>}

        {!selectedSpec ? <section className="welcome">
          <span className="eyebrow">První verze systému</span><h1>Od hodnot k platné návodce.</h1>
          <p>Vyber stroj a formu, založ předpis a vyplň cílové hodnoty. Schválená revize zůstává neměnná; další změna vzniká jako její kopie.</p>
          <div className="steps"><div><b>01</b><strong>Draft</strong><small>Parametry a tolerance</small></div>
            <div><b>02</b><strong>Schválení</strong><small>Autor, důvod, audit</small></div>
            <div><b>03</b><strong>PDF návodka</strong><small>Platná revize pro tisk</small></div></div>
          {mesMode === 'DEMO' && <p className="demo-note">Právě používáš testovací číselník. Po připojení v práci ho nahradí export z Cyklades.</p>}
        </section> : <>
          <section className="page-heading">
            <div><span className="eyebrow">Předpis #{selectedSpec.id}</span>
              <h1>{selectedSpec.machine_ref} <span>×</span> {selectedSpec.tool_ref}</h1>
              <p>{currentRevision ? `Platná revize ${currentRevision.revision_number} · ${currentRevision.product_name}` : 'Zatím bez schválené revize'}</p></div>
            <div className="page-actions">
              {currentRevision && <button className="secondary" disabled={busy} onClick={() => exportPdf(currentRevision)}>↗ Vydat / otevřít PDF</button>}
              {currentRevision && (user.role === 'ENGINEER' || user.role === 'ADMIN')
                && !selectedSpec.revisions.some(r => r.status === 'DRAFT' || r.status === 'IN_REVIEW')
                && <button className="primary" disabled={busy} onClick={newRevision}>+ Nová revize</button>}
            </div>
          </section>

          <section className="revision-strip"><span className="eyebrow">Historie revizí</span><div>
            {selectedSpec.revisions.map(r => <button key={r.id}
              className={`revision-tab ${activeRevision?.id === r.id ? 'active' : ''}`}
              onClick={() => setSelectedRevisionId(r.id)}>
              <b>Revize {r.revision_number}</b><small>{labels[r.status]}</small>
            </button>)}
          </div></section>

          {activeRevision && <section className="revision-card">
            <div className="revision-card-head"><div><span className={`status ${activeRevision.status.toLowerCase()}`}>{labels[activeRevision.status]}</span>
              <h2>Revize {activeRevision.revision_number}</h2>
              <p>Vytvořeno {shownDate(activeRevision.created_at)} · {activeRevision.parameters.length} hodnot</p></div>
              {activeRevision.status === 'APPROVED' && <button className="secondary" onClick={() => exportPdf(activeRevision)}>↗ PDF této revize</button>}
            </div>

            {draft ? <div className="draft-editor">
              <div className="fields-grid">
                <label>Výrobek <span>*</span><input value={draft.product_name} onChange={e => setDraft({ ...draft, product_name: e.target.value })} placeholder="Název výrobku" /></label>
                <label>Materiál<input value={draft.material_name} onChange={e => setDraft({ ...draft, material_name: e.target.value })} placeholder="Vstupní materiál" /></label>
                <label>Důvod revize <span>*</span><input value={draft.change_reason} onChange={e => setDraft({ ...draft, change_reason: e.target.value })} placeholder="Co se mění a proč" /></label>
                <label>Procesní poznámka<input value={draft.process_note} onChange={e => setDraft({ ...draft, process_note: e.target.value })} placeholder="Volitelná instrukce" /></label>
              </div>
              <div className="table-heading"><div><span className="eyebrow">Technologické hodnoty</span><h3>Pole podle firemní návodky</h3></div>
                <button className="secondary" onClick={addRow}>+ Vlastní parametr</button></div>
              <p className="form-hint">Formulář obsahuje všechna pole z dodané návodky. Prázdné hodnoty se do revize neukládají, v PDF zůstanou jako prázdné buňky.</p>
              <div className="parameter-rows">
                {draft.rows.map((row, rowIndex) => {
                  const definition = definitionById.get(row.definition_id);
                  const previous = rowIndex > 0 ? definitionById.get(draft.rows[rowIndex - 1].definition_id) : null;
                  const isTemplate = row.key.startsWith('template-');
                  return <Fragment key={row.key}>
                    {definition && definition.category !== previous?.category && <div className="parameter-category">
                      <span>{definition.category}</span><small>{draft.rows.filter(item => definitionById.get(item.definition_id)?.category === definition.category).length} polí</small>
                    </div>}
                    <div className={`parameter-row ${isTemplate ? 'template-row' : ''}`}>
                    <div className="row-top">{isTemplate && definition ? <div className="fixed-parameter"><b>{definition.name}</b>
                      <small>{row.position_label || row.position_key || 'jedna hodnota'}</small></div> : <label>Parametr<select value={row.definition_id || ''}
                      onChange={e => updateRow(row.key, { definition_id: Number(e.target.value), position_key: '', position_label: '' })}>
                      <option value="">Vyber parametr</option>
                      {categories.map(category => <optgroup key={category} label={category}>
                        {definitions.filter(d => d.category === category).map(d => <option key={d.id} value={d.id}>{d.name} ({d.unit || d.value_type})</option>)}
                      </optgroup>)}
                    </select></label>}
                    {!isTemplate && definition && definition.position_kind !== 'NONE' && <label>Pozice{definition.positions.length ? <select value={row.position_key}
                      onChange={e => { const slot = definition.positions.find(item => item.key === e.target.value); updateRow(row.key, { position_key: e.target.value, position_label: slot?.label ?? e.target.value }); }}>
                      <option value="">Vyber pozici</option>{definition.positions.map(position => <option key={position.key} value={position.key}>{position.label}</option>)}</select> : <input value={row.position_key}
                        onChange={e => updateRow(row.key, { position_key: e.target.value, position_label: e.target.value })}
                        placeholder="1 / Zóna 2 / pevná" />}</label>}
                    {!isTemplate && <button className="remove" title="Odebrat parametr" onClick={() => setDraft(old => old && { ...old, rows: old.rows.filter(r => r.key !== row.key) })}>×</button>}</div>
                    {definition?.value_type === 'TEXT' ? <label>Textová hodnota<input value={row.text_value} onChange={e => updateRow(row.key, { text_value: e.target.value })} /></label>
                      : definition?.value_type === 'BOOLEAN' ? <label className="checkbox"><input type="checkbox" checked={row.boolean_value} onChange={e => updateRow(row.key, { boolean_value: e.target.checked })} /> Ano</label>
                      : <div className="value-grid">
                        <label>Cíl<input type="number" step="any" value={row.numeric_target} onChange={e => updateRow(row.key, { numeric_target: e.target.value })} /></label>
                        <label>Minimum<input type="number" step="any" value={row.numeric_min} onChange={e => updateRow(row.key, { numeric_min: e.target.value })} /></label>
                        <label>Maximum<input type="number" step="any" value={row.numeric_max} onChange={e => updateRow(row.key, { numeric_max: e.target.value })} /></label>
                        <span className="unit">{definition?.unit || ''}</span>
                      </div>}
                    {!isTemplate && <label className="note-label">Poznámka k hodnotě<input value={row.note} onChange={e => updateRow(row.key, { note: e.target.value })} /></label>}
                  </div></Fragment>;
                })}
              </div>
              <div className="editor-actions"><button className="primary" disabled={busy} onClick={saveDraft}>Uložit draft</button>
                <button className="secondary" disabled={busy || !activeRevision} onClick={previewRevision}>↗ Náhled PDF</button>
                <button className="secondary" disabled={busy} onClick={issueRevision}>✓ Vydat</button>
                <small>Nejdřív ulož změny. Vydání používá naposledy uloženou verzi a rovnou zveřejní platnou revizi.</small></div>
            </div> : <div className="read-only">
              <div className="read-facts"><div><small>Výrobek</small><b>{activeRevision.product_name || '—'}</b></div>
                <div><small>Materiál</small><b>{activeRevision.material_name || '—'}</b></div>
                <div><small>Důvod revize</small><b>{activeRevision.change_reason || '—'}</b></div>
                <div><small>Schváleno</small><b>{shownDate(activeRevision.approved_at)}</b></div></div>
              <div className="read-table"><div className="read-header"><span>Parametr</span><span>Pozice</span><span>Cíl / hodnota</span><span>Min</span><span>Max</span></div>
                {activeRevision.parameters.map((p, index) => <div className="read-line" key={`${p.definition_id}-${p.position_key}-${index}`}>
                  <b>{p.definition_name}</b><span>{p.position_label || p.position_key || '—'}</span>
                  <strong>{p.definition_type === 'TEXT' ? p.text_value : p.definition_type === 'BOOLEAN' ? (p.boolean_value ? 'Ano' : 'Ne') : `${shownNumber(p.numeric_target)} ${p.unit}`}</strong>
                  <span>{shownNumber(p.numeric_min)}</span><span>{shownNumber(p.numeric_max)}</span></div>)}
              </div>
              {activeRevision.status === 'APPROVED' && activeRevision.id === selectedSpec.current_approved_revision_id &&
                (user.role === 'ENGINEER' || user.role === 'ADMIN') && <div className="save-template">
                  <div><span className="eyebrow">Výchozí vzor</span><b>Uložit tuto schválenou revizi pro nové nástroje</b>
                    <small>Vznikne neměnná kopie hodnot a tolerancí. Pozdější revize původního předpisu ji nezmění.</small></div>
                  <label>Název vzoru<input value={newTemplateName} onChange={e => setNewTemplateName(e.target.value)} placeholder="Např. ENGEL 900 · podobné formy" /></label>
                  <label>Popis<input value={newTemplateDescription} onChange={e => setNewTemplateDescription(e.target.value)} placeholder="Kdy tento vzor použít" /></label>
                  <button className="secondary" disabled={busy || newTemplateName.trim().length < 3} onClick={saveAsProcessTemplate}>Uložit jako vzor</button>
                </div>}
              {activeRevision.status === 'IN_REVIEW' && (user.role === 'APPROVER' || user.role === 'ADMIN') &&
                <div className="review-actions"><button className="primary" disabled={busy} onClick={() => review(true)}>✓ Schválit revizi</button>
                  <input value={returnReason} onChange={e => setReturnReason(e.target.value)} placeholder="Důvod vrácení" />
                  <button className="secondary" disabled={busy || returnReason.length < 3} onClick={() => review(false)}>Vrátit k úpravě</button></div>}
            </div>}
            <div className="audit"><span className="eyebrow">Audit revize</span>
              <div>{audit.map(item => <p key={item.id}><b>{shownDate(item.created_at)}</b> · {item.action}
                {item.reason && <span> · {item.reason}</span>}</p>)}{!audit.length && <p>Bez záznamů.</p>}</div></div>
          </section>}
        </>}

        {user.role === 'ADMIN' && templateForm && <section className="template-card">
          <div><span className="eyebrow">Vzhled exportů</span><h2>PDF šablona <small>{template?.version}</small></h2>
            <p>Nová verze ovlivní další vydané PDF. Již vydané soubory zůstávají v archivu.</p></div>
          <form onSubmit={publishTemplate} className="template-form">
            <label>Nadpis<input value={templateForm.title} onChange={e => setTemplateForm({ ...templateForm, title: e.target.value })} /></label>
            <label>Barva hodnot<input type="color" value={templateForm.accent_color} onChange={e => setTemplateForm({ ...templateForm, accent_color: e.target.value })} /></label>
            <label>Barva sekcí<input type="color" value={templateForm.section_color} onChange={e => setTemplateForm({ ...templateForm, section_color: e.target.value })} /></label>
            <label className="checkbox"><input type="checkbox" checked={templateForm.show_english_subtitle}
              onChange={e => setTemplateForm({ ...templateForm, show_english_subtitle: e.target.checked })} /> Anglické podnadpisy</label>
            <button className="secondary" disabled={busy}>Publikovat novou verzi</button>
          </form>
        </section>}
      </main>
    </div>
    <BugReportWidget user={user} context={selectedSpec ? `Předpis #${selectedSpec.id}` : 'Přehled'} />
  </div>;
}

import { useEffect, useMemo, useState } from 'react';
import { api, issuePdf, setSession } from './api';
import type { Definition, MesItem, Parameter, Revision, Spec, Template, User } from './types';

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
const toDraft = (revision: Revision): Draft => ({
  product_name: revision.product_name, material_name: revision.material_name,
  process_note: revision.process_note, change_reason: revision.change_reason,
  rows: revision.parameters.map(fromParameter),
});
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
  const [mesMode, setMesMode] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedRevisionId, setSelectedRevisionId] = useState<number | null>(null);
  const [machineRef, setMachineRef] = useState('');
  const [toolRef, setToolRef] = useState('');
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
    Promise.all([api<Spec[]>('/specs'), api<Definition[]>('/parameter-definitions')])
      .then(([allSpecs, defs]) => { setSpecs(allSpecs); setDefinitions(defs); })
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
    setDraft(activeRevision?.status === 'DRAFT' &&
      (user?.role === 'ADMIN' || user?.id === activeRevision.created_by)
      ? toDraft(activeRevision) : null);
    if (activeRevision && user) {
      api<Audit[]>(`/revisions/${activeRevision.id}/audit`).then(setAudit).catch(() => setAudit([]));
    } else setAudit([]);
  }, [activeRevision?.id, activeRevision?.row_version, user]);

  const categories = useMemo(() => Array.from(new Set(definitions.map(d => d.category))), [definitions]);
  const definitionById = useMemo(() => new Map(definitions.map(d => [d.id, d])), [definitions]);

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
      const created = await api<Spec>('/specs', 'POST', { machine_ref: machineRef, tool_ref: toolRef });
      await reload(); setSelectedId(created.id); setSelectedRevisionId(created.revisions[0].id);
      setMachineRef(''); setToolRef('');
    }, 'Nový předpis a první rozpracovaná revize jsou připravené.');
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
      const rows = draft.rows.filter(r => r.definition_id);
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

  async function submit() {
    if (!activeRevision) return;
    await action(async () => {
      await api(`/revisions/${activeRevision.id}/submit`, 'POST', { row_version: activeRevision.row_version });
      await reload();
    }, 'Revize čeká na schválení.');
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
          <label>Stroj<select value={machineRef} onChange={e => setMachineRef(e.target.value)} required>
            <option value="">Vyber stroj</option>{machines.map(m => <option key={m.ref} value={m.ref}>{m.code} · {m.name}</option>)}
          </select></label>
          <label>Forma / nástroj<select value={toolRef} onChange={e => setToolRef(e.target.value)} required>
            <option value="">Vyber formu</option>{tools.map(t => <option key={t.ref} value={t.ref}>{t.code} · {t.name}</option>)}
          </select></label>
          <button className="primary full" disabled={busy || !machines.length || !tools.length}>+ Založit draft</button>
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
              <div className="table-heading"><div><span className="eyebrow">Technologické hodnoty</span><h3>Parametry a tolerance</h3></div>
                <button className="secondary" onClick={addRow}>+ Přidat parametr</button></div>
              {draft.rows.length === 0 && <p className="empty-rows">Přidej první parametr. Opakované stupně a zóny rozlišíš pozicí.</p>}
              <div className="parameter-rows">
                {draft.rows.map(row => {
                  const definition = definitionById.get(row.definition_id);
                  return <div className="parameter-row" key={row.key}>
                    <div className="row-top"><label>Parametr<select value={row.definition_id || ''}
                      onChange={e => updateRow(row.key, { definition_id: Number(e.target.value), position_key: '', position_label: '' })}>
                      <option value="">Vyber parametr</option>
                      {categories.map(category => <optgroup key={category} label={category}>
                        {definitions.filter(d => d.category === category).map(d => <option key={d.id} value={d.id}>{d.name} ({d.unit || d.value_type})</option>)}
                      </optgroup>)}
                    </select></label>
                    {definition?.position_kind !== 'NONE' && <label>Pozice<input value={row.position_key}
                      onChange={e => updateRow(row.key, { position_key: e.target.value, position_label: e.target.value })}
                      placeholder="1 / Zóna 2 / pevná" /></label>}
                    <button className="remove" title="Odebrat parametr" onClick={() => setDraft(old => old && { ...old, rows: old.rows.filter(r => r.key !== row.key) })}>×</button></div>
                    {definition?.value_type === 'TEXT' ? <label>Textová hodnota<input value={row.text_value} onChange={e => updateRow(row.key, { text_value: e.target.value })} /></label>
                      : definition?.value_type === 'BOOLEAN' ? <label className="checkbox"><input type="checkbox" checked={row.boolean_value} onChange={e => updateRow(row.key, { boolean_value: e.target.checked })} /> Ano</label>
                      : <div className="value-grid">
                        <label>Cíl<input type="number" step="any" value={row.numeric_target} onChange={e => updateRow(row.key, { numeric_target: e.target.value })} /></label>
                        <label>Minimum<input type="number" step="any" value={row.numeric_min} onChange={e => updateRow(row.key, { numeric_min: e.target.value })} /></label>
                        <label>Maximum<input type="number" step="any" value={row.numeric_max} onChange={e => updateRow(row.key, { numeric_max: e.target.value })} /></label>
                        <span className="unit">{definition?.unit || ''}</span>
                      </div>}
                    <label className="note-label">Poznámka k hodnotě<input value={row.note} onChange={e => updateRow(row.key, { note: e.target.value })} /></label>
                  </div>;
                })}
              </div>
              <div className="editor-actions"><button className="primary" disabled={busy} onClick={saveDraft}>Uložit draft</button>
                <button className="secondary" disabled={busy} onClick={submit}>Odeslat ke schválení</button>
                <small>Nejdřív ulož změny. Odeslání používá naposledy uloženou verzi.</small></div>
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
  </div>;
}

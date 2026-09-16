import { useEffect, useState } from 'react';
import { api } from './api';
import type { BugReport, User } from './types';

const shown = (value: string) => new Date(value).toLocaleString('cs-CZ');

export function BugReportWidget({ user, context }: { user: User; context: string }) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reports, setReports] = useState<BugReport[]>([]);

  useEffect(() => {
    if (open && user.role === 'ADMIN') {
      api<BugReport[]>('/bug-reports').then(setReports).catch(() => {});
    }
  }, [open, user.role]);

  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (message.trim().length < 3) return;
    setBusy(true); setError('');
    try {
      await api('/bug-reports', 'POST', { message, page: context });
      setMessage(''); setSent(true);
      if (user.role === 'ADMIN') setReports(await api<BugReport[]>('/bug-reports'));
    } catch (e) { setError(e instanceof Error ? e.message : 'Nepodařilo se odeslat hlášení.'); }
    finally { setBusy(false); }
  }

  async function toggleDone(report: BugReport) {
    try {
      const updated = await api<BugReport>(`/bug-reports/${report.id}`, 'PATCH',
        { status: report.status === 'OPEN' ? 'DONE' : 'OPEN' });
      setReports(list => list.map(item => item.id === updated.id ? updated : item));
    } catch { /* ignore */ }
  }

  return <div className="bug-widget">
    <button className="bug-fab" onClick={() => { setOpen(o => !o); setSent(false); }} title="Nahlásit chybu v systému">
      🐞
    </button>
    {open && <div className="bug-panel">
      <div className="bug-panel-head"><span className="eyebrow">Zpětná vazba</span><h3>Hlášení chyby</h3>
        <button className="ghost" onClick={() => setOpen(false)}>×</button></div>
      <form onSubmit={send}>
        <label>Co se stalo nebo co nefunguje?
          <textarea rows={4} value={message} onChange={e => setMessage(e.target.value)}
            placeholder="Popiš chybu, ideálně i kroky, jak ji zopakovat." required minLength={3} />
        </label>
        {error && <p className="alert error">{error}</p>}
        {sent && !error && <p className="alert success">Díky, uložili jsme to. Projdeme to spolu.</p>}
        <button className="primary full" disabled={busy || message.trim().length < 3}>Odeslat hlášení</button>
      </form>
      {user.role === 'ADMIN' && <div className="bug-list">
        <span className="eyebrow">Nahlášené chyby ({reports.length})</span>
        {reports.map(item => <div key={item.id} className={`bug-item ${item.status.toLowerCase()}`}>
          <p>{item.message}</p>
          <div className="bug-item-meta">
            <small>{shown(item.created_at)}{item.page ? ` · ${item.page}` : ''}</small>
            <button className="ghost" onClick={() => toggleDone(item)}>
              {item.status === 'OPEN' ? 'Označit vyřešené' : 'Vrátit jako otevřené'}
            </button>
          </div>
        </div>)}
        {!reports.length && <p className="muted tiny">Zatím žádná hlášení.</p>}
      </div>}
    </div>}
  </div>;
}

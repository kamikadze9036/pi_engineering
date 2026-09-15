import type { User } from './types';

let csrf = '';
export function setSession(user: User | null) { csrf = user?.csrf || ''; }

export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (!['GET', 'HEAD'].includes(method) && csrf) headers['X-CSRF-Token'] = csrf;
  const response = await fetch(`/api/v1${path}`, {
    method, headers, credentials: 'same-origin',
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = error.detail;
    throw new Error(typeof detail === 'string' ? detail : `Požadavek selhal (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export async function issuePdf(revisionId: number): Promise<void> {
  const response = await fetch(`/api/v1/revisions/${revisionId}/pdf/issue`, {
    method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': csrf },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `PDF se nepodařilo vytvořit (${response.status}).`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `operacni-navodka-rev-${revisionId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

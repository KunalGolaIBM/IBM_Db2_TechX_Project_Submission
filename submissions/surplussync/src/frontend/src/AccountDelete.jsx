import { useState } from 'react';

export default function AccountDelete({ api, onDeleted }) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [understood, setUnderstood] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    if (!understood) {
      setError('Confirm that you understand the account and personal profile will be permanently deleted.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await api('/auth/account/delete', {
        method: 'POST',
        body: JSON.stringify({ confirm_email: email.trim().toLowerCase(), password }),
      });
      onDeleted();
    } catch (exception) {
      setError(exception.message || 'Account deletion failed. Your account was not deleted.');
    } finally {
      setBusy(false);
    }
  }

  return <section className="account-settings-danger"><div><h3>Permanently Delete Account</h3><p>This permanently removes your login and personal profile. Listing and rescue history is retained with your identity anonymized. Active rescue assignments must be completed, cancelled, or reassigned first. This action cannot be undone.</p></div>{!open ? <button type="button" className="account-delete" onClick={() => { setOpen(true); setError(''); }}>Permanently Delete Account</button> : <form className="account-delete-form" onSubmit={submit}><label>Enter your account email<input type="email" autoComplete="email" required maxLength="254" value={email} onChange={event => setEmail(event.target.value)}/></label><label>Enter your current password<input type="password" autoComplete="current-password" required maxLength="128" value={password} onChange={event => setPassword(event.target.value)}/></label><label className="account-delete-confirm"><input type="checkbox" checked={understood} onChange={event => setUnderstood(event.target.checked)}/>I understand this permanently deletes my account and profile.</label>{error && <p className="account-delete-error" role="alert">{error}</p>}<div className="account-delete-actions"><button type="submit" className="account-delete" disabled={busy || !understood}>{busy ? 'Deleting…' : 'Confirm permanent deletion'}</button><button type="button" className="auth-secondary" disabled={busy} onClick={() => { setOpen(false); setEmail(''); setPassword(''); setUnderstood(false); setError(''); }}>Cancel</button></div></form>}</section>;
}

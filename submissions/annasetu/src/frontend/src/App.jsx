import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { api, patch, post, token } from './api.js';

const NAV = [
  { id: 'overview', label: 'Overview', icon: '◫', group: 'Workspace' },
  { id: 'food', label: 'Food passports', icon: '◉', count: '01', group: 'Workspace' },
  { id: 'rescues', label: 'Rescue operations', icon: '↗', group: 'Workspace' },
  { id: 'ngos', label: 'NGO capacity', icon: '⌂', group: 'Network' },
  { id: 'policy', label: 'Policy copilot', icon: '✧', badge: 'AI', group: 'Network' },
];

const fmtKg = (value = 0) => `${Math.round(Number(value) || 0).toLocaleString('en-IN')} kg`;
const fmtTime = (value) => value ? new Date(value).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—';
const fmtRemaining = (value) => {
  const minutes = Number(value);
  if (!Number.isFinite(minutes)) return 'Checking…';
  if (minutes <= 0) return 'Expired';
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder ? `${hours} hr ${remainder} min` : `${hours} hr`;
};
const formatAuditEvent = (value) => {
  try { return JSON.stringify(JSON.parse(value), null, 2); }
  catch { return String(value || 'Audit payload unavailable'); }
};
const statusClass = (value = '') => value.toLowerCase().replaceAll('_', '-');
const ROLE_LABELS = { admin: 'ADMIN', donor: 'DONOR', ngo: 'NGO', volunteer: 'VOLUNTEER' };
const ROLE_ORDER = ['admin', 'donor', 'ngo', 'volunteer'];
const EMAIL_LOCAL_ATOM = "[A-Z0-9!#$%&'*+/=?^_`{|}~-]+";
const EMAIL_LABEL = '[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?';
const EMAIL_PATTERN = new RegExp(`^${EMAIL_LOCAL_ATOM}(?:\\.${EMAIL_LOCAL_ATOM})*@${EMAIL_LABEL}(?:\\.${EMAIL_LABEL})+$`, 'i');
function validEmail(value) {
  const email = value.trim().toLowerCase();
  if (email.length > 254 || !EMAIL_PATTERN.test(email)) return false;
  const [local, domain] = email.split('@');
  const labels = domain.split('.');
  return local.length <= 64 && domain.length <= 253 && labels.every(label => label.length <= 63)
    && (/^[a-z]{2,}$/i.test(labels.at(-1)) || /^xn--[a-z0-9-]{2,}$/i.test(labels.at(-1)));
}
function passwordIssue(value) {
  if (value.length < 6 || value.length > 128) return 'Use 6–128 characters.';
  if (!/[A-Za-z]/.test(value)) return 'Add at least one letter.';
  if (!/[0-9]/.test(value)) return 'Add at least one number.';
  if (!/[^A-Za-z0-9\s]/.test(value)) return 'Add at least one special character.';
  return '';
}
const commaSeparated = value => value.split(',').map(item => item.trim()).filter(Boolean);

function Icon({ children, className = '' }) { return <span className={`icon ${className}`} aria-hidden="true">{children}</span>; }
function Button({ children, variant = 'primary', className = '', ...props }) { return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>; }
function Pill({ children, tone = 'neutral' }) { return <span className={`pill pill-${tone}`}>{children}</span>; }

function PasswordField({ label, value, onChange, autoComplete, name, minLength = 6, invalid = false }) {
  const [visible, setVisible] = useState(false);
  return <label>{label}<span className="password-field"><input type={visible ? 'text' : 'password'} name={name} autoComplete={autoComplete} value={value} onChange={onChange} required minLength={minLength} maxLength="128" aria-invalid={invalid} /><button type="button" className="password-toggle" aria-label={visible ? 'Hide password' : 'Show password'} onClick={() => setVisible(show => !show)}>{visible ? 'Hide' : 'Show'}</button></span></label>;
}

function Login({ onLogin, onSignup, onResetRequest, onResetVerify, onResetConfirm, notice = '' }) {
  const queryToken = new URLSearchParams(window.location.search).get('reset_token') || '';
  const [mode, setMode] = useState(queryToken ? 'reset' : 'login');
  const [resetToken, setResetToken] = useState(queryToken);
  const [recoveryEntry, setRecoveryEntry] = useState('');
  const [recoveryMode, setRecoveryMode] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState('');
  const [serviceArea, setServiceArea] = useState('');
  const [ngoProfile, setNgoProfile] = useState({ name: '', available_kg: '', accepted_categories: 'prepared meals', storage_capabilities: 'cold', latitude: '', longitude: '', receiving_hours: 'Daily · 08:00–20:00' });
  const [demoAccounts, setDemoAccounts] = useState([]);
  const [demoRole, setDemoRole] = useState('');
  const [emailLogin, setEmailLogin] = useState(false);
  const [db2Status, setDb2Status] = useState('Checking API and IBM Db2…');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [resetVerified, setResetVerified] = useState(false);
  useEffect(() => {
    let active = true;
    api('/auth/demo-accounts').then(accounts => {
      if (active && Array.isArray(accounts)) setDemoAccounts(accounts);
    }).catch(() => { if (active) setDemoAccounts([]); });
    api('/health').then(health => {
      if (active && health.status === 'ok' && health.database === 'IBM Db2') setDb2Status(`Connected to IBM Db2 · ${health.database_name}`);
      else if (active) setDb2Status('API or Db2 health check failed');
    }).catch(() => { if (active) setDb2Status('FastAPI or IBM Db2 is unavailable'); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (mode !== 'reset') return undefined;
    if (!resetToken) { setError('This reset link or recovery code is invalid or expired.'); return undefined; }
    let active = true;
    onResetVerify(resetToken).then(() => { if (active) { setResetVerified(true); setError(''); } })
      .catch(issue => { if (active) setError(issue.message); });
    return () => { active = false; };
  }, [mode, resetToken, onResetVerify]);
  function changeMode(next) {
    setMode(next); setError(''); setMessage(''); setPassword(''); setConfirmPassword(''); setDemoRole(''); setEmailLogin(false);
    setResetToken(''); setRecoveryEntry(''); setRecoveryMode(''); setResetVerified(false);
  }
  function normalizedEmail() {
    const value = email.trim().toLowerCase();
    if (!validEmail(value)) throw new Error('Enter a valid email address.');
    return value;
  }
  async function submitLogin(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const issue = passwordIssue(password);
      if (issue) throw new Error(`Password is invalid. ${issue}`);
      if (demoRole) await onLogin(demoRole, password, true);
      else if (emailLogin) await onLogin(normalizedEmail(), password, false);
      else throw new Error('Select a demo role or choose email sign-in.');
    } catch (problem) { setError(problem.message); }
    finally { setBusy(false); }
  }
  async function submitSignup(event) {
    event.preventDefault(); if (!event.currentTarget.reportValidity()) return; setBusy(true); setError(''); setMessage('');
    try {
      const normalized = normalizedEmail();
      const issue = passwordIssue(password);
      if (issue) throw new Error(`Password is invalid. ${issue}`);
      if (password !== confirmPassword) throw new Error('Password confirmation does not match.');
      const payload = { email: normalized, display_name: displayName.trim(), password, confirm_password: confirmPassword, role };
      if (role === 'volunteer') payload.service_area = serviceArea.trim();
      if (role === 'ngo') payload.ngo_profile = {
        name: ngoProfile.name.trim(), available_kg: Number(ngoProfile.available_kg),
        accepted_categories: commaSeparated(ngoProfile.accepted_categories),
        storage_capabilities: commaSeparated(ngoProfile.storage_capabilities),
        latitude: Number(ngoProfile.latitude), longitude: Number(ngoProfile.longitude),
        receiving_hours: ngoProfile.receiving_hours.trim(),
      };
      await onSignup(payload);
    } catch (problem) { setError(problem.message); }
    finally { setBusy(false); }
  }
  async function submitResetRequest(event) {
    event.preventDefault(); if (!event.currentTarget.reportValidity()) return; setBusy(true); setError(''); setMessage('');
    try {
      const result = await onResetRequest(normalizedEmail());
      setRecoveryMode(result.recovery_mode || 'email'); setMessage(result.message);
      if (result.recovery_mode === 'local_admin_approval') {
        setRecoveryEntry(''); setMode('local_code');
      }
    }
    catch (problem) { setError(problem.message); }
    finally { setBusy(false); }
  }
  function submitLocalRecoveryCode(event) {
    event.preventDefault();
    const code = recoveryEntry.trim();
    if (!/^\d{6}$/.test(code)) { setError('Enter the six-digit local recovery code.'); return; }
    setResetToken(code); setResetVerified(false); setError(''); setMessage(''); setMode('reset');
  }
  async function submitReset(event) {
    event.preventDefault(); if (!event.currentTarget.reportValidity()) return; setBusy(true); setError(''); setMessage('');
    try {
      const issue = passwordIssue(password);
      if (issue) throw new Error(`Password is invalid. ${issue}`);
      if (password !== confirmPassword) throw new Error('Password confirmation does not match.');
      const result = await onResetConfirm({ token: resetToken, password, confirm_password: confirmPassword });
      setMessage(result.message); setPassword(''); setConfirmPassword(''); setResetVerified(false);
      window.history.replaceState({}, '', window.location.pathname);
      setResetToken(''); setRecoveryEntry(''); setRecoveryMode('');
      setMode('login');
    } catch (problem) { setError(problem.message); }
    finally { setBusy(false); }
  }
  const demoRoles = ROLE_ORDER.map(roleName => demoAccounts.find(account => account.role === roleName)).filter(Boolean);
  const heading = mode === 'signup' ? 'Create an account' : mode === 'forgot' ? 'Reset your password' : mode === 'local_code' ? 'Verify recovery code' : mode === 'reset' ? 'Choose a new password' : 'Welcome back';
  const description = mode === 'signup' ? 'Join the rescue network with a role-based account.' : mode === 'forgot' ? 'Request a reset for a local administrator to approve.' : mode === 'local_code' ? 'Enter the code issued by an administrator after identity review.' : mode === 'reset' ? 'Set a new password for your account.' : 'Sign in to your rescue network workspace.';
  return <main className="login-shell">
    <div className="login-art"><div className="brand-mark large"><span>अ</span></div><p className="eyebrow light">GOOD FOOD. SHARED WELL.</p>
      <h1>Every surplus has<br />a place at the table.</h1><p className="login-copy">A trusted local network that moves good food quickly, carefully and with a clear record at every handoff.</p>
      <div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit orbit-three"/><div className="login-foot">A community logistics network · Bengaluru</div>
    </div>
    <section className="login-panel"><div className="login-form-wrap auth-form-wrap"><p className="eyebrow">ANNASETU OPERATIONS</p><h2>{heading}</h2><p className="muted">{description}</p>
      {mode === 'login' && <>
        <form onSubmit={submitLogin} className="form-stack" noValidate autoComplete="off">
          {demoRole ? <div className="demo-selected-role"><span>Signing in as {ROLE_LABELS[demoRole]}</span><button type="button" className="auth-link" onClick={() => { setDemoRole(''); setEmail(''); setEmailLogin(true); setPassword(''); setError(''); }}>Use email instead</button></div> : emailLogin ? <label>Email address<input type="text" inputMode="email" name="annasetu-account-input" autoComplete="off" value={email} onChange={e => { setEmail(e.target.value); setError(''); }} onBlur={() => setEmail(value => value.trim().toLowerCase())} required maxLength="254" /></label> : <div className="demo-selected-role"><span>Select a demo role below</span><button type="button" className="auth-link" onClick={() => { setEmail(''); setEmailLogin(true); setDemoRole(''); }}>Sign in with email</button></div>}
          <PasswordField label="Password" name="annasetu-signin-secret" autoComplete="new-password" value={password} onChange={e => { setPassword(e.target.value); setError(''); }} />
          <button type="button" className="auth-link auth-forgot" onClick={() => changeMode('forgot')}>Forgot password?</button>
          {(error || notice) && <div className="inline-error" role="alert">{error || notice}</div>}
          <Button className="full-width" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'} <span>→</span></Button>
        </form>
        <div className="auth-mode-switch"><span>New to the network?</span><button type="button" className="auth-link" onClick={() => changeMode('signup')}>Create account</button></div>
        <div className="demo-login"><div className="demo-title"><span>DEMO ACCESS</span><span className="demo-dot"/> Local accounts · password required</div>
          <div className="demo-users">{demoRoles.length ? demoRoles.map(account => <button type="button" aria-label={`Select ${ROLE_LABELS[account.role]} demo account`} className={`demo-user ${demoRole === account.role ? 'selected' : ''}`} key={account.role} onClick={() => { setDemoRole(account.role); setEmailLogin(false); setEmail(''); setPassword(''); setError(''); }}><span className="avatar tiny">{ROLE_LABELS[account.role][0]}</span><span><b>{ROLE_LABELS[account.role]}</b></span></button>) : <small className="muted">No seeded demo roles are available for this database.</small>}</div>
        </div>
        <div className="login-note"><span>●</span> {db2Status}</div>
      </>}
      {mode === 'signup' && <form onSubmit={submitSignup} className="form-stack auth-scroll-form" noValidate>
        <label>Your name<input name="annasetu-signup-name" value={displayName} onChange={e => setDisplayName(e.target.value)} required minLength="2" maxLength="120" autoComplete="off" /></label>
        <label>Email address<input type="text" inputMode="email" name="annasetu-signup-contact" autoComplete="off" value={email} onChange={e => { setEmail(e.target.value); setError(''); }} onBlur={() => setEmail(value => value.trim().toLowerCase())} required maxLength="254" /></label>
        <label>Role<select value={role} required onChange={e => { setRole(e.target.value); setError(''); }}><option value="" disabled>Select a role</option><option value="donor">DONOR</option><option value="ngo">NGO</option><option value="volunteer">VOLUNTEER</option></select></label>
        {role === 'volunteer' && <label>Service area<input value={serviceArea} onChange={e => setServiceArea(e.target.value)} required minLength="2" maxLength="160" placeholder="Area you can serve" /></label>}
        {role === 'ngo' && <div className="ngo-signup-fields"><p className="auth-field-hint">NGO receiving profile · unverified until admin review</p>
          <label>Organization name<input value={ngoProfile.name} onChange={e => setNgoProfile({...ngoProfile,name:e.target.value})} required minLength="3" maxLength="160" /></label>
          <label>Available capacity (kg)<input type="number" value={ngoProfile.available_kg} onChange={e => setNgoProfile({...ngoProfile,available_kg:e.target.value})} required min="0" max="100000" step="0.01" /></label>
          <label>Accepted food categories<input value={ngoProfile.accepted_categories} onChange={e => setNgoProfile({...ngoProfile,accepted_categories:e.target.value})} required placeholder="prepared meals, produce" /></label>
          <label>Storage capabilities<input value={ngoProfile.storage_capabilities} onChange={e => setNgoProfile({...ngoProfile,storage_capabilities:e.target.value})} required placeholder="cold, hot" /></label>
          <div className="auth-two-fields"><label>Latitude<input type="number" value={ngoProfile.latitude} onChange={e => setNgoProfile({...ngoProfile,latitude:e.target.value})} required min="-90" max="90" step="any" /></label><label>Longitude<input type="number" value={ngoProfile.longitude} onChange={e => setNgoProfile({...ngoProfile,longitude:e.target.value})} required min="-180" max="180" step="any" /></label></div>
          <label>Receiving hours<input value={ngoProfile.receiving_hours} onChange={e => setNgoProfile({...ngoProfile,receiving_hours:e.target.value})} required minLength="3" maxLength="160" /></label>
        </div>}
        <PasswordField label="Password" name="annasetu-signup-secret" autoComplete="new-password" value={password} onChange={e => { setPassword(e.target.value); setError(''); }} />
        <small className="password-hint">6–128 characters with a letter, number and special character.</small>
        <PasswordField label="Confirm password" name="annasetu-signup-secret-confirm" autoComplete="new-password" value={confirmPassword} onChange={e => { setConfirmPassword(e.target.value); setError(''); }} invalid={!!confirmPassword && confirmPassword !== password} />
        {error && <div className="inline-error" role="alert">{error}</div>}
        <Button className="full-width" disabled={busy}>{busy ? 'Creating account…' : 'Create account'} <span>→</span></Button>
        <div className="auth-mode-switch"><span>Already registered?</span><button type="button" className="auth-link" onClick={() => changeMode('login')}>Sign in</button></div>
      </form>}
      {mode === 'forgot' && <form onSubmit={submitResetRequest} className="form-stack" noValidate>
        <label>Email address<input type="text" inputMode="email" name="annasetu-recovery-contact" autoComplete="off" value={email} onChange={e => { setEmail(e.target.value); setError(''); setMessage(''); }} onBlur={() => setEmail(value => value.trim().toLowerCase())} required maxLength="254" /></label>
        {error && <div className="inline-error" role="alert">{error}</div>}{message && <div className="inline-success" role="status">{message}</div>}
        <Button className="full-width" disabled={busy}>{busy ? 'Requesting approval…' : 'Request local admin approval'} <span>→</span></Button>
        <div className="auth-mode-switch"><button type="button" className="auth-link" onClick={() => changeMode('login')}>Back to sign in</button></div>
      </form>}
      {mode === 'local_code' && <form onSubmit={submitLocalRecoveryCode} className="form-stack" noValidate>
        <section className="local-recovery-panel" aria-live="polite">
          <p className="eyebrow">LOCAL ADMIN APPROVAL</p>
          <strong>The code is issued only in the signed-in administrator workspace.</strong>
          <p>Ask a local administrator to verify your identity and provide the five-minute code.</p>
          <small>No email, SMS, or external verification service is used. Recovery is available only in development.</small>
        </section>
        <label>Admin-approved six-digit code<input name="annasetu-local-recovery-code" type="text" inputMode="numeric" autoComplete="off" pattern="[0-9]{6}" minLength="6" maxLength="6" value={recoveryEntry} onChange={e => { setRecoveryEntry(e.target.value.replace(/\D/g, '').slice(0, 6)); setError(''); }} required /></label>
        {error && <div className="inline-error" role="alert">{error}</div>}
        <Button className="full-width" disabled={busy}>Verify code <span>→</span></Button>
        <div className="auth-mode-switch"><button type="button" className="auth-link" onClick={() => changeMode('forgot')}>Request another code</button></div>
      </form>}
      {mode === 'reset' && <form onSubmit={submitReset} className="form-stack" noValidate>
        {resetVerified ? <><PasswordField label="New password" name="annasetu-reset-secret" autoComplete="new-password" value={password} onChange={e => { setPassword(e.target.value); setError(''); }} /><small className="password-hint">6–128 characters with a letter, number and special character.</small><PasswordField label="Confirm new password" name="annasetu-reset-secret-confirm" autoComplete="new-password" value={confirmPassword} onChange={e => { setConfirmPassword(e.target.value); setError(''); }} invalid={!!confirmPassword && confirmPassword !== password} /></> : !error && <div className="inline-success" role="status">Verifying local administrator recovery code…</div>}
        {error && <div className="inline-error" role="alert">{error}</div>}{message && <div className="inline-success" role="status">{message}</div>}
        {resetVerified && <Button className="full-width" disabled={busy}>{busy ? 'Updating password…' : 'Set new password'} <span>→</span></Button>}
        {recoveryMode === 'local_admin_approval' && <div className="auth-mode-switch"><button type="button" className="auth-link" onClick={() => changeMode('forgot')}>Request another admin approval</button></div>}
        <div className="auth-mode-switch"><button type="button" className="auth-link" onClick={() => changeMode('login')}>Back to sign in</button></div>
      </form>}
    </div></section>
  </main>;
}

function Shell({ user, page, setPage, onLogout, children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  return <div className="app-shell">
    <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
      <div className="brand"><div className="brand-mark"><span>अ</span></div><div><b>AnnaSetu</b><small>FOOD RESCUE NETWORK</small></div><button className="mobile-close" onClick={() => setMobileOpen(false)}>×</button></div>
      <div className="workspace-switch"><div className="workspace-avatar">BLR</div><div><b>Bengaluru Network</b><small>Community operations</small></div><span className="chevron">⌄</span></div>
      <div className="nav-group-label">WORKSPACE</div>
      <nav className="side-nav">{NAV.map(item => <button key={item.id} className={`nav-item ${page === item.id ? 'active' : ''}`} onClick={() => { setPage(item.id); setMobileOpen(false); }}><Icon>{item.icon}</Icon><span>{item.label}</span>{item.count && <small className="nav-count">{item.count}</small>}{item.badge && <small className="nav-ai">{item.badge}</small>}</button>)}</nav>
      <div className="side-status"><div className="status-line"><span className="online-pulse"/> NETWORK LIVE <span>·</span> 3 NGOS</div><div className="side-map"><div className="map-grid"/><span className="map-label map-label-a">Indiranagar</span><span className="map-label map-label-b">Koramangala</span><span className="map-label map-label-c">Domlur</span><i className="map-pin pin-a"/><i className="map-pin pin-b"/><i className="map-pin pin-c"/><i className="map-route route-a"/><i className="map-route route-b"/></div><p>Supply and demand across<br /><b>Central Bengaluru</b></p></div>
      <div className="sidebar-bottom"><button className="help-link"><span className="help-mark">?</span> Help & guidelines <span>↗</span></button><div className="profile-row"><div className="avatar">{user.display_name.slice(0,1)}</div><div className="profile-details"><b>{user.display_name}</b><small>{user.role} access</small></div><button className="profile-menu" onClick={onLogout} title="Sign out">↗</button></div></div>
    </aside>
    {mobileOpen && <button className="sidebar-scrim" onClick={() => setMobileOpen(false)} aria-label="Close menu"/>}
    <main className="main-area"><header className="topbar"><button className="mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Open menu">☰</button><div className="breadcrumbs"><span>AnnaSetu</span><b>/</b><strong>{NAV.find(n => n.id === page)?.label || 'Overview'}</strong></div><div className="topbar-right"><span className="date-label">{new Intl.DateTimeFormat('en-IN',{weekday:'long',day:'2-digit',month:'short',year:'numeric'}).format(new Date())}</span><button className="top-icon" title="Notifications">♧<i/></button><div className="top-avatar">{user.display_name.slice(0,1)}</div></div></header>{children}</main>
  </div>;
}

function PageHeading({ eyebrow, title, description, action }) { return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="muted">{description}</p></div>{action}</div>; }

function MetricCard({ label, value, note, icon, accent, trend }) {
  return <article className={`metric-card ${accent || ''}`}><div className="metric-top"><span>{label}</span><span className="metric-icon">{icon}</span></div><div className="metric-value">{value}</div><div className="metric-foot"><span className={trend ? 'metric-trend' : ''}>{trend || '↗'} <b>{note}</b></span><small>this month</small></div></article>;
}

function AdminRecoveryPanel({ onIssue }) {
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [issuedAt, setIssuedAt] = useState(0);
  useEffect(() => {
    if (!issuedAt) return undefined;
    const timer = window.setTimeout(() => { setCode(''); setMessage('Recovery code expired and was cleared.'); setIssuedAt(0); }, 5 * 60 * 1000);
    return () => window.clearTimeout(timer);
  }, [issuedAt]);
  async function submit(event) {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    setBusy(true); setError(''); setMessage(''); setCode('');
    try {
      const result = await onIssue(email.trim().toLowerCase());
      setCode(result.recovery_code); setMessage(result.message); setIssuedAt(Date.now());
    } catch (problem) { setError(problem.message); }
    finally { setBusy(false); }
  }
  return <section className="card admin-recovery-card">
    <div className="card-heading"><div><p className="eyebrow">LOCAL PASSWORD RECOVERY</p><h3>Issue an approved recovery code</h3><p>Verify the requester in person before issuing a code. It expires after five minutes.</p></div></div>
    <form className="admin-recovery-form" onSubmit={submit} noValidate>
      <label>Account email<input type="text" inputMode="email" name="annasetu-admin-recovery-contact" autoComplete="off" required maxLength="254" value={email} onChange={event => { setEmail(event.target.value); setError(''); setCode(''); }} onBlur={() => setEmail(value => value.trim().toLowerCase())} /></label>
      <Button disabled={busy || !email.trim()}>{busy ? 'Issuing code…' : 'Issue recovery code'} <span>→</span></Button>
    </form>
    {error && <div className="inline-error" role="alert">{error}</div>}
    {message && <div className="inline-success" role="status">{message}</div>}
    {code && <div className="local-recovery-panel admin-issued-recovery"><p className="eyebrow">SHARE ONLY AFTER IDENTITY CHECK</p><output className="local-recovery-code" aria-label="Admin-approved recovery code">{code}</output><small>This code is visible only in the signed-in admin view and will be cleared here after five minutes.</small></div>}
  </section>;
}

function Overview({ dashboard, batches, rescues, user, onNavigate, onRefresh, onAudit, onIssuePasswordReset }) {
  const m = dashboard?.metrics || {};
  const trend = dashboard?.trend || [];
  const maxTrend = Math.max(1, ...trend.map(item => Number(item.donated_kg) || 0));
  const active = batches.filter(batch => ['listed', 'allocated', 'picked_up'].includes(batch.status));
  const held = batches.filter(batch => batch.status === 'hold').length;
  const total = Number(m.donated_kg) || 0;
  const distributed = Number(m.distributed_kg) || 0;
  const pct = total ? Math.min(100, Math.round(distributed / total * 100)) : 0;
  const completed = rescues.filter(r => r.status === 'distributed').length;
  return <div className="page-content">
    <PageHeading eyebrow={new Intl.DateTimeFormat('en-IN',{weekday:'long',day:'2-digit',month:'long',year:'numeric'}).format(new Date()).toUpperCase()} title="Good morning, team" description="Here’s what’s happening across the Bengaluru rescue network today." action={<Button variant="soft" onClick={onRefresh}><span className="refresh-icon">↻</span> Refresh data</Button>} />
    <div className="network-banner"><div className="banner-symbol"><span>↗</span></div><div className="banner-copy"><b>Good food is moving.</b><span>{fmtKg(m.collected_kg)} collected across <b>{dashboard?.rescue_count || 0} verified rescue handoffs</b>, with {fmtKg(m.distributed_kg)} already reaching the community.</span></div><div className="banner-route"><span>DONOR</span><i/><span>VOLUNTEER</span><i/><span>NGO</span></div></div>
    <div className="section-title-row"><div><h2>Network impact</h2><p>Live totals from verified batch and rescue records</p></div><button className="text-link" onClick={() => onNavigate('food')}>View all records <span>→</span></button></div>
    <div className="metrics-grid"><MetricCard label="Food donated" value={fmtKg(m.donated_kg)} icon="◌" note={`${batches.length} batches listed`} accent="metric-green"/><MetricCard label="Food collected" value={fmtKg(m.collected_kg)} icon="↗" note="verified at pickup" accent="metric-blue"/><MetricCard label="Food delivered" value={fmtKg(m.delivered_kg)} icon="⌂" note={`${completed} completed handoffs`} accent="metric-violet"/><MetricCard label="Food distributed" value={fmtKg(m.distributed_kg)} icon="✳" note={`${pct}% of donated food`} trend="↑" accent="metric-orange"/></div>
    <div className="dashboard-grid">
      <section className="card impact-card"><div className="card-heading"><div><h3>Rescue momentum</h3><p>Food moving through the network</p></div><button className="select-chip">Last 30 days <span>⌄</span></button></div>
        <div className="chart-legend"><span><i className="legend-green"/> Donated</span><span><i className="legend-blue"/> Distributed</span></div>
        <div className="chart-area"><div className="chart-y"><span>{Math.round(maxTrend)} kg</span><span>{Math.round(maxTrend*.75)} kg</span><span>{Math.round(maxTrend*.5)} kg</span><span>{Math.round(maxTrend*.25)} kg</span><span>0</span></div><div className="chart-plot"><div className="chart-gridlines"><i/><i/><i/><i/><i/></div><div className="chart-bars">{trend.map((item,n) => { const a = Number(item.donated_kg)||0; const b=Number(item.distributed_kg)||0; return <div className="bar-pair" key={item.label+n} title={`${item.label}: ${fmtKg(a)} donated, ${fmtKg(b)} distributed`}><div className="bar donated" style={{height: `${Math.max(a ? 4 : 1,a/maxTrend*100)}%`}}/><div className="bar distributed" style={{height: `${Math.max(b ? 4 : 1,b/maxTrend*100)}%`}}/></div>; })}</div><div className="chart-x">{trend.map(item=><span key={item.label}>{item.label}</span>)}</div></div></div>
        <div className="chart-summary"><div><span className="summary-dot green"/><b>{fmtKg(m.donated_kg)}</b><small>donated to date</small></div><div><span className="summary-dot blue"/><b>{fmtKg(m.distributed_kg)}</b><small>reached recipients</small></div><div><span className="summary-dot orange"/><b>{dashboard?.failed_attempts || 0}</b><small>failed attempts</small></div></div>
      </section>
      <section className="card activity-card"><div className="card-heading"><div><h3>Rescue activity</h3><p>Latest batch movement</p></div><button className="more-button" onClick={() => onNavigate('rescues')}>•••</button></div>
        <div className="activity-list">{batches.slice(0,4).map((batch, index) => <div className="activity-item" key={batch.batch_id}><div className={`food-thumb thumb-${index}`}><span>{['◒','✿','◍','◇'][index % 4]}</span></div><div className="activity-info"><b>{batch.title}</b><small>{fmtKg(batch.quantity_kg)} <span>·</span> {batch.category}</small></div><div className="activity-status"><Pill tone={batch.status === 'hold' ? 'orange' : batch.status === 'distributed' ? 'green' : 'blue'}>{batch.status.replace('_',' ')}</Pill><small>{fmtTime(batch.created_at)}</small></div></div>)}{!batches.length && <div className="empty-state compact">No food batches recorded yet.</div>}</div>
        <button className="activity-footer" onClick={() => onNavigate('food')}>Open food passports <span>→</span></button>
      </section>
    </div>
    <div className="lower-grid"><section className="card receiver-card"><div className="card-heading"><div><h3>Receiving partners</h3><p>Verified NGOs and available capacity</p></div><button className="text-link" onClick={() => onNavigate('ngos')}>View network →</button></div>
      {(dashboard?.ngo_performance || []).slice(0,3).map((ngo,index) => <div className="receiver-row" key={ngo.ngo_id}><div className={`receiver-logo logo-${index}`}>{ngo.name.slice(0,1)}</div><div className="receiver-main"><b>{ngo.name}</b><small><span className="verified-check">✓</span> Verified partner <span>·</span> {fmtKg(ngo.distributed_kg)} delivered</small></div><div className="capacity-indicator"><div className="capacity-meter"><i style={{width:`${Math.min(100,Math.max(18,Number(ngo.available_kg) / 1.5))}%`}}/></div><small>{fmtKg(ngo.available_kg)} available</small></div></div>)}
    </section><section className="card attention-card"><div className="card-heading"><div><h3>Needs attention</h3><p>Keep every handoff accountable</p></div><span className="attention-count">{held + active.filter(b => !b.human_verified).length}</span></div>
      <div className="attention-item"><div className="attention-icon orange">!</div><div><b>{held} batch{held === 1 ? '' : 'es'} on safety hold</b><small>Missing or unconfirmed safety evidence</small></div><button onClick={() => onNavigate('food')}>→</button></div>
      <div className="attention-item"><div className="attention-icon blue">↗</div><div><b>{rescues.filter(r => ['allocated','picked_up','delivered'].includes(r.status)).length} handoffs in progress</b><small>Pickup, delivery and distribution checks</small></div><button onClick={() => onNavigate('rescues')}>→</button></div>
      {user.role==='admin'?<button className="audit-link" onClick={onAudit}><span>◈</span> Audit records are append-only and tamper-evident · verify hash chain</button>:<div className="audit-link audit-static"><span>◈</span> Audit records are append-only and tamper-evident</div>}
    </section></div>
    {user.role === 'admin' && <AdminRecoveryPanel onIssue={onIssuePasswordReset} />}
  </div>;
}

function NewFoodModal({ onClose, onCreate, busy }) {
  const now = new Date(); const plus = new Date(now.getTime() + 18 * 3600_000);
  const local = (d) => new Date(d.getTime() - d.getTimezoneOffset()*60_000).toISOString().slice(0,16);
  const [form, setForm] = useState({title:'',category:'prepared meals',quantity_kg:'',prepared_at:local(now),use_by:local(plus),storage_type:'cold',storage_temp_c:'4',allergens:'milk, gluten',allergens_confirmed:true,ingredients:'',pickup_address:'Indiranagar, Bengaluru',latitude:'12.9716',longitude:'77.5946',storage_note:'Stored in monitored refrigerator.'});
  const [validationError,setValidationError]=useState('');
  const update = (key, value) => setForm(current => ({...current, [key]:value}));
  async function submit(event) {
    event.preventDefault();
    const prepared = new Date(form.prepared_at);
    const useBy = new Date(form.use_by);
    if (prepared > new Date()) { setValidationError('Preparation time cannot be in the future.'); return; }
    if (useBy <= prepared) { setValidationError('Use-by time must be later than preparation time.'); return; }
    setValidationError('');
    await onCreate({...form,quantity_kg:Number(form.quantity_kg),storage_temp_c:form.storage_temp_c === '' ? null : Number(form.storage_temp_c),latitude:Number(form.latitude),longitude:Number(form.longitude),allergens:form.allergens.split(',').map(s=>s.trim()).filter(Boolean),ingredients:form.ingredients.split(',').map(s=>s.trim()).filter(Boolean),prepared_at:prepared.toISOString(),use_by:useBy.toISOString()});
  }
  return <div className="modal-backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}><section className="modal-card"><div className="modal-head"><div><p className="eyebrow">FOOD SAFETY PASSPORT</p><h2>List a food batch</h2><p className="muted">Record the information a verifier and receiver need.</p></div><button className="modal-close" onClick={onClose}>×</button></div>
    <form className="modal-form" onSubmit={submit}><div className="form-grid"><label className="span-2">Batch name<input required minLength="3" maxLength="160" value={form.title} onChange={e=>update('title',e.target.value)} placeholder="e.g. Fresh lunch bowls"/></label><label>Food category<select value={form.category} onChange={e=>update('category',e.target.value)}>{['prepared meals','produce','bakery','dairy'].map(c=><option key={c}>{c}</option>)}</select></label><label>Quantity (kg)<input type="number" min="0.1" max="5000" step="0.1" required value={form.quantity_kg} onChange={e=>update('quantity_kg',e.target.value)} placeholder="24"/></label>
      <label>Prepared at<input type="datetime-local" max={local(now)} required value={form.prepared_at} onChange={e=>update('prepared_at',e.target.value)}/></label><label>Use by<input type="datetime-local" min={form.prepared_at} required value={form.use_by} onChange={e=>update('use_by',e.target.value)}/></label><label>Storage type<select value={form.storage_type} onChange={e=>update('storage_type',e.target.value)}><option value="cold">Cold (≤5°C)</option><option value="hot">Hot (≥60°C)</option><option value="frozen">Frozen (≤−18°C)</option><option value="ambient">Ambient</option></select></label><label>Last recorded temperature (°C)<input type="number" min="-50" max="100" step="0.1" value={form.storage_temp_c} onChange={e=>update('storage_temp_c',e.target.value)} placeholder="4.0"/></label>
      <label className="span-2">Pickup address<input required minLength="5" maxLength="500" value={form.pickup_address} onChange={e=>update('pickup_address',e.target.value)}/></label><label>Latitude<input type="number" min="-90" max="90" step="0.000001" required value={form.latitude} onChange={e=>update('latitude',e.target.value)}/></label><label>Longitude<input type="number" min="-180" max="180" step="0.000001" required value={form.longitude} onChange={e=>update('longitude',e.target.value)}/></label>
      <label className="span-2">Allergens (comma separated)<input maxLength="2000" value={form.allergens} onChange={e=>update('allergens',e.target.value)} placeholder="milk, peanuts, wheat"/></label><label className="span-2">Storage observation<input required minLength="4" maxLength="500" value={form.storage_note} onChange={e=>update('storage_note',e.target.value)}/></label>
      <label className="span-2">Ingredients, if available<input maxLength="2000" value={form.ingredients} onChange={e=>update('ingredients',e.target.value)} placeholder="rice, lentils, seasonal vegetables"/></label></div>
      {validationError&&<div className="inline-error" role="alert">{validationError}</div>}
      <label className="checkbox-label"><input type="checkbox" checked={form.allergens_confirmed} onChange={e=>update('allergens_confirmed',e.target.checked)}/><span>I confirm the allergen declaration is complete, including “none known”.</span></label>
      <div className="modal-note"><span>ⓘ</span> Listing does not certify safety. A human verifier must approve the passport before allocation.</div><div className="modal-actions"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={busy}>{busy?'Saving…':'Save food passport'} <span>→</span></Button></div>
    </form></section></div>;
}

function EvidenceModal({ batch, onClose, onSave, busy }) {
  const [form,setForm]=useState({storage_temp_c:batch.storage_temp_c==null?'':String(batch.storage_temp_c),storage_note:'Current storage condition checked and recorded by donor.',allergens:(batch.allergens||[]).join(', '),allergens_confirmed:Boolean(batch.allergens_confirmed)});
  const update=(key,value)=>setForm(current=>({...current,[key]:value}));
  async function submit(event){event.preventDefault();await onSave({storage_temp_c:form.storage_temp_c===''?null:Number(form.storage_temp_c),storage_note:form.storage_note,allergens:form.allergens.split(',').map(x=>x.trim()).filter(Boolean),allergens_confirmed:form.allergens_confirmed});}
  return <div className="modal-backdrop"><section className="confirm-modal evidence-modal"><button className="modal-close" onClick={onClose}>×</button><p className="eyebrow">APPEND A STORAGE OBSERVATION</p><h2>Complete batch evidence</h2><p className="muted">Updating safety evidence creates a new observation and resets the previous human review.</p><form onSubmit={submit} className="form-stack"><label>Storage temperature (°C)<input type="number" min="-50" max="100" step="0.1" value={form.storage_temp_c} onChange={e=>update('storage_temp_c',e.target.value)} placeholder="e.g. 4.0"/></label><label>Storage observation<input required minLength="4" maxLength="500" value={form.storage_note} onChange={e=>update('storage_note',e.target.value)}/></label><label>Allergens (comma separated)<input maxLength="2000" value={form.allergens} onChange={e=>update('allergens',e.target.value)}/></label><label className="checkbox-label"><input type="checkbox" checked={form.allergens_confirmed} onChange={e=>update('allergens_confirmed',e.target.checked)}/><span>I confirm this allergen declaration is complete.</span></label><div className="confirm-modal-actions"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={busy}>{busy?'Saving…':'Save evidence'}</Button></div></form></section></div>;
}

function FoodPage({ batches, user, refresh, notify, rememberCodes }) {
  const [selected, setSelected] = useState(null); const [showCreate, setShowCreate] = useState(false); const [showEvidence, setShowEvidence] = useState(false); const [busy, setBusy] = useState(false); const [filter, setFilter] = useState('all'); const [passport, setPassport] = useState(null); const [evaluation, setEvaluation] = useState(null);
  const filtered = batches.filter(batch => filter === 'all' || batch.status === filter);
  useEffect(() => { if (!selected) {setPassport(null);setEvaluation(null);return;} api(`/food/${selected.batch_id}/passport`).then(setPassport).catch(() => setPassport(null)); api(`/food/${selected.batch_id}/evaluate`).then(setEvaluation).catch(() => setEvaluation(null)); }, [selected?.batch_id, selected?.human_verified, selected?.verified_at, selected?.storage_temp_c, selected?.allergens_confirmed]);
  async function create(data){setBusy(true);try{await post('/food',data);setShowCreate(false);notify('Food passport created. A verifier must approve it before allocation.');await refresh();}catch(e){notify(e.message,'error');}finally{setBusy(false);}}
  async function verify(batch){try{await post(`/food/${batch.batch_id}/verify`,{decision:'verified',notes:'Human review completed. Storage observation, declared allergens, packaging and use-by details checked.'});notify('Human verification recorded.');await refresh();const latest=(await api('/food')).find(x=>x.batch_id===batch.batch_id);setSelected(latest||batch);}catch(e){notify(e.message,'error');}}
  async function updateEvidence(data){setBusy(true);try{await patch(`/food/${selected.batch_id}/evidence`,data);notify('New storage evidence saved. Human review has been reset.');setShowEvidence(false);await refresh();const latest=(await api('/food')).find(x=>x.batch_id===selected.batch_id);setSelected(latest||selected);}catch(e){notify(e.message,'error');}finally{setBusy(false);}}
  async function allocate(batch){setBusy(true);try{const result=await post(`/food/${batch.batch_id}/allocate`,{});rememberCodes(result.allocated);notify(`${fmtKg(result.allocated_kg)} reserved. One-time handoff codes are shown in Rescue operations.`);await refresh();setSelected(null);}catch(e){notify(e.message,'error');}finally{setBusy(false);}}
  const canVerify = ['admin','ngo'].includes(user.role); const canCreate=['admin','donor'].includes(user.role); const canAllocate=['admin','ngo'].includes(user.role); const canUpdateEvidence=user.role==='admin'||(user.role==='donor'&&batches.some(item=>item.batch_id===selected?.batch_id));
  return <div className="page-content"><PageHeading eyebrow="BATCH-LEVEL TRACEABILITY" title="Food passports" description="A complete identity and evidence trail for every food batch in the network." action={canCreate && <Button onClick={()=>setShowCreate(true)}>＋ List a food batch</Button>}/>
    <div className="passport-banner"><div className="passport-icon">◈</div><div><b>Every batch gets a traceable passport</b><span>Donor details, preparation, storage readings, allergen declaration and human verification in one record.</span></div><div className="passport-stat"><b>{batches.length.toString().padStart(2,'0')}</b><small>active records</small></div></div>
    <div className="table-toolbar"><div className="filter-tabs">{[['all','All batches'],['listed','Listed'],['allocated','Allocated'],['hold','On hold'],['distributed','Distributed']].map(([id,label])=><button key={id} className={filter===id?'active':''} onClick={()=>setFilter(id)}>{label}{id==='hold'&&batches.filter(b=>b.status==='hold').length>0&&<i/>}</button>)}</div><div className="table-tools"><button className="tool-button">⌕ <span>Search</span></button><button className="tool-button">☷ <span>Filters</span></button></div></div>
    <div className="table-wrap"><table className="data-table"><thead><tr><th>FOOD BATCH</th><th>DONOR</th><th>QUANTITY</th><th>STORAGE</th><th>USE BY</th><th>SAFETY STATUS</th><th></th></tr></thead><tbody>{filtered.map(batch=><tr key={batch.batch_id} onClick={()=>setSelected(batch)} className={selected?.batch_id===batch.batch_id?'row-selected':''}><td><div className="food-table-cell"><div className={`food-thumb thumb-${batch.category==='produce'?1:batch.category==='bakery'?2:0}`}><span>◒</span></div><div><b>{batch.title}</b><small>{batch.category} <span>·</span> #{batch.batch_id.slice(0,8).toUpperCase()}</small></div></div></td><td>{batch.donor_name||'Community donor'}</td><td><b>{fmtKg(batch.quantity_kg)}</b></td><td>{batch.storage_temp_c == null ? <span className="muted">No reading</span> : `${batch.storage_temp_c}°C`}<small className="cell-sub">{batch.storage_type} storage</small></td><td>{fmtTime(batch.use_by)}</td><td><Pill tone={batch.status==='hold'||!batch.human_verified?'orange':batch.status==='distributed'?'green':'blue'}>{!batch.human_verified?'verification needed':batch.status}</Pill></td><td><button className="row-arrow" onClick={e=>{e.stopPropagation();setSelected(batch);}}>↗</button></td></tr>)}{!filtered.length&&<tr><td colSpan="7"><div className="empty-state">No batches match this filter.</div></td></tr>}</tbody></table></div>
    {selected && <div className="detail-backdrop" onMouseDown={e=>e.target===e.currentTarget&&setSelected(null)}><aside className="detail-panel"><div className="detail-head"><div><p className="eyebrow">BATCH PASSPORT</p><h2>{selected.title}</h2><small>#{selected.batch_id.toUpperCase()}</small></div><button className="modal-close" onClick={()=>setSelected(null)}>×</button></div><div className="detail-status-row"><Pill tone={selected.status==='hold'||!selected.human_verified?'orange':'green'}>{!selected.human_verified?'HUMAN REVIEW NEEDED':selected.status.toUpperCase()}</Pill><span>Created {fmtTime(selected.created_at)}</span></div>
      <div className="detail-section"><h3>Food identity</h3><div className="detail-grid"><div><small>DONOR</small><b>{selected.donor_name||'Community donor'}</b></div><div><small>CATEGORY</small><b>{selected.category}</b></div><div><small>QUANTITY</small><b>{fmtKg(selected.quantity_kg)}</b></div><div><small>USE BY</small><b>{fmtTime(selected.use_by)}</b></div><div className="span-2"><small>PICKUP LOCATION</small><b>{selected.pickup_address}</b></div></div></div>
      <div className="detail-section"><h3>Safety evidence</h3><div className="evidence-row"><span className={selected.human_verified?'evidence-check':'evidence-hold'}>{selected.human_verified?'✓':'!'}</span><div><b>Human verification</b><small>{selected.human_verified?`Verified ${fmtTime(selected.verified_at)}`:'Required before any allocation'}</small></div><Pill tone={selected.human_verified?'green':'orange'}>{selected.human_verified?'verified':'pending'}</Pill></div><div className="evidence-row"><span className={selected.storage_temp_c!=null?'evidence-check':'evidence-hold'}>{selected.storage_temp_c!=null?'✓':'!'}</span><div><b>Storage observation</b><small>{selected.storage_temp_c==null?'No temperature recorded':`${selected.storage_temp_c}°C · ${selected.storage_type} storage`}</small></div></div><div className="evidence-row"><span className={selected.allergens_confirmed?'evidence-check':'evidence-hold'}>{selected.allergens_confirmed?'✓':'!'}</span><div><b>Allergen declaration</b><small>{selected.allergens_confirmed?(selected.allergens.join(', ')||'None declared'):'Not confirmed'}</small></div></div><div className="evidence-row"><span className="evidence-check">✓</span><div><b>Preparation record</b><small>{fmtTime(selected.prepared_at)} · {selected.ingredients?.join(', ')||'Ingredients not listed'}</small></div></div></div>
      <div className="detail-section feasibility-box"><div className="feasibility-title"><div><h3>Rescue feasibility</h3><small>Deterministic checks · current receiving network</small></div><Pill tone={evaluation?.status==='FEASIBLE'?'green':'orange'}>{evaluation?.status||'CHECKING'}</Pill></div><div className="candidate-line"><span>Time to declared use-by</span><b>{fmtRemaining(evaluation?.remaining_minutes)}</b></div>{evaluation?.reasons?.map((reason,i)=><p className="reason" key={i}><span>{evaluation.status==='FEASIBLE'?'✓':'•'}</span>{reason}</p>)}{evaluation?.candidates?.slice(0,2).map(candidate=><div className="candidate-line" key={candidate.ngo_id}><span>{candidate.name} · {fmtRemaining(candidate.remaining_minutes)} remaining</span><b>{candidate.estimated_transit_minutes} min ETA</b></div>)}{evaluation?.estimate_label&&<small className="estimate-note">{evaluation.estimate_label}</small>}</div>
      <div className="detail-actions">{canUpdateEvidence&&['listed','hold'].includes(selected.status)&&<Button variant="soft" onClick={()=>setShowEvidence(true)}>＋ Update safety evidence</Button>}{canVerify&&!selected.human_verified&&<Button variant="soft" onClick={()=>verify(selected)}>✓ Record human verification</Button>}{canAllocate&&evaluation?.status==='FEASIBLE'&&<Button disabled={busy||!selected.human_verified} onClick={()=>allocate(selected)}>{busy?'Allocating…':'Allocate rescue →'}</Button>}<Button variant="ghost" onClick={()=>{api(`/food/${selected.batch_id}/passport`).then(setPassport).catch(()=>{});notify('Passport evidence refreshed.');}}>↻ Refresh passport</Button></div>
      <div className="passport-audit"><span>◈</span><div><b>Tamper-evident history</b><small>{passport?.audit_events?.length||0} immutable events on the batch</small></div><i>SHA-256</i></div><details className="passport-events"><summary>Inspect complete audit history</summary><ol>{(passport?.audit_events||[]).map(event=><li key={event.event_id}><b>{event.event_type}</b><small>{fmtTime(event.created_at)}</small><pre>{formatAuditEvent(event.event_data)}</pre></li>)}</ol></details>
    </aside></div>}
    {showCreate&&<NewFoodModal onClose={()=>setShowCreate(false)} onCreate={create} busy={busy}/>}{showEvidence&&selected&&<EvidenceModal batch={selected} onClose={()=>setShowEvidence(false)} onSave={updateEvidence} busy={busy}/>}
  </div>;
}

function RescuesPage({ rescues, user, refresh, notify, oneTimeCodes }) {
  const [code,setCode]=useState(''); const [actualKg,setActualKg]=useState(''); const [stage,setStage]=useState('pickup'); const [selected,setSelected]=useState(null); const [failSelected,setFailSelected]=useState(null); const [failureReason,setFailureReason]=useState(''); const [busy,setBusy]=useState(false);
  const visible = rescues.filter(r => user.role!=='volunteer'||r.status!=='distributed');
  const stages = ['allocated','picked_up','delivered','distributed'];
  useEffect(()=>{setCode('');setActualKg('');},[selected?.rescue_id,stage]);
  async function confirm(){if(!selected)return;setBusy(true);try{const payload={stage,otp:code};if(stage==='distribution')payload.actual_distributed_kg=Number(actualKg);await post(`/rescues/${selected.rescue_id}/confirm`,payload);notify(stage==='distribution'?`Distribution of ${fmtKg(actualKg)} recorded.`:`${stage.charAt(0).toUpperCase()+stage.slice(1)} confirmed and recorded.`);setCode('');setActualKg('');setSelected(null);await refresh();}catch(e){notify(e.message,'error');}finally{setBusy(false);}}
  async function reportFailure(){if(!failSelected)return;setBusy(true);try{await post(`/rescues/${failSelected.rescue_id}/fail`,{reason:failureReason});notify('Rescue failure recorded and reserved capacity released.');setFailureReason('');setFailSelected(null);await refresh();}catch(e){notify(e.message,'error');}finally{setBusy(false);}}
  return <div className="page-content"><PageHeading eyebrow="VERIFIED HANDOFFS" title="Rescue operations" description="Donors confirm pickup, assigned volunteers confirm the handoff, and receiving NGOs confirm community distribution." action={<div className="live-chip"><span className="online-pulse"/> LIVE WORKFLOW</div>}/>
    <div className="workflow-strip"><div className="workflow-step complete"><span>✓</span><div><b>Allocated</b><small>Receiver reserved</small></div></div><i className="workflow-connector complete"/><div className="workflow-step active"><span>02</span><div><b>Picked up</b><small>Donor confirmation</small></div></div><i className="workflow-connector"/><div className="workflow-step"><span>03</span><div><b>Delivered</b><small>Volunteer handoff</small></div></div><i className="workflow-connector"/><div className="workflow-step"><span>04</span><div><b>Distributed</b><small>NGO confirmation</small></div></div></div>
    {oneTimeCodes.length>0&&<div className="codes-banner"><div><b>One-time codes from your latest allocation</b><small>Share each code with the person receiving that handoff. Codes disappear when this page is refreshed.</small></div><div className="codes-list">{oneTimeCodes.map(codeRow=><div key={codeRow.rescue_id}><span>{codeRow.ngo_name}</span><small>Pickup <b>{codeRow.one_time_codes.pickup}</b> · Delivery <b>{codeRow.one_time_codes.delivery}</b> · Distribution <b>{codeRow.one_time_codes.distribution}</b></small></div>)}</div></div>}
    <div className="section-title-row rescue-heading"><div><h2>Active assignments</h2><p>OTP checks only advance in sequence</p></div><Pill tone="blue">{rescues.filter(r=>r.status!=='distributed'&&r.status!=='failed').length} IN PROGRESS</Pill></div>
    <div className="rescue-list">{visible.map(rescue=>{const index=stages.indexOf(rescue.status);const next=['pickup','delivery','distribution'][Math.max(0,index)];const checkpointRole={allocated:'donor',picked_up:'volunteer',delivered:'ngo'}[rescue.status];const canConfirm=index>=0&&index<3&&(user.role==='admin'||user.role===checkpointRole);const canFail=index>=0&&index<3&&['admin','volunteer','ngo'].includes(user.role);return <article className="rescue-card" key={rescue.rescue_id}><div className="rescue-card-top"><div className="rescue-food"><div className="rescue-food-icon">◒</div><div><b>{rescue.food_title}</b><small>#{rescue.rescue_id.slice(0,8).toUpperCase()} <span>·</span> {rescue.ngo_name}</small></div></div><Pill tone={rescue.status==='distributed'?'green':rescue.status==='failed'?'orange':'blue'}>{rescue.status.replace('_',' ')}</Pill></div><div className="rescue-progress">{stages.map((step,i)=><div className={`progress-point ${i<=index?'done':''}`} key={step}><span>{i<index?'✓':String(i+1).padStart(2,'0')}</span><small>{step.replace('_',' ')}</small></div>)}</div><div className="rescue-card-bottom"><div className="rescue-meta"><div><small>ALLOCATED</small><b>{fmtKg(rescue.allocated_kg)}</b></div>{rescue.actual_distributed_kg!=null&&<div><small>ACTUALLY DISTRIBUTED</small><b>{fmtKg(rescue.actual_distributed_kg)}</b></div>}<div><small>VOLUNTEER</small><b>{rescue.volunteer_name}</b></div><div><small>LAST CHECKPOINT</small><b>{fmtTime(rescue.distributed_at||rescue.delivered_at||rescue.picked_up_at||rescue.created_at)}</b></div></div><div className="rescue-actions">{index>=0&&index<3&&!canConfirm&&<small className="muted">Awaiting {checkpointRole} checkpoint</small>}{canConfirm&&<Button variant="soft" onClick={()=>{setSelected(rescue);setStage(next);}}>Confirm {next} ↗</Button>}{canFail&&<Button variant="ghost" onClick={()=>{setFailSelected(rescue);setFailureReason('');}}>Report failure</Button>}</div></div></article>;})}{!visible.length&&<div className="empty-state card">No rescue assignments are visible for this account yet.</div>}</div>
    {selected&&<div className="modal-backdrop"><section className="confirm-modal"><button className="modal-close" onClick={()=>setSelected(null)}>×</button><p className="eyebrow">EVIDENCE CHECKPOINT</p><h2>Confirm {stage}</h2><p className="muted">The {stage==='pickup'?'donor':stage==='delivery'?'assigned volunteer':'receiving NGO'} enters the six-digit code for <b>{selected.food_title}</b>. The timestamp and actor are added to its audit trail.</p><label>One-time handoff code<input autoFocus inputMode="numeric" pattern="[0-9]{6}" maxLength="6" required value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))} placeholder="000000"/></label>{stage==='distribution'&&<label>Actual distributed quantity (kg)<input type="number" min="0.01" max={selected.allocated_kg} step="0.01" required value={actualKg} onChange={e=>setActualKg(e.target.value)} placeholder="Enter quantity received"/></label>}<div className="confirm-modal-actions"><Button variant="ghost" onClick={()=>setSelected(null)}>Cancel</Button><Button onClick={confirm} disabled={busy||code.length!==6||(stage==='distribution'&&(!actualKg.trim()||!Number.isFinite(Number(actualKg))||Number(actualKg)<=0||Number(actualKg)>Number(selected.allocated_kg)))}>{busy?'Recording…':'Confirm checkpoint →'}</Button></div></section></div>}
    {failSelected&&<div className="modal-backdrop"><section className="confirm-modal"><button className="modal-close" onClick={()=>setFailSelected(null)}>×</button><p className="eyebrow">RESCUE EXCEPTION</p><h2>Record failed attempt</h2><p className="muted">Capacity will be released. Add the observed reason to the immutable audit record.</p><label>Failure reason<textarea className="failure-textarea" rows="4" minLength="8" maxLength="500" value={failureReason} onChange={e=>setFailureReason(e.target.value)} placeholder="What prevented the handoff?"/></label><div className="confirm-modal-actions"><Button variant="ghost" onClick={()=>setFailSelected(null)}>Cancel</Button><Button onClick={reportFailure} disabled={busy||failureReason.trim().length<8}>{busy?'Recording…':'Record failure'}</Button></div></section></div>}
  </div>;
}

function NgoPage({ ngos, dashboard, user, refresh, notify }) {
  const [editing,setEditing]=useState(null);const [capacity,setCapacity]=useState('');const [active,setActive]=useState(true);
  async function save(){const amount=Number(capacity);if(!capacity.trim()||!Number.isFinite(amount)||amount<0||amount>100000){notify('Available capacity must be between 0 and 100,000 kg.','error');return;}try{await patch(`/ngos/${editing.ngo_id}/capacity`,{available_kg:amount,active});notify('Receiving capacity updated.');setEditing(null);await refresh();}catch(e){notify(e.message,'error');}}
  async function reviewProfile(ngo){try{await patch(`/ngos/${ngo.ngo_id}/verification`,{verified:!ngo.verified,notes:ngo.verified?'Administrator review revoked profile verification.':'Administrator reviewed the receiving profile.'});notify(ngo.verified?'NGO profile verification revoked.':'NGO profile verified.');await refresh();}catch(e){notify(e.message,'error');}}
  return <div className="page-content"><PageHeading eyebrow="DYNAMIC CAPACITY INTELLIGENCE" title="NGO capacity" description="See who can receive food now, what they can safely handle, and how the network is performing." action={<div className="capacity-live"><span className="online-pulse"/> Capacity updated live</div>}/><div className="ngo-network-banner"><div><span className="eyebrow">VERIFIED RECEIVING NETWORK</span><h2>A little surplus. A lot of good.</h2><p>Allocations reserve capacity in Db2 transactions and can split one batch across multiple partners.</p></div><div className="ngo-network-stats"><div><b>{ngos.filter(n=>n.verified).length.toString().padStart(2,'0')}</b><small>verified partners</small></div><div><b>{fmtKg(ngos.reduce((sum,n)=>sum+Number(n.available_kg||0),0))}</b><small>available capacity</small></div></div></div>
    <div className="ngo-grid">{ngos.map((ngo,index)=>{const canEdit=user.role==='admin'||ngo.owner_user_id===user.user_id;return <article className="ngo-card" key={ngo.ngo_id}><div className="ngo-card-top"><div className={`ngo-monogram ngo-${index}`}>{ngo.name.slice(0,1)}</div><div className="ngo-card-title"><b>{ngo.name}</b><small><span className="verified-check">✓</span> {ngo.verified?'Verified partner':'Pending verification'}</small></div><button className="more-button">•••</button></div><div className="ngo-location"><span>⌖</span> Central Bengaluru <i>·</i> Receiving {ngo.receiving_hours}</div><div className="ngo-capacity"><div className="ngo-capacity-header"><span>AVAILABLE RECEIVING CAPACITY</span><b>{fmtKg(ngo.available_kg)}</b></div><div className="capacity-meter large"><i style={{width:`${Math.max(5,Math.min(100,Number(ngo.available_kg)/1.5))}%`}}/></div><small>Can receive {ngo.storage_capabilities.join(' · ')} storage</small></div><div className="ngo-categories"><span>ACCEPTS</span><div>{ngo.accepted_categories.map(category=><Pill key={category}>{category}</Pill>)}</div></div><div className="ngo-card-footer"><div><small>COMMUNITY DISTRIBUTED</small><b>{fmtKg(ngo.distributed_kg||0)}</b></div><Button variant="outline" disabled={!canEdit} title={!canEdit?'Only the profile owner or administrator can change capacity':''} onClick={()=>{setEditing(ngo);setCapacity(String(ngo.available_kg));setActive(ngo.active);}}>{canEdit?'Update capacity':'Capacity visible'} {canEdit&&<span>↗</span>}</Button></div>{user.role==='admin'&&<Button variant="soft" className="ngo-review-button" onClick={()=>reviewProfile(ngo)}>{ngo.verified?'Revoke verification':'Verify receiving profile'}</Button>}</article>;})}</div>
    <section className="geo-analysis"><div className="geo-analysis-head"><div><span className="eyebrow">GEOGRAPHIC SUPPLY & DEMAND</span><h3>Where the network can reach</h3><p>Capacity and open allocations by receiving location</p></div><span className="geo-zone">⌖ Central Bengaluru</span></div><div className="geo-legend"><span><i className="geo-supply"/> Available supply</span><span><i className="geo-demand"/> Open demand</span></div><div className="geo-rows">{(dashboard?.geography||[]).map((area,index)=>{const supply=Number(area.available_kg)||0;const demand=Number(area.open_demand_kg)||0;const max=Math.max(1,...(dashboard?.geography||[]).flatMap(row=>[Number(row.available_kg)||0,Number(row.open_demand_kg)||0]));return <div className="geo-row" key={area.name}><div className={`geo-dot geo-dot-${index%3}`}/><div className="geo-place"><b>{area.name}</b><small>Verified receiving point</small></div><div className="geo-bars"><div><i className="geo-supply" style={{width:`${Math.max(supply?3:0,supply/max*100)}%`}}/></div><div><i className="geo-demand" style={{width:`${Math.max(demand?3:0,demand/max*100)}%`}}/></div></div><div className="geo-values"><b>{fmtKg(supply)}</b><small>{fmtKg(demand)} open</small></div></div>;})}</div></section>
    <div className="ngo-info"><span>ⓘ</span><div><b>Capacity is reserved only when the whole allocation transaction commits.</b><small>If any part of an allocation fails, capacity and rescue records roll back together.</small></div></div>
    {editing&&<div className="modal-backdrop"><section className="confirm-modal"><button className="modal-close" onClick={()=>setEditing(null)}>×</button><p className="eyebrow">RECEIVING PROFILE</p><h2>Update capacity</h2><p className="muted">{editing.name} · Available capacity is reserved as allocations are made.</p><label>Available now (kg)<input type="number" required min="0" max="100000" step="0.01" value={capacity} onChange={e=>setCapacity(e.target.value)}/></label><label className="checkbox-label compact-check"><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/><span>Accepting rescue offers right now</span></label><div className="confirm-modal-actions"><Button variant="ghost" onClick={()=>setEditing(null)}>Cancel</Button><Button onClick={save} disabled={!capacity.trim()||!Number.isFinite(Number(capacity))||Number(capacity)<0||Number(capacity)>100000}>Save capacity →</Button></div></section></div>}
  </div>;
}

function PolicyPage({ notify }) {
  const [question,setQuestion]=useState('What temperature should chilled surplus food be stored at?');const [answer,setAnswer]=useState(null);const [busy,setBusy]=useState(false);const [batchId,setBatchId]=useState('');
  async function ask(event){event.preventDefault();setBusy(true);try{setAnswer(await post('/policy/ask',{question,batch_id:batchId.trim()||null}));}catch(e){notify(e.message,'error');}finally{setBusy(false);}}
  return <div className="page-content policy-page"><PageHeading eyebrow="RETRIEVAL-AUGMENTED POLICY GUIDANCE" title="Policy copilot" description="Ask a question and retrieve passages from the policy library stored in Db2. The copilot cannot certify food as safe." action={<Pill tone="violet">✧ LANGCHAIN + DB2 VECTOR</Pill>}/>
    <div className="policy-hero"><div className="policy-orb"><span>✧</span></div><p className="eyebrow">GROUNDED IN DOCUMENTED GUIDANCE</p><h2>Find the guidance.<br/><span>Keep the human in control.</span></h2><p>AnnaSetu retrieves matching food-safety passages from IBM Db2 vector search and shows the source. Allocation remains governed by deterministic rules and human verification.</p><div className="policy-tags"><Pill>Db2 vector retrieval</Pill><Pill>Source-linked</Pill><Pill>Never a safety certification</Pill></div></div>
    <section className="policy-query-card"><div className="query-heading"><div className="copilot-avatar">✧</div><div><b>Ask the policy library</b><small>Stored in Db2 · retrieved with LangChain DB2VS</small></div><div className="powered-by">IBM Db2 <span>·</span> LANGCHAIN</div></div><form onSubmit={ask}><textarea rows="3" required minLength="3" maxLength="500" value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Ask about storage, receiving or traceability…"/><div className="query-bottom"><label>Optional batch ID<input maxLength="36" value={batchId} onChange={e=>setBatchId(e.target.value)} placeholder="Paste a batch ID to include deterministic status"/></label><Button disabled={busy||question.trim().length<3}>{busy?'Searching Db2…':'Retrieve guidance'} <span>→</span></Button></div></form>
      {!answer&&<div className="suggestion-row"><span>Try asking</span>{['Cold storage thresholds','Why is human verification required?','How is a rescue ETA estimated?'].map(text=><button key={text} onClick={()=>setQuestion(text)}>{text} ↗</button>)}</div>}
      {answer&&<div className="answer-area"><div className="answer-title"><span className="copilot-avatar small">✧</span><div><b>Retrieved guidance</b><small>{answer.mode}</small></div><Pill tone="orange">EXPLANATION ONLY</Pill></div><p className="answer-text">{answer.answer}</p>{answer.batch_context&&<div className="batch-context"><b>Deterministic batch context · {answer.batch_context.decision}</b>{answer.batch_context.reasons.map((reason,i)=><small key={i}>• {reason}</small>)}<small>{answer.batch_context.note}</small></div>}<div className="source-heading"><b>Source passages</b><span>{answer.sources.length} retrieved from Db2</span></div>{answer.sources.map((source,index)=><article className="source-card" key={`${source.title}-${index}`}><div className="source-number">0{index+1}</div><div><b>{source.title}</b><p>{source.excerpt}</p><a href={source.source_url} target="_blank" rel="noreferrer">Open official source ↗</a></div><small>{Number(source.similarity_score).toFixed(3)}</small></article>)}</div>}
    </section><div className="policy-safety"><span>ⓘ</span><p><b>Safety decisions stay deterministic.</b> Missing or unreliable evidence keeps a batch on HOLD. Language model output never changes a batch status or makes a food safety determination.</p></div>
  </div>;
}

function Toast({ toast }) { if(!toast)return null;return <div className={`toast toast-${toast.type}`}><span>{toast.type==='error'?'!':'✓'}</span>{toast.message}</div>; }

export default function App() {
  const [user,setUser]=useState(null);const [page,setPage]=useState('overview');const [dashboard,setDashboard]=useState(null);const [batches,setBatches]=useState([]);const [rescues,setRescues]=useState([]);const [ngos,setNgos]=useState([]);const [loading,setLoading]=useState(true);const [toast,setToast]=useState(null);const [oneTimeCodes,setOneTimeCodes]=useState([]);const [bootError,setBootError]=useState('');const [bootAttempt,setBootAttempt]=useState(0);
  const notify=useCallback((message,type='success')=>{setToast({message,type});window.setTimeout(()=>setToast(null),4500);},[]);
  const refresh=useCallback(async()=>{if(!token())return;const [nextDashboard,nextBatches,nextRescues,nextNgos]=await Promise.all([api('/dashboard'),api('/food'),api('/rescues'),api('/ngos')]);setDashboard(nextDashboard);setBatches(nextBatches);setRescues(nextRescues);setNgos(nextNgos);},[]);
  useEffect(()=>{let alive=true;async function boot(){const saved=token();if(!saved){setLoading(false);return;}try{const profile=await api('/me');await refresh();if(alive){setUser(profile);setBootError('');}}catch(issue){if(!alive)return;if(issue.status===401||issue.status===403){localStorage.removeItem('annasetu_token');setBootError('Your session expired. Sign in again.');}else{setBootError(issue.message||'AnnaSetu could not load data from FastAPI and IBM Db2.');}}finally{if(alive)setLoading(false);}}boot();return()=>{alive=false;};},[refresh,bootAttempt]);
  async function doLogin(emailOrRole,password,isDemo=false){const result=await post(isDemo?'/auth/demo-login':'/auth/login',isDemo?{role:emailOrRole,password}:{email:emailOrRole,password});localStorage.setItem('annasetu_token',result.access_token);try{await refresh();setBootError('');setUser(result.user);}catch(issue){localStorage.removeItem('annasetu_token');throw issue;}}
  async function doSignup(payload){const result=await post('/auth/signup',payload);localStorage.setItem('annasetu_token',result.access_token);try{await refresh();setBootError('');setUser(result.user);}catch(issue){localStorage.removeItem('annasetu_token');throw new Error(`Account created, but the workspace could not load: ${issue.message}`);}}
  async function requestPasswordReset(email){return post('/auth/password-reset',{email});}
  async function issueLocalPasswordReset(email){return post('/auth/password-reset/admin-issue',{email});}
  async function verifyPasswordReset(resetToken){return post('/auth/password-reset/verify',{token:resetToken});}
  async function confirmPasswordReset(payload){return post('/auth/password-reset/confirm',payload);}
  async function checkAudit(){try{const result=await api('/audit/verify');notify(result.valid?`Audit chain verified · ${result.checked_events} events checked.`:`Audit integrity issue near event ${result.broken_event_id}.`,result.valid?'success':'error');}catch(e){notify(e.message,'error');}}
  function logout(){localStorage.removeItem('annasetu_token');setUser(null);setPage('overview');setOneTimeCodes([]);}
  if(loading)return <div className="loading-screen"><div className="brand-mark"><span>अ</span></div><span className="loading-orbit"/>Connecting to the network…</div>;
  if(!user&&bootError&&token())return <main className="loading-screen connection-error"><div className="brand-mark"><span>अ</span></div><h2>AnnaSetu is temporarily unavailable</h2><p>{bootError}</p><Button variant="soft" onClick={()=>{setLoading(true);setBootError('');setBootAttempt(value=>value+1);}}>Retry connection</Button><Button variant="ghost" onClick={()=>{localStorage.removeItem('annasetu_token');setBootError('');}}>Sign in instead</Button></main>;
  if(!user)return <><Login onLogin={doLogin} onSignup={doSignup} onResetRequest={requestPasswordReset} onResetVerify={verifyPasswordReset} onResetConfirm={confirmPasswordReset} notice={bootError}/><Toast toast={toast}/></>;
  return <Shell user={user} page={page} setPage={setPage} onLogout={logout}><div className="content-scroll">{page==='overview'&&<Overview dashboard={dashboard} batches={batches} rescues={rescues} user={user} onNavigate={setPage} onAudit={checkAudit} onIssuePasswordReset={issueLocalPasswordReset} onRefresh={()=>refresh().then(()=>notify('Dashboard refreshed from Db2.')).catch(e=>notify(e.message,'error'))}/ >}{page==='food'&&<FoodPage batches={batches} user={user} refresh={refresh} notify={notify} rememberCodes={setOneTimeCodes}/ >}{page==='rescues'&&<RescuesPage rescues={rescues} user={user} refresh={refresh} notify={notify} oneTimeCodes={oneTimeCodes}/ >}{page==='ngos'&&<NgoPage ngos={ngos} dashboard={dashboard} user={user} refresh={refresh} notify={notify}/ >}{page==='policy'&&<PolicyPage notify={notify}/ >}</div><Toast toast={toast}/></Shell>;
}

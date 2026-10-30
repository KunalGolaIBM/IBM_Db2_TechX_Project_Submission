import { useEffect, useState } from 'react';
import './auth.css';
import AccountDelete from './AccountDelete.jsx';

const BASE = import.meta.env?.VITE_API_BASE_URL || '/api';

async function request(path, body) {
  let response;
  try {
    response = await fetch(`${BASE}${path}`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  } catch {
    throw new Error('Cannot reach SurplusSync. Check that the FastAPI service is available, then try again.');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const error = new Error(detail?.message || (typeof detail === 'string' ? detail : detail?.[0]?.msg) || `Request failed (${response.status}).`);
    error.code = detail?.code;
    error.status = response.status;
    error.roles = detail?.roles;
    throw error;
  }
  return data;
}

async function protectedRequest(path, method, body = null) {
  let response;
  try {
    response = await fetch(`${BASE}${path}`, { method, credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.__surplusCsrf || '' }, ...(body ? { body: JSON.stringify(body) } : {}) });
  } catch {
    throw new Error('Cannot reach SurplusSync. Check that the FastAPI service is available, then try again.');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail?.message || data.detail || `Request failed (${response.status}).`);
  return data;
}

function fileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
    reader.onerror = () => reject(new Error('The certificate file could not be read.'));
    reader.readAsDataURL(file);
  });
}

const FOOD_CATEGORIES = ['Prepared meals', 'Fresh produce', 'Bakery', 'Dairy', 'Packaged groceries'];
const REGISTRATION_TYPES = ['Registered trust', 'Registered society', 'Section 8 company', 'Other registered organization'];

export default function Auth({ user, onAuthenticated, onProfileSaved, onAccountDeleted, onClose }) {
  const showLocalDemoAccounts = import.meta.env.DEV && ['localhost', '127.0.0.1'].includes(window.location.hostname);
  const params = new URLSearchParams(location.search);
  const [page, setPage] = useState(params.has('reset_token') ? 'reset' : user ? 'onboarding' : 'welcome');
  const [email, setEmail] = useState(params.get('email') || user?.email || '');
  const [password, setPassword] = useState('');
  const [loginRoles, setLoginRoles] = useState([]);
  const [loginRole, setLoginRole] = useState('');
  const [recoveryRoles, setRecoveryRoles] = useState([]);
  const [recoveryRole, setRecoveryRole] = useState('');
  const [show, setShow] = useState(false);
  const [role, setRole] = useState(user?.role || 'DONOR');
  const [roleToAdd, setRoleToAdd] = useState('');
  const [profile, setProfile] = useState(user?.profile || {});
  const [certificate, setCertificate] = useState(null);
  const [maxCertificateBytes, setMaxCertificateBytes] = useState(5 * 1024 * 1024);
  const [token, setToken] = useState(params.get('reset_token') || '');
  const [newPassword, setNewPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [checks, setChecks] = useState(Object.fromEntries((user?.profile?.food_categories || []).map(category => [category, true])));
  const demoRecipientProfile = user?.role === 'RECIPIENT' && user?.profile_demo === true && (user?.presentation_demo_mode === true || user?.presentation_setup === true);
  const set = (key, value) => setProfile(current => ({ ...current, [key]: value }));

  useEffect(() => {
    if (user) {
      setRole(user.role);
      setEmail(user.email);
      setProfile(user.profile || {});
      setChecks(Object.fromEntries((user.profile?.food_categories || []).map(category => [category, true])));
    }
  }, [user?.id, user?.role, user?.profile_status]);

  useEffect(() => {
    if (user?.role !== 'RECIPIENT' || demoRecipientProfile) return undefined;
    let active = true;
    fetch(`${BASE}/auth/organization/application-limit`, { credentials: 'include' })
      .then(async response => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !Number.isInteger(data.max_certificate_bytes)) throw new Error(data.detail?.message || 'Could not load certificate upload settings.');
        if (active) setMaxCertificateBytes(data.max_certificate_bytes);
      })
      .catch(exception => { if (active) setError(exception.message); });
    return () => { active = false; };
  }, [user?.id, user?.role, demoRecipientProfile]);

  const activeRole = user?.role || role;
  const fields = activeRole === 'DONOR'
    ? [['contact_name', 'Contact person'], ['phone', 'Phone'], ['organization_name', 'Business / organization'], ['address', 'Address'], ['pickup_area', 'Pickup area']]
    : activeRole === 'RECIPIENT'
      ? (demoRecipientProfile ? [['organization_name', 'Fictional demo organization name'], ['service_area', 'Receiving area'], ['capacity', 'Configured demo capacity (portions)']] : [['organization_name', 'Official NGO / organization name'], ['address', 'Organization address'], ['service_area', 'Service location / receiving area'], ['contact_person', 'Authorized Contact Person — Full Name'], ['phone', 'Contact mobile number'], ['receiving_hours', 'Receiving hours'], ['registration_type', 'NGO registration type'], ['registration_number', 'NGO Registration Number'], ['capacity', 'Configured capacity (portions)']])
      : [['contact_name', 'Contact name'], ['phone', 'Phone'], ['service_area', 'Service area'], ['availability', 'Availability']];

  async function run(action) {
    setBusy(true);
    setError('');
    setMessage('');
    try { await action(); } catch (exception) {
      if (exception.code === 'role_selection_required') {
        if (page === 'login') { setLoginRoles(exception.roles || []); setLoginRole(exception.roles?.[0] || ''); }
        if (page === 'forgot') { setRecoveryRoles(exception.roles || []); setRecoveryRole(exception.roles?.[0] || ''); }
      }
      setError(exception.message);
    } finally { setBusy(false); }
  }

  async function addRoleProfile() {
    if (!roleToAdd) return;
    await run(async () => {
      const result = await protectedRequest('/auth/role-profiles', 'POST', { role: roleToAdd });
      onAuthenticated(result.user, window.__surplusCsrf || '');
      setRoleToAdd('');
      setMessage(result.message);
    });
  }

  async function switchRole(nextRole) {
    await run(async () => {
      const result = await protectedRequest('/auth/active-role', 'POST', { role: nextRole });
      onAuthenticated(result.user, window.__surplusCsrf || '');
      setPage('onboarding');
    });
  }

  async function submitProfile(event) {
    event.preventDefault();
    await run(async () => {
      if (activeRole === 'RECIPIENT' && demoRecipientProfile) {
        const result = await protectedRequest('/auth/profile', 'PUT', { profile: { organization_name: profile.organization_name, service_area: profile.service_area, capacity: Number(profile.capacity), food_categories: FOOD_CATEGORIES.filter(category => checks[category]) } });
        setMessage(result.message);
        onProfileSaved(result.user, result.message);
        return;
      }
      if (activeRole !== 'RECIPIENT') {
        const result = await protectedRequest('/auth/profile', 'PUT', { profile: { ...profile } });
        setMessage(result.message);
        onProfileSaved(result.user, result.message);
        return;
      }
      if (!certificate) throw new Error('Attach the organization registration certificate before submitting for review.');
      if (certificate.size > maxCertificateBytes) throw new Error(`Certificate files must be no larger than ${(maxCertificateBytes / (1024 * 1024)).toFixed(1)} MB.`);
      const encoded = await fileAsBase64(certificate);
      const result = await protectedRequest('/auth/organization/application', 'PUT', {
        profile: { ...profile, food_categories: FOOD_CATEGORIES.filter(category => checks[category]), capacity: Number(profile.capacity) },
        certificate_filename: certificate.name,
        certificate_base64: encoded,
      });
      setMessage(result.message);
      setCertificate(null);
      event.target.reset();
      onProfileSaved(result.user, result.message);
    });
  }

  const accountDeleteApi = (path, options) => protectedRequest(path, options.method, options.body ? JSON.parse(options.body) : null);
  const verificationStatus = user?.organization_verification_status || user?.profile_status;

  return <main className="auth-page"><section className="auth-story"><div className="auth-brand"><span>↗</span> surplus<strong>sync</strong></div><div className="auth-story-copy"><small>COMMUNITY FOOD RESCUE</small><h1>Good food,<br/><em>going further.</em></h1><p>Coordinate surplus with local organisations that may be able to receive it in time.</p><div className="auth-promise">Explainable planning · Human safety checks · Fictional demo network</div></div><footer>SurplusSync · Team HyperX</footer></section><section className="auth-panel"><div className="auth-card">
    {page === 'welcome' && <><small className="auth-kicker">WELCOME TO SURPLUSSYNC</small><h2>Food rescue, coordinated.</h2><p className="auth-lead">Use a local fictional demo account for the presentation, or create an account and log in right away.</p><button className="auth-primary" onClick={() => setPage('signup')}>Create an account <span>→</span></button><button className="auth-secondary" onClick={() => setPage('login')}>Log in</button><p className="auth-footnote">Frontend preview works without the API. Real sign-in and database actions require FastAPI. Recipient organizations need admin review before joining the operational network. Fictional recipient data and travel estimates are illustrative; SurplusSync does not certify food safety.</p></>}

    {page === 'signup' && <form onSubmit={event => { event.preventDefault(); run(async () => { await request('/auth/signup', { email, password, role }); setEmail(email.trim().toLowerCase()); setPassword(''); setMessage('Account created. You can log in now.'); setPage('login'); }); }}><small className="auth-kicker">GET STARTED</small><h2>Create your account</h2><label>Email<input type="email" required maxLength="254" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)}/></label><label>Password (8 characters minimum; include one uppercase letter and one number)<span className="password-row"><input type={show ? 'text' : 'password'} required minLength="8" maxLength="128" pattern="(?=.*[A-Z])(?=.*[0-9]).{8,}" title="Use at least 8 characters, including one uppercase letter and one number." autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)}/><button type="button" onClick={() => setShow(value => !value)}>{show ? 'Hide' : 'Show'}</button></span></label><label>Account role<select value={role} onChange={event => setRole(event.target.value)}><option value="DONOR">Food donor</option><option value="RECIPIENT">Recipient organization</option><option value="VOLUNTEER">Volunteer</option></select></label><p className="auth-footnote">One login can hold donor, recipient and volunteer profiles. Create the first profile here, then add and switch roles from account settings. Each profile keeps its own permissions. Donor and volunteer accounts can start after profile completion. Real recipient organizations must submit a registration certificate and wait for administrator review. Administrator access is created only through trusted local setup.</p><button className="auth-primary" disabled={busy}>{busy ? 'Creating…' : 'Create account'}</button><button className="auth-link" type="button" onClick={() => setPage('login')}>Already have an account? Log in</button></form>}

    {page === 'login' && <form onSubmit={event => { event.preventDefault(); run(async () => { const data = await request('/auth/login', { email, password, ...(loginRole ? { role: loginRole } : {}) }); onAuthenticated(data.user, data.csrf_token); setPage('onboarding'); }); }}><small className="auth-kicker">WELCOME BACK</small><h2>Log in</h2><label>Email<input type="email" required autoComplete="username" value={email} onChange={event => { setEmail(event.target.value); setLoginRoles([]); setLoginRole(''); }}/></label><label>Password<span className="password-row"><input type={show ? 'text' : 'password'} required autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)}/><button type="button" onClick={() => setShow(value => !value)}>{show ? 'Hide' : 'Show'}</button></span></label>{loginRoles.length > 0 && <label>Choose role profile<select required value={loginRole} onChange={event => setLoginRole(event.target.value)}><option value="">Select a role</option>{loginRoles.map(item => <option key={item} value={item}>{item}</option>)}</select></label>}{loginRoles.length > 0 && <p className="auth-footnote">This login has multiple role profiles. Choose which one to open.</p>}<button className="auth-primary" disabled={busy}>{busy ? 'Signing in…' : 'Log in'}</button><button className="auth-link" type="button" onClick={() => setPage('forgot')}>Forgot password?</button><button className="auth-link" type="button" onClick={() => setPage('signup')}>Create an account</button>{showLocalDemoAccounts && <details className="demo-login-help"><summary>Local presentation account</summary><p>Run <code>.\.venv\Scripts\python.exe -m backend.seed_presentation_demo</code> from the project root. It preserves this account's current password and data, then makes Donor, Recipient and Volunteer profiles available under one login.</p><ul><li>Shared identity: <code>tournamentgaming07@gmail.com</code></li><li>Choose Donor, Recipient or Volunteer after login; recipient operations remain pending admin review.</li></ul><small>Shown only on localhost during Vite development. Passwords are never stored in the frontend.</small></details>}<p className="auth-footnote">Real authentication and SQLite-backed features require the FastAPI service. The UI alone is a preview.</p></form>}

    {page === 'forgot' && <form onSubmit={event => { event.preventDefault(); run(async () => { const result = await request('/auth/password/forgot', { email, ...(recoveryRole ? { role: recoveryRole } : {}) }); setMessage(result.development_token ? `${result.message} Local development token: ${result.development_token}` : result.message); }); }}><small className="auth-kicker">ACCOUNT RECOVERY</small><h2>Reset your password</h2><p className="auth-lead">If an account exists, reset instructions will be sent to its email address.</p><label>Email<input type="email" required autoComplete="email" value={email} onChange={event => { setEmail(event.target.value); setRecoveryRoles([]); setRecoveryRole(''); }}/></label>{recoveryRoles.length > 0 && <label>Choose role profile<select required value={recoveryRole} onChange={event => setRecoveryRole(event.target.value)}><option value="">Select a role</option>{recoveryRoles.map(item => <option key={item} value={item}>{item}</option>)}</select></label>}{recoveryRoles.length > 0 && <p className="auth-footnote">Select which role account should receive the reset link.</p>}<button className="auth-primary" disabled={busy}>{busy ? 'Requesting…' : 'Send reset link'}</button><button className="auth-link" type="button" onClick={() => setPage('login')}>Back to log in</button></form>}

    {page === 'reset' && <form onSubmit={event => { event.preventDefault(); run(async () => { await request('/auth/password/reset', { email, token, new_password: newPassword }); history.replaceState({}, '', location.pathname); setMessage('Password changed. Log in with your new password.'); setPage('login'); }); }}><small className="auth-kicker">ACCOUNT RECOVERY</small><h2>Choose a new password</h2><label>Email<input type="email" required value={email} onChange={event => setEmail(event.target.value)}/></label><label>Reset token<input required minLength="20" value={token} onChange={event => setToken(event.target.value)}/></label><label>New password (8 characters minimum; include one uppercase letter and one number)<input type="password" required minLength="8" maxLength="128" pattern="(?=.*[A-Z])(?=.*[0-9]).{8,}" title="Use at least 8 characters, including one uppercase letter and one number." autoComplete="new-password" value={newPassword} onChange={event => setNewPassword(event.target.value)}/></label><button className="auth-primary" disabled={busy}>{busy ? 'Saving…' : 'Change password'}</button></form>}

    {page === 'onboarding' && user && <form onSubmit={submitProfile}><small className="auth-kicker">PROFILE SETUP · {activeRole}</small><h2>{demoRecipientProfile ? (user.profile_status === 'approved' ? 'Demo organization profile' : 'Create demo organization account') : activeRole === 'RECIPIENT' ? 'Organization verification' : user.profile_status === 'rejected' ? 'Update your profile' : 'Complete your profile'}</h2>{activeRole === 'RECIPIENT' && (demoRecipientProfile ? <div className="verification-status"><b>FICTIONAL DEMO · Not officially registered or verified</b><p>{user.presentation_demo_mode ? 'No certificate or registration number is requested in presentation mode. This profile is only a synthetic network fixture and is not an official approval.' : 'Presentation mode is disabled. Enable SURPLUSSYNC_PRESENTATION_DEMO_ENABLED only for a local or isolated demo database before saving this fictional profile.'}</p></div> : <div className="verification-status"><b>Status: {verificationStatus === 'resubmission_required' ? 'Resubmission Required' : verificationStatus === 'rejected' ? 'Rejected' : verificationStatus === 'approved_legacy' ? 'Approved — legacy admin-reviewed profile; no certificate record is on file' : verificationStatus === 'approved' ? 'Approved' : verificationStatus === 'demo_fixture' ? 'Fictional demo fixture — not legal or government verification' : 'Pending Verification'}</b><p>{user.organization_review_reason || user.review_reason || (verificationStatus === 'approved_legacy' ? 'This older recipient account was approved before document upload was introduced.' : 'The organization cannot receive or accept rescue offers until an administrator approves the submitted profile and certificate.')}</p>{user.profile?.organization_name && ['pending','rejected','resubmission_required'].includes(verificationStatus) && <a className="auth-link" href={`${BASE}/auth/organization/document`} target="_blank" rel="noreferrer">View your submitted certificate</a>}</div>)}{user.available_roles?.length > 1 && <label>Switch role profile<select value={activeRole} onChange={event => switchRole(event.target.value)}>{user.available_roles.map(item => <option key={item} value={item}>{item}</option>)}</select></label>}{user.available_roles?.length < 3 && user.role !== 'ADMIN' && <div className="fields"><label>Add role profile<select value={roleToAdd} onChange={event => setRoleToAdd(event.target.value)}><option value="">Choose role</option>{['DONOR','RECIPIENT','VOLUNTEER'].filter(item => !user.available_roles?.includes(item)).map(item => <option key={item}>{item}</option>)}</select></label><button type="button" className="outline" disabled={!roleToAdd || busy} onClick={addRoleProfile}>{busy ? 'Adding…' : 'Add profile'}</button></div>}{activeRole === 'RECIPIENT' && <p className="auth-lead">{demoRecipientProfile ? 'Create a fictional presentation profile. It is labeled DEMO and is never presented as a registered or verified organization.' : 'Provide the organization’s official information and upload its registration document. Administrator review is required before operational recipient access.'}</p>}{fields.map(([key, label]) => <label key={key}>{label}{key === 'registration_type' ? <select required value={profile[key] || ''} onChange={event => set(key, event.target.value)}><option value="">Select registration type</option>{REGISTRATION_TYPES.map(type => <option value={type} key={type}>{type}</option>)}</select> : <input required type={key === 'capacity' ? 'number' : 'text'} min={key === 'capacity' ? 1 : undefined} max={key === 'capacity' ? 100000 : undefined} value={profile[key] ?? ''} onChange={event => set(key, event.target.value)}/>}</label>)}{activeRole === 'RECIPIENT' && <>{!demoRecipientProfile && <p className="field-help">This means the name of the person responsible for communicating and coordinating food pickups on behalf of the NGO. It is not the NGO’s name.</p>}<fieldset><legend>Food categories accepted</legend>{FOOD_CATEGORIES.map(category => <label className="auth-check" key={category}><input type="checkbox" checked={checks[category] ?? false} onChange={event => setChecks(current => ({ ...current, [category]: event.target.checked }))}/>{category}</label>)}</fieldset>{!demoRecipientProfile && <><label>Registration certificate (PDF, JPG, or PNG · max {(maxCertificateBytes / (1024 * 1024)).toFixed(1)} MB)<input type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" required onChange={event => setCertificate(event.target.files?.[0] || null)}/></label><p className="auth-footnote">Uploaded documents are stored privately on this computer and are visible only to this organization and authorized administrators.</p></>}</>}{message && <p className="auth-success" role="status">{message}</p>}<button className="auth-primary" disabled={busy || demoRecipientProfile && !user.presentation_demo_mode}>{busy ? 'Saving…' : demoRecipientProfile ? (user.profile_status === 'approved' ? 'Save Organisation Profile' : 'Create Organisation Account') : activeRole === 'RECIPIENT' ? 'Submit organization for review' : 'Save and continue'}</button>{!demoRecipientProfile && <p className="auth-footnote">Review confirms an administrator reviewed the supplied information. It does not establish government identity or legal status automatically.</p>}<button type="button" className="auth-link" onClick={() => run(async () => { await protectedRequest('/auth/logout', 'POST'); setPage('welcome'); onAuthenticated(null, ''); })}>Log out</button><button type="button" className="auth-link" onClick={() => { setPage('settings'); setError(''); setMessage(''); }}>Settings → Account Settings</button>{onClose && <button type="button" className="auth-link" onClick={onClose}>Back to dashboard</button>}</form>}

    {page === 'settings' && user && <section><small className="auth-kicker">SETTINGS · ACCOUNT SETTINGS</small><h2>Account settings</h2><p className="auth-lead">Manage this account. Permanent deletion requires your current password and explicit confirmation.</p><AccountDelete api={accountDeleteApi} onDeleted={onAccountDeleted}/><button className="auth-link" type="button" onClick={() => setPage('onboarding')}>Back to profile</button></section>}

    {error && <p className="auth-error" role="alert">{error}</p>}{message && !['welcome', 'onboarding'].includes(page) && <p className="auth-success" role="status">{message}</p>}
  </div></section></main>;
}

export function VerificationQueue({ api, onMessage }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState({});
  const [failure, setFailure] = useState('');
  const [reasons, setReasons] = useState({});

  async function load() {
    setLoading(true);
    setFailure('');
    try {
      const data = await api('/admin/verifications');
      if (!Array.isArray(data)) throw new Error('The server returned an invalid review queue.');
      setRows(data);
    } catch (exception) { setFailure(exception.message); } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function review(row, decision) {
    const reason = reasons[`${row.user_id}:${row.role}`] || '';
    if (['rejected', 'resubmission_required'].includes(decision) && !reason.trim()) {
      setFailure('Add a review reason before rejecting or requesting new documents.');
      return;
    }
    setBusy(current => ({ ...current, [`${row.user_id}:${row.role}`]: true }));
    setFailure('');
    try {
      await api(`/admin/verifications/${row.user_id}?role=${encodeURIComponent(row.role)}`, { method: 'PATCH', body: JSON.stringify({ decision, reason }) });
      onMessage(decision === 'approved' ? 'Organization approved after administrator review.' : decision === 'resubmission_required' ? 'Resubmission requested.' : 'Application rejected with a reason.');
      await load();
    } catch (exception) { setFailure(exception.message); } finally { setBusy(current => ({ ...current, [`${row.user_id}:${row.role}`]: false })); }
  }

  return <><div className="page-title"><div><div className="kicker">AUTHORIZED REVIEW</div><h1>Organization verification queue</h1><p>Review registration details and supporting documents. This is a human administrative review, not automatic certification.</p></div><button className="outline" onClick={load} disabled={loading}>{loading ? 'Loading…' : 'Refresh queue'}</button></div>{failure && <div className="toast error" role="alert">{failure}</div>}{loading ? <div className="card empty">Loading pending applications…</div> : rows.length === 0 ? <div className="card empty"><b>No profiles waiting for review</b><p>Submitted donor, recipient and volunteer profiles appear here.</p></div> : <div className="verification-grid">{rows.map(row => <article className="card verification-card" key={`${row.user_id}:${row.role}`}><div className="kicker">{row.role} · USER #{row.user_id}</div><h3>{row.profile.organization_name || row.profile.contact_name || row.email}</h3><p>{row.email}</p><p><b>Verification state:</b> {row.role === 'RECIPIENT' ? (row.verification_status === 'resubmission_required' ? 'Resubmission Required' : row.verification_status === 'rejected' ? 'Rejected' : 'Pending Verification') : row.verification_status}</p>{row.role === 'RECIPIENT' && <><p><b>Authorized Contact Person — Full Name:</b> {row.profile.contact_person || 'Not submitted'}</p><p><b>Mobile:</b> {row.profile.phone || 'Not submitted'}</p><p><b>Registration type:</b> {row.registration_type || row.profile.registration_type || 'Not submitted'}</p><p><b>Registration number:</b> {row.registration_number || row.profile.registration_number || 'Not provided'}</p><p><b>Submitted:</b> {row.submitted_at || 'Not recorded'}</p>{row.certificate_name ? <p><a className="outline" href={`${BASE}/admin/verifications/${row.user_id}/document`} target="_blank" rel="noreferrer">View private certificate · {row.certificate_name} ({Math.ceil(row.certificate_size / 1024)} KB)</a></p> : <p className="auth-error">No certificate is on file. This organization cannot be approved yet.</p>}</>}{row.role !== 'RECIPIENT' && <dl>{Object.entries(row.profile).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{Array.isArray(value) ? value.join(', ') : String(value)}</dd></div>)}</dl>}{row.review_reason && <p><b>Previous review note:</b> {row.review_reason}</p>}<label>Review reason<textarea value={reasons[`${row.user_id}:${row.role}`] || ''} onChange={event => setReasons(current => ({ ...current, [`${row.user_id}:${row.role}`]: event.target.value }))} maxLength={500} placeholder="Required when rejecting or requesting resubmission"/></label><div className="rescue-actions"><button className="primary" disabled={busy[`${row.user_id}:${row.role}`] || row.role === 'RECIPIENT' && !row.certificate_name} onClick={() => review(row, 'approved')}>Approve organization</button><button className="outline danger" disabled={busy[`${row.user_id}:${row.role}`]} onClick={() => review(row, 'rejected')}>Reject with reason</button>{row.role === 'RECIPIENT' && <button className="outline" disabled={busy[`${row.user_id}:${row.role}`]} onClick={() => review(row, 'resubmission_required')}>Request resubmission</button>}</div></article>)}</div>}</>;
}

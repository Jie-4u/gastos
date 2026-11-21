const app = document.getElementById('app');
const S = { view: 'welcome', me: null, avatar: null, stack: [], k: 'expense', plan: 'budgets', filter: 'all', q: '', rows: [], bills: [], budgets: [], goals: [], wallets: null, wd: null, wk: 'cash', w: null, wid: null, id: null, invite: null, inviteInfo: null, reset: null, resetSent: null };

/* ---------- Formatting helpers ---------- */
const peso = n => { const a = Math.abs(Number(n) || 0); return (n < 0 ? '−' : '') + '₱' + a.toLocaleString('en-PH', { minimumFractionDigits: a % 1 ? 2 : 0, maximumFractionDigits: 2 }); };
const kpeso = n => { const a = Math.abs(n); return (n < 0 ? '−' : '') + '₱' + (a >= 1e6 ? +(a / 1e6).toFixed(1) + 'M' : a >= 1e3 ? +(a / 1e3).toFixed(1) + 'k' : Math.round(a)); };
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const iso = d => new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
const today = () => iso(new Date());
const days = d => Math.round((new Date(d + 'T00:00') - new Date(today() + 'T00:00')) / 864e5);
const fdate = (d, o = { month: 'short', day: 'numeric' }) => new Date(d + 'T00:00').toLocaleDateString('en-PH', o);
const lbl = d => { const n = days(d); return n === 0 ? 'Today' : n === -1 ? 'Yesterday' : fdate(d, { weekday: 'short', month: 'short', day: 'numeric' }); };
const due = d => { const n = days(d); return n < 0 ? [`Overdue by ${-n} day${n === -1 ? '' : 's'}`, 'bad'] : n === 0 ? ['Due today', 'warn'] : n <= 3 ? [`Due in ${n} day${n === 1 ? '' : 's'}`, 'warn'] : [`Due ${fdate(d)}`, '']; };
const first = n => String(n || '').trim().split(/\s+/)[0];
const owner = () => !!S.me?.family?.owner;
const manageFinances = () => !!S.me?.family?.permissions?.manage_finances || owner() || S.me?.family?.role === 'Parent';
const isPrem = () => S.me?.family?.plan === 'premium';
const approved = t => !t.status || t.status === 'approved';
const sum = (l, f) => l.reduce((a, x) => a + f(x), 0);
const hue = s => [...String(s)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);

/* ---------- Icons (24px stroke) ---------- */
const ic = p => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${p}</svg>`;
const I = {
  home: ic('<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>'),
  list: ic('<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>'),
  plan: ic('<rect x="3" y="4" width="18" height="17" rx="3"/><path d="M16 2v4M8 2v4M3 10h18M8.5 15.5l2.5 2.5 4.5-4.5"/>'),
  users: ic('<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0M16 4a4 4 0 0 1 0 8M22 21a7 7 0 0 0-4-6.3"/>'),
  chart: ic('<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 6-6"/>'),
  plus: ic('<path d="M12 5v14M5 12h14"/>'),
  back: ic('<path d="m15 18-6-6 6-6"/>'),
  next: ic('<path d="m9 18 6-6-6-6"/>'),
  up: ic('<path d="M7 17 17 7M8 7h9v9"/>'),
  down: ic('<path d="M17 7 7 17M16 17H7V8"/>'),
  receipt: ic('<path d="M5 3h14v18l-3-2-2 2-2-2-2 2-2-2-3 2z"/><path d="M9 8h6M9 12h6"/>'),
  target: ic('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>'),
  trash: ic('<path d="M3 6h18M8 6V4h8v2M19 6l-1 14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1L5 6"/>'),
  edit: ic('<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>'),
  copy: ic('<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>'),
  x: ic('<path d="M18 6 6 18M6 6l12 12"/>'),
  check: ic('<path d="M20 6 9 17l-5-5"/>'),
  dl: ic('<path d="M12 3v12m-5-5 5 5 5-5M4 21h16"/>'),
  crown: ic('<path d="m3 7 4.5 4L12 4l4.5 7L21 7l-2 12H5z"/>'),
  logout: ic('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>'),
  eye: ic('<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'),
  eyeOff: ic('<path d="M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.1M6.6 6.6A17 17 0 0 0 2 12s3.5 7 10 7a9.7 9.7 0 0 0 5.4-1.6M9.9 9.9a3 3 0 0 0 4.2 4.2"/>'),
  search: ic('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>'),
  brief: ic('<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18"/>'),
  send: ic('<path d="M22 2 11 13M22 2l-7 20-4-9-9-4z"/>'),
  refresh: ic('<path d="M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5"/>'),
  camera: ic('<path d="M3 8a2 2 0 0 1 2-2h2l2-3h6l2 3h2a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><circle cx="12" cy="13" r="4"/>'),
  mail: ic('<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>'),
  wallet: ic('<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>'),
  card: ic('<rect x="2" y="5" width="20" height="14" rx="3"/><path d="M2 10h20M6 15h4"/>'),
  share: ic('<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4"/>'),
};

/* ---------- Categories ---------- */
const CATS = { expense: ['Food', 'Groceries', 'Bills', 'Transport', 'Tuition', 'Health', 'Shopping', 'Other'], income: ['Salary', 'Allowance', 'Business', 'Gift', 'Other'] };
const EMO = { Food: '🍲', Groceries: '🛒', Bills: '💡', Transport: '🚌', Tuition: '🎓', Health: '💊', Shopping: '🛍️', Salary: '💼', Allowance: '👛', Business: '🏪', Gift: '🎁', Other: '📦' };
const HUE = { Food: 24, Groceries: 140, Bills: 45, Transport: 210, Tuition: 265, Health: 340, Shopping: 300, Salary: 160, Allowance: 190, Business: 100, Gift: 0, Other: 220 };
const ch = c => HUE[c] ?? hue(c);
const catIco = c => `<span class="cat" style="--h:${ch(c)}">${EMO[c] || '🏷️'}</span>`;

/* ---------- Wallets (Cash Wallet & Card Wallet) ---------- */
const wIco = w => w.kind === 'cash' ? '💵' : '💳';
const isCredit = w => w.kind === 'card' && w.card_type === 'credit';
const wHue = w => w.kind === 'cash' ? 155 : hue(w.bank || w.name);
const wSub = w => w.kind === 'cash' ? 'Cash on hand' : `${esc(w.bank || (isCredit(w) ? 'Credit card' : 'Debit card'))} · ${isCredit(w) ? 'Credit' : 'Debit'} •••• ${esc(w.last4)}`;
// The coloured card face. With link=true it is a button that opens the wallet.
const wFace = (w, link) => {
  const credit = isCredit(w), tag = link ? 'button' : 'div', over = !credit && w.balance < 0;
  const pct = credit && w.credit_limit ? w.owed / w.credit_limit * 100 : 0;
  return `<${tag} class="wcard" style="--h:${wHue(w)}" ${link ? `data-go="wallet" data-wid="${w.id}"` : ''}>
    <span class="wtop"><span class="wname">${wIco(w)} ${esc(w.name)}</span>${over ? '<span class="wtag bad">Overdrawn</span>' : `<span class="wtag">${w.kind === 'cash' ? 'Cash' : credit ? 'Credit' : 'Debit'}</span>`}</span>
    <span><small>${credit ? 'Amount owed' : 'Balance'}</small><span class="wbal">${credit ? peso(w.owed) : peso(w.balance)}</span></span>
    ${credit && w.credit_limit ? `<span class="wutil">${bar(pct)}<small>${peso(w.available)} available of ${peso(w.credit_limit)}</small></span>` : ''}
    <span class="wbot"><span>${w.kind === 'card' ? `•••• •••• •••• ${esc(w.last4)}` : 'Cash wallet'}</span><span>${esc(w.bank || '')}</span></span></${tag}>`;
};
// Compact row for the Home screen.
const wRow = w => `<button class="item" data-go="wallet" data-wid="${w.id}"><span class="cat" style="--h:${wHue(w)}">${wIco(w)}</span><span class="grow"><b>${esc(w.name)}</b><small>${wSub(w)}</small></span><span class="amt ${w.balance < 0 ? 'tx-out' : ''}">${peso(w.balance)}</span></button>`;
const walletChips = (ws, sel) => ws.length ? `<fieldset class="field"><legend>Wallet</legend><div class="chips"><label class="chip"><input type="radio" name="wallet_id" value="" ${sel ? '' : 'checked'}>No wallet</label>${ws.map(w => `<label class="chip"><input type="radio" name="wallet_id" value="${w.id}" ${String(sel) === String(w.id) ? 'checked' : ''}>${wIco(w)} ${esc(w.name)}${w.kind === 'card' ? ` ••${esc(w.last4)}` : ''}</label>`).join('')}</div></fieldset>` : '';

/* ---------- Small components ---------- */
const logo = '<span class="wordmark">Gastos</span>';
const bar = (p, cls = '', color = '') => `<span class="bar ${cls}"><i style="width:${Math.min(100, Math.max(0, p))}%;${color ? `background:${color}` : ''}"></i></span>`;
const empty = (art, title, text, cta = '') => `<div class="empty"><div class="art">${art}</div><b>${title}</b><p>${text}</p>${cta}</div>`;
const cardH = (title, more = '') => `<div class="card-h"><h3>${title}</h3>${more}</div>`;
const field = (label, input, hint = '') => `<label class="field"><span>${label}</span>${input}${hint ? `<small>${hint}</small>` : ''}</label>`;
const pw = (name, ph, extra = '') => `<div class="pw"><input name="${name}" type="password" placeholder="${ph}" ${extra}><button type="button" class="link peek" data-act="peek" aria-label="Show password">Show</button></div>`;
const money = (name, v = '', extra = '') => `<input name="${name}" type="number" inputmode="decimal" step="0.01" min="0.01" placeholder="₱ 0.00" value="${v}" required ${extra}>`;
const stat = (label, value, cls = '') => `<div class="stat"><small>${label}</small><b class="${cls}">${value}</b></div>`;
const av = (name, img, cls = '') => img ? `<img class="av ${cls}" src="${esc(img)}" alt="">` : `<span class="av ${cls}" style="--h:${hue(name)}">${esc(String(name || '?').trim().split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase())}</span>`;
const meBtn = () => `<button class="me-btn" data-go="profile" aria-label="Your profile">${av(S.me.name, S.avatar, 'sm')}</button>`;
const seg = (items, cur, attr) => `<div class="seg">${items.map(([k, l]) => `<button ${attr(k)} class="${cur === k ? 'on' : ''}">${l}</button>`).join('')}</div>`;
const lock = (title, sub) => `<button class="promo" data-go="premium"><span class="crown">${I.crown}</span><span class="grow"><b>${title}</b><small>${sub}</small></span>${I.next}</button>`;

let tt;
function toast(m, err) { const t = document.getElementById('toast'); t.textContent = m; t.className = 'on' + (err ? ' err' : ''); clearTimeout(tt); tt = setTimeout(() => t.className = '', 3400); }

function sheet(html, onClose) {
  closeSheet();
  const s = document.createElement('div');
  s.className = 'scrim'; s.onClose = onClose;
  s.innerHTML = `<div class="sheet" role="dialog" aria-modal="true"><span class="grab"></span>${html}</div>`;
  s.addEventListener('click', e => { if (e.target === s || e.target.closest('[data-close]')) closeSheet(); });
  document.body.append(s);
  requestAnimationFrame(() => s.classList.add('on'));
  setTimeout(() => s.querySelector('input:not([type=hidden]),select,[data-ok]')?.focus(), 60);
  return s;
}
function closeSheet() { document.querySelectorAll('.scrim').forEach(s => { s.remove(); s.onClose?.(); }); }
const ask = (title, msg, ok = 'Confirm', danger) => new Promise(res => {
  const s = sheet(`<h3>${title}</h3><p class="mu">${msg}</p><div class="actions"><button class="btn ghost" data-close>Cancel</button><button class="btn ${danger ? 'danger' : ''}" data-ok>${ok}</button></div>`, () => res(false));
  s.querySelector('[data-ok]').onclick = () => { res(true); closeSheet(); };
});

async function api(p, m = 'GET', b) {
  const r = await fetch('/api/' + p, { method: m, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + (localStorage.t || '') }, body: b ? JSON.stringify(b) : undefined });
  if (p === 'export' && r.ok) return r.blob();
  const d = await r.json().catch(() => ({}));
  if (r.status === 401 && p !== 'signin') { localStorage.removeItem('t'); S.me = null; S.view = 'welcome'; }
  if (!r.ok) throw new Error(d.error || 'Something went wrong');
  return d;
}

/* ---------- Shared list rows ---------- */
const statusBadge = t => t.status === 'pending' ? ' <span class="badge warn">Pending approval</span>' : t.status === 'rejected' ? ' <span class="badge bad">Rejected</span>' : '';
const txRow = t => { const tag = t.id && t.can_edit ? 'button' : 'div'; return `<${tag} class="item tx ${approved(t) ? 'tx-' + t.kind : 'tx-pending'}" ${tag === 'button' ? `data-go="edittx" data-id="${t.id}"` : ''}>${catIco(t.category)}<span class="grow"><b>${esc(t.note || t.category)}</b><small><span class="cchip" style="--h:${ch(t.category)}">${esc(t.category)}</span> ${esc(t.member)}${t.wallet ? ` · ${esc(t.wallet)}` : ''}${t.id ? '' : ` · ${lbl(t.date)}`}${t.has_receipt ? ' · 🧾' : ''}${statusBadge(t)}</small></span><span class="amt ${approved(t) ? t.kind : 'mu'}">${t.kind === 'income' ? '+' : '−'}${peso(t.amount)}</span></${tag}>`; };
const approvalRow = t => `<div class="item">${catIco(t.category)}<span class="grow"><b>${esc(t.note || t.category)}</b><small>${esc(t.member)} · ${lbl(t.date)}</small></span><span class="end"><span class="amt">−${peso(t.amount)}</span><span class="row-acts">${t.has_receipt ? `<button class="iconbtn sm" data-act="receipt" data-id="${t.id}" aria-label="View receipt">🧾</button>` : ''}<button class="iconbtn sm" data-act="reject" data-id="${t.id}" aria-label="Reject ${esc(t.note || t.category)}">${I.x}</button><button class="btn sm soft" data-act="approve" data-id="${t.id}">${I.check}Approve</button></span></span></div>`;
const billRow = (b, full) => { const [t, c] = due(b.due); return `<div class="item">${catIco('Bills')}<span class="grow"><b>${esc(b.name)}</b><small><span class="badge ${c}">${t}</span></small></span><span class="end"><span class="amt">${peso(b.amount)}</span>${full && manageFinances() ? `<span class="row-acts"><button class="iconbtn sm" data-go="editbill" data-id="${b.id}" aria-label="Edit ${esc(b.name)}">${I.edit}</button><button class="btn sm soft" data-act="pay" data-id="${b.id}">${I.check}Paid</button></span>` : ''}</span></div>`; };
const budgetRow = b => {
  const lim = b.limit ?? b.monthly_limit, p = lim ? b.spent / lim * 100 : 0, cls = p >= 100 ? 'over' : p >= 80 ? 'warn' : '';
  return `<span class="brow">${catIco(b.category)}<span class="grow"><span class="between"><b>${esc(b.category)}</b><span class="small ${cls ? 'tx-' + cls : 'mu'}">${peso(b.spent)} / ${peso(lim)}</span></span>${bar(p, cls)}<small>${p >= 100 ? `Over by ${peso(b.spent - lim)}` : `${peso(lim - b.spent)} left · ${Math.round(p)}% used`}</small></span></span>`;
};
const flowChart = ms => {
  const max = Math.max(1, ...ms.flatMap(m => [m.income, m.expense]));
  return `<div class="chart">${ms.map((m, i) => `<div class="col ${i === ms.length - 1 ? 'now' : ''}" title="${m.label}: income ${peso(m.income)}, expenses ${peso(m.expense)}"><div class="bars"><i class="in" style="height:${m.income / max * 100}%"></i><i class="ex" style="height:${m.expense / max * 100}%"></i></div><span>${m.label}</span></div>`).join('')}</div><div class="legend"><span><i class="in"></i>Income</span><span><i class="ex"></i>Expenses</span></div>`;
};
const catBreakdown = (totals, total) => {
  const l = Object.entries(totals || {}).sort((a, b) => b[1] - a[1]);
  return l.length ? `<div class="stack">${l.map(([k, v]) => `<div class="brow">${catIco(k)}<span class="grow"><span class="between"><b>${esc(k)}</b><span class="amt">${peso(v)}</span></span>${bar(v / total * 100, '', `hsl(${ch(k)} 60% 48%)`)}<small>${Math.round(v / total * 100)}% of spending</small></span></div>`).join('')}</div>` : '<p class="note">No expenses recorded this month yet.</p>';
};

/* ---------- Views ---------- */
const V = {};
const auth = (title, sub, body) => ({ bare: 1, title, html: `<section class="auth"><div class="auth-top"><button class="link" data-back>Back</button>${logo}</div><h1>${title}</h1><p class="mu">${sub}</p>${body}</section>` });

V.welcome = async () => ({ bare: 1, html: `<section class="welcome"><div class="intro">${logo}
  <h1>Every peso,<br><em>together.</em></h1>
  <p class="lead">Gastos is the shared money app for Filipino families: track spending, stay ahead of bills, and save for what matters in one place.</p>
  <ul class="perks"><li>See where the household budget goes</li><li>Know which bills are due before they're late</li><li>Save toward goals as a family</li></ul>
  <div class="stack"><button class="btn lg" data-go="signup">Create a free account</button><button class="btn ghost lg" data-go="signin">Sign in</button></div>
  <p class="note">Free for up to 4 family members.</p></div></section>` });

V.signup = async () => {
  const inv = S.inviteInfo;
  return auth(inv ? `Join ${esc(inv.family)}` : 'Create your account', inv ? `Create an account with <b>${esc(inv.email)}</b> to accept your invitation.` : 'It takes less than a minute. No credit card needed.',
    `<form data-f="signup" class="stack">${inv ? `<input type="hidden" name="invite_token" value="${esc(S.invite)}">` : ''}
    ${field('Full name', '<input name="name" autocomplete="name" placeholder="Juan dela Cruz" maxlength="120" required>')}
    ${field('Email', `<input name="email" type="email" autocomplete="email" placeholder="you@example.com" ${inv ? `value="${esc(inv.email)}" readonly` : ''} required>`)}
    ${field('Password', pw('password', 'At least 8 characters', 'minlength="8" autocomplete="new-password" required'))}
    ${field('Confirm password', pw('password2', 'Repeat your password', 'minlength="8" autocomplete="new-password" required'))}
    <button class="btn lg">Create account</button><p class="foot">Already have an account? <button type="button" class="link" data-go="signin">Sign in</button></p></form>`);
};
V.signin = async () => auth('Welcome back', S.inviteInfo ? `Sign in as <b>${esc(S.inviteInfo.email)}</b> to accept your invitation.` : 'Sign in to see how your family is doing.',
  `<form data-f="signin" class="stack">${field('Email', `<input name="email" type="email" autocomplete="email" placeholder="you@example.com" value="${esc(S.inviteInfo?.email || '')}" required>`)}
  ${field('Password', pw('password', 'Your password', 'autocomplete="current-password" required'))}
  <button type="button" class="link forgot" data-go="forgot">Forgot password?</button>
  <button class="btn lg">Sign in</button><p class="foot">New to Gastos? <button type="button" class="link" data-go="signup">Create an account</button></p></form>`);
V.forgot = async () => S.resetSent
  ? auth('Check your inbox', 'If an account exists for that email, a reset link is on its way. The link expires in 15 minutes.', `<div class="card"><b>${esc(S.resetSent)}</b><p class="note">Didn't get it? Check spam, or try again in a minute.</p></div><button class="btn lg" data-act="toSignin">Back to sign in</button>`)
  : auth('Reset your password', "Enter your account email and we'll send you a link to choose a new password.", `<form data-f="forgot" class="stack">${field('Email', '<input name="email" type="email" autocomplete="email" placeholder="you@example.com" required>')}<button class="btn lg">Send reset link</button></form>`);
V.reset = async () => auth('Choose a new password', 'Use at least 8 characters. You will be signed out on other devices.',
  `<form data-f="reset" class="stack">${field('New password', pw('password', 'At least 8 characters', 'minlength="8" autocomplete="new-password" required'))}${field('Confirm password', pw('password2', 'Repeat your password', 'minlength="8" autocomplete="new-password" required'))}<button class="btn lg">Update password</button></form>`);
V.join = async () => {
  const i = S.inviteInfo, same = S.me && S.me.email.toLowerCase() === i.email.toLowerCase();
  return auth("You're invited 🎉", `${esc(i.inviter || 'A family member')} wants you to manage money together on Gastos.`,
    `<div class="card invite-card">${av(i.family)}<span class="grow"><b>${esc(i.family)}</b><small>Invitation for ${esc(i.email)}${i.expires ? ` · expires ${fdate(i.expires.slice(0, 10))}` : ''}</small></span></div>` +
    (same ? `<button class="btn lg" data-act="accept">Join ${esc(i.family)}</button>`
      : S.me ? `<p class="note">You're signed in as <b>${esc(S.me.email)}</b>. Sign out, then sign in or sign up with <b>${esc(i.email)}</b> to accept.</p><button class="btn ghost lg" data-act="signout">Sign out</button>`
        : `<div class="stack"><button class="btn lg" data-go="signup">Create an account</button><button class="btn ghost lg" data-go="signin">I already have an account</button></div>`));
};

V.family = async () => ({ title: 'Set up your family', sub: `Welcome, ${esc(first(S.me.name))}!`, narrow: 1, html: `<div class="card stack">${empty('🏡', 'Your shared money space', "Create a family to track income, bills and savings together. You'll be the owner and can invite others.")}
  <form data-f="family" class="stack">${field('Family name', '<input name="name" placeholder="e.g. Santos Family" maxlength="120" required>')}
  <fieldset class="field"><legend>Your role</legend><div class="seg"><label><input type="radio" name="role" value="Parent" checked><span>Parent</span></label><label><input type="radio" name="role" value="Member"><span>Member</span></label></div></fieldset>
  <button class="btn lg">Create family</button></form></div>
  <p class="note center">Joining someone else's family? Open the invitation link from your email.</p><button class="btn ghost" data-act="signout">${I.logout}Sign out</button>` });

const inviteForm = () => {
  const f = S.me.family, used = f.members.length + f.invites.filter(i => i.status === 'pending').length;
  return `<form data-f="invite" class="card stack">${cardH('Invite a family member', `<span class="badge ${used >= f.limit ? 'bad' : ''}">${used} / ${f.limit} seats</span>`)}<p class="note" style="margin-top:-8px">They'll get a link to join <b>${esc(f.name)}</b>. Links expire after 7 days.</p><input name="email" type="email" placeholder="family@example.com" aria-label="Member email" required><label class="field"><span>Assign role</span><select name="role" aria-label="Family role"><option value="Member">Member</option><option value="Parent">Parent</option></select></label><small class="note">Parents can manage bills, budgets, goals and expense approvals. Members can manage their own transactions and contribute to goals.</small><button class="btn">${I.send}Invite</button></form>`;
};
const memberList = () => {
  const f = S.me.family;
  return `<div class="card list">${f.members.map(m => { const role = m.role || 'Member'; const desc = m.owner ? 'Full access · manages family, plan & finances' : role === 'Parent' ? 'Can manage bills, budgets, goals & expense approvals' : 'Can view family finances, manage own transactions & contribute to goals'; return `<div class="item">${av(m.name)}<span class="grow"><b>${esc(m.name)}</b><small>${desc}</small></span>${m.owner ? '<span class="badge gold">Owner</span>' : owner() ? `<select class="member-role" data-member-role data-id="${m.id}" data-current-role="${esc(role)}" aria-label="Role for ${esc(m.name)}"><option value="Member" ${role === 'Member' ? 'selected' : ''}>Member</option><option value="Parent" ${role === 'Parent' ? 'selected' : ''}>Parent</option></select><button class="iconbtn sm" data-act="removemember" data-id="${m.id}" aria-label="Remove ${esc(m.name)}">${I.x}</button>` : `<span class="badge">${esc(role)}</span>`}</div>`; }).join('')}</div>`;
};
const inviteList = () => {
  const l = S.me.family.invites.filter(i => i.status === 'pending' || i.status === 'expired');
  return l.length ? `<h3 class="sec">Invitations</h3><div class="card list">${l.map(i => `<div class="item"><span class="av" style="--h:${hue(i.email)}">${I.mail}</span><span class="grow"><b>${esc(i.email)}</b><small>${esc(i.role || 'Member')} · ${i.status === 'expired' ? '<span class="badge bad">Expired</span>' : `${i.expires ? `Expires ${fdate(i.expires.slice(0, 10))} · ` : ''}${i.delivery === 'sent' ? 'Email sent' : i.delivery === 'failed' ? 'Email failed, share the link' : 'Share the link'}`}</small></span>${owner() ? `<span class="row-acts">${i.link ? `<button class="iconbtn sm" data-act="copylink" data-id="${i.id}" title="Copy invite link" aria-label="Copy invite link">${I.copy}</button>` : ''}<button class="iconbtn sm" data-act="resend" data-id="${i.id}" title="Resend" aria-label="Resend invite">${I.refresh}</button><button class="iconbtn sm" data-act="revoke" data-id="${i.id}" title="Cancel invite" aria-label="Cancel invite">${I.x}</button></span>` : '<span class="badge warn">Pending</span>'}</div>`).join('')}</div>` : '';
};
V.invite = async () => ({ title: 'Invite your family', sub: 'Almost done', narrow: 1, html: `${inviteForm()}<h3 class="sec">Members</h3>${memberList()}${inviteList()}<button class="btn lg" data-act="finish">Continue to dashboard ${I.next}</button>` });

V.home = async () => {
  const d = await api('dashboard'), f = S.me.family, h = new Date().getHours();
  S.bills = d.bills;
  const month = new Date().toLocaleDateString('en-PH', { month: 'long' });
  const o = n => `style="order:${n}"`, soon = isPrem() ? d.bills.filter(b => days(b.due) <= 3) : [];
  const reminders = soon.length ? `<div class="alert" ${o(0)} role="status"><b>⏰ Bill reminder${soon.length > 1 ? 's' : ''}</b>${soon.map(b => `<span>${esc(b.name)}: ${due(b.due)[0].toLowerCase()} · ${peso(b.amount)}</span>`).join('')}</div>` : '';
  const approvals = d.approvals.length ? `<div class="card" ${o(0)}>${cardH(`Waiting for your approval`, `<span class="badge warn">${d.approvals.length}</span>`)}<div class="list">${d.approvals.map(approvalRow).join('')}</div></div>` : '';
  const wl = d.wallets || [], walletCard = `<div class="card" ${o(3)}>${cardH('Wallets', wl.length ? '<button class="link" data-go="wallets">See all</button>' : '')}${wl.length ? `<div class="list">${wl.map(wRow).join('')}</div>` : empty('👛', 'Your wallets', 'Add your Cash Wallet or Card Wallet to see where your money sits.', `<button class="btn sm" data-go="addwallet" data-wk="cash">${I.plus}Add wallet</button>`)}</div>`;
  return { title: `${h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'}, ${esc(first(S.me.name))}`, sub: esc(f.name), nav: 1, right: meBtn(), html: `<div class="grid"><div class="col">${reminders}${approvals}
  <section class="hero" ${o(1)}><small>${month} balance</small><div class="big">${peso(d.balance)}</div><div class="split"><div class="pill"><i>${I.up}</i><span><small>Income</small><b>${peso(d.income)}</b></span></div><div class="pill"><i>${I.down}</i><span><small>Expenses</small><b>${peso(d.expense)}</b></span></div></div></section>
  <div class="quick" ${o(2)}><button data-go="addtx" data-k="income"><i>${I.up}</i>Income</button><button data-go="addtx" data-k="expense"><i class="ex">${I.down}</i>Expense</button>${manageFinances() ? `<button data-go="addbill"><i>${I.receipt}</i>Add bill</button><button data-go="addgoal"><i>${I.target}</i>New goal</button>` : `<button data-tab="plan" data-plan="bills"><i>${I.receipt}</i>Bills</button><button data-tab="plan" data-plan="goals"><i>${I.target}</i>Goals</button>`}</div>
  <div class="card" ${o(5)}>${cardH('Recent activity', '<button class="link" data-tab="tx">See all</button>')}${d.recent.length ? `<div class="list">${d.recent.map(txRow).join('')}</div>` : empty('🧾', 'No transactions yet', 'Log your first income or expense to get started.', `<button class="btn sm" data-go="addtx" data-k="expense">${I.plus}Add transaction</button>`)}</div>
  <div class="card" ${o(6)}>${cardH('Cash flow', '<button class="link" data-tab="reports">Reports</button>')}${flowChart(d.months)}</div>
  </div><div class="col">
  ${walletCard}
  ${d.bills.length ? `<div class="card" ${o(3)}>${cardH('Upcoming bills', '<button class="link" data-tab="plan" data-plan="bills">See all</button>')}<div class="list">${d.bills.slice(0, 3).map(b => billRow(b)).join('')}</div></div>` : ''}
  ${d.budgets.length ? `<div class="card" ${o(4)}>${cardH(`${month} budgets`, '<button class="link" data-tab="plan" data-plan="budgets">Manage</button>')}<div class="stack">${d.budgets.slice(0, 4).map(budgetRow).join('')}</div></div>` : ''}
  <div class="card" ${o(7)}>${cardH('Spending by category')}${catBreakdown(d.category_totals, d.expense)}</div>
  <button class="card goal" style="order:8;text-align:left;width:100%" data-tab="plan" data-plan="goals"><span class="ring" style="--p:${d.savings.percent}"><span>${d.savings.percent}%</span></span><span class="grow"><b>Family savings</b><small>${d.savings.target ? `${peso(d.savings.saved)} of ${peso(d.savings.target)} saved` : 'Create a goal to start saving together'}</small></span>${I.next}</button>
  ${f.plan === 'free' && owner() ? `<button class="promo" ${o(9)} data-go="premium"><span class="crown">${I.crown}</span><span class="grow"><b>Upgrade to Premium</b><small>Up to 10 members and advanced reports</small></span>${I.next}</button>` : ''}
  </div></div>` };
};

V.tx = async () => {
  S.rows = await api('transactions');
  return { title: 'Activity', sub: 'Every family transaction', nav: 1, right: meBtn(), html: `<div class="stack"><label class="field" style="position:relative"><span class="sr" hidden>Search</span><span style="position:absolute;left:14px;top:14px;color:var(--faint)">${I.search}</span><input data-search placeholder="Search notes, categories or members" value="${esc(S.q)}" style="padding-left:44px" aria-label="Search transactions"></label>${seg([['all', 'All'], ['expense', 'Expenses'], ['income', 'Income']], S.filter, k => `data-filter="${k}"`)}</div><div id="txlist" class="stack">${txList()}</div>` };
};
function txList() {
  if (!S.rows.length) return empty('🧾', 'No transactions yet', 'Add your first income or expense to start seeing where your money goes.', `<button class="btn" data-go="addtx" data-k="expense">${I.plus}Add transaction</button>`);
  const q = S.q.trim().toLowerCase(), rows = S.rows.filter(t => (S.filter === 'all' || t.kind === S.filter) && (!q || [t.note, t.category, t.member].join(' ').toLowerCase().includes(q)));
  if (!rows.length) return empty('🔍', 'No matches', 'Try a different search or filter.');
  const ok = rows.filter(approved), inc = sum(ok, t => t.kind === 'income' ? t.amount : 0), exp = sum(ok, t => t.kind === 'expense' ? t.amount : 0), groups = {};
  rows.forEach(t => (groups[t.date] ||= []).push(t));
  return `<div class="stats">${stat('Money in', peso(inc), 'tx-in')}${stat('Money out', peso(exp), 'tx-out')}${stat('Net', peso(inc - exp), inc - exp < 0 ? 'tx-out' : 'tx-in')}</div><div class="legend2"><span><i class="dot in"></i>Income</span><span><i class="dot out"></i>Expense</span><span><i class="dot pend"></i>Pending / rejected</span></div>` +
    Object.entries(groups).map(([d, l]) => { const n = sum(l.filter(approved), t => t.kind === 'income' ? t.amount : -t.amount); return `<div><div class="day"><span>${lbl(d)}</span><span class="${n > 0 ? 'tx-in' : n < 0 ? 'tx-out' : ''}">${n > 0 ? '+' : ''}${peso(n)}</span></div><div class="card list" style="margin-top:6px">${l.map(txRow).join('')}</div></div>`; }).join('') +
    (S.rows.length >= 100 ? '<p class="note center">Showing the 100 most recent transactions. Export the full history from Reports.</p>' : '');
}

const receiptInput = '<input type="file" accept="image/*" capture="environment" class="vh" data-receipt>';
const receiptBlock = url => url
  ? `<img class="rimg" src="${esc(url)}" alt="Receipt photo"><span class="row-acts"><label class="btn sm ghost">${I.camera}Retake${receiptInput}</label><button type="button" class="btn sm text-danger" data-act="rmreceipt">${I.trash}Remove</button></span>`
  : `<label class="btn ghost">${I.camera}Scan receipt${receiptInput}</label><small class="note">Gastos reads the total and fills in the amount.</small>`;
const catChips = (k, sel) => { const l = [...CATS[k]]; if (sel && !l.includes(sel)) l.push(sel); sel = sel || l[0]; return l.map(c => `<label class="chip"><input type="radio" name="category" value="${esc(c)}" ${c === sel ? 'checked' : ''}>${EMO[c] || '🏷️'} ${esc(c)}</label>`).join(''); };
const txForm = (t, ws = []) => {
  const k = t.kind || S.k;
  return `<form data-f="savetx" class="stack">${t.id ? `<input type="hidden" name="id" value="${t.id}">` : ''}
  <div class="seg">${[['expense', 'Expense'], ['income', 'Income']].map(([v, l]) => `<label><input type="radio" name="kind" value="${v}" ${k === v ? 'checked' : ''}><span>${l}</span></label>`).join('')}</div>
  <label class="amount"><span>₱</span><input name="amount" type="number" inputmode="decimal" step="0.01" min="0.01" placeholder="0" value="${t.amount ?? ''}" aria-label="Amount" required autofocus></label>
  <fieldset class="field"><legend>Category</legend><div class="chips" id="catchips">${catChips(k, t.category)}</div></fieldset>
  ${t.id && t.mine === false ? '' : walletChips(ws, t.id ? t.wallet_id : S.w)}
  <div class="two">${field('Date', `<input name="date" type="date" value="${t.date || today()}" required>`)}${field('Note', `<input name="note" maxlength="200" placeholder="What was this for?" value="${esc(t.note || '')}">`)}</div>
  ${isPrem() ? `<div class="receipt" id="rcpt">${receiptBlock(t.receipt_data)}</div>` : lock('Scan receipts with Premium', 'Snap a photo and Gastos reads the total')}
  ${t.status === 'pending' ? '<p class="note">This expense is waiting for the family owner\'s approval.</p>' : t.status === 'rejected' ? '<p class="note">The family owner rejected this expense. Edit it to send it for approval again, or delete it.</p>' : ''}
  <button class="btn lg">${t.id ? 'Save changes' : 'Save transaction'}</button>${t.id ? `<button type="button" class="btn text-danger" data-act="deltx" data-id="${t.id}">${I.trash}Delete transaction</button>` : ''}</form>`;
};
V.addtx = async () => ({ title: 'New transaction', back: 1, narrow: 1, html: txForm({}, (await api('wallets')).wallets) });
V.edittx = async () => { const [t, w] = await Promise.all([api(`transactions/${S.id}`), api('wallets')]); return { title: 'Edit transaction', back: 1, narrow: 1, html: txForm(t, w.wallets) }; };

/* ---------- Wallets screens ---------- */
V.wallets = async () => {
  const { wallets: ws, totals: t } = await api('wallets'), m = true;
  const cash = ws.filter(w => w.kind === 'cash'), cards = ws.filter(w => w.kind === 'card');
  const add = (k, text) => m ? `<button class="btn ghost" data-go="addwallet" data-wk="${k}">${I.plus}${text}</button>` : '';
  if (!ws.length) return { title: 'Wallets', sub: 'Cash & cards', back: 1, narrow: 1, html: `<div class="card">${empty('👛', 'No wallets yet', 'Add your own Cash Wallet for money on hand and a Card Wallet for your debit and credit cards. Pick a wallet when you log a transaction and Gastos keeps each balance up to date. Only you can see your wallets.', m ? `<button class="btn" data-go="addwallet" data-wk="cash">${I.plus}Add a cash wallet</button>` : '')}</div>${m ? `<button class="btn ghost" data-go="addwallet" data-wk="card">${I.plus}Add a card</button>` : ''}` };
  return { title: 'Wallets', sub: 'Cash & cards', back: 1, narrow: 1, html: `<section class="hero"><small>Available to spend</small><div class="big">${peso(t.available)}</div><div class="split"><div class="pill"><i>${I.wallet}</i><span><small>Cash</small><b>${peso(t.cash)}</b></span></div><div class="pill"><i>${I.card}</i><span><small>Credit owed</small><b>${peso(t.owed)}</b></span></div></div></section>
  <h3 class="sec">Cash Wallet</h3>${cash.length ? `<div class="stack">${cash.map(w => wFace(w, 1)).join('')}</div>` : '<p class="note">No cash wallet yet.</p>'}${add('cash', 'Add a cash wallet')}
  <h3 class="sec">Card Wallet</h3>${cards.length ? `<div class="stack">${cards.map(w => wFace(w, 1)).join('')}</div>` : '<p class="note">No cards yet.</p>'}${add('card', 'Add a card')}
  <p class="note center">Wallets are private to your account.</p>` };
};
V.wallet = async () => {
  const w = S.wd = await api(`wallets/${S.wid}`), m = true, credit = isCredit(w);
  return { title: esc(w.name), sub: wSub(w), back: 1, narrow: 1, html: `${wFace(w)}
  <div class="quick"><button data-go="addtx" data-k="income" data-w="${w.id}"><i>${I.up}</i>${credit ? 'Payment' : 'Income'}</button><button data-go="addtx" data-k="expense" data-w="${w.id}"><i class="ex">${I.down}</i>Expense</button>${m ? `<button data-act="walletadjust" data-id="${w.id}"><i>${I.refresh}</i>Adjust</button><button data-go="editwallet" data-wid="${w.id}"><i>${I.edit}</i>Edit</button>` : ''}</div>
  <div class="stats">${stat('In this month', peso(w.month_income), 'tx-in')}${stat('Out this month', peso(w.month_expense), 'tx-out')}${credit && w.credit_limit ? stat('Credit limit', peso(w.credit_limit)) : ''}</div>
  <div class="card">${cardH('Activity')}${w.transactions.length ? `<div class="list">${w.transactions.map(txRow).join('')}</div>` : empty('🧾', 'No activity yet', 'Choose this wallet when you log a transaction and it will show up here.')}</div>
  ${m ? `<button class="btn text-danger" data-act="delwallet" data-id="${w.id}">${I.trash}Delete wallet</button>` : ''}` };
};
const walletForm = w => {
  const kind = w.kind || S.wk, card = kind === 'card', credit = isCredit(w);
  return `<form data-f="savewallet" class="stack">${w.id ? `<input type="hidden" name="id" value="${w.id}">` : ''}<input type="hidden" name="kind" value="${kind}">
  ${field(card ? 'Card nickname' : 'Wallet name', `<input name="name" maxlength="80" placeholder="${card ? 'e.g. Payroll card' : 'e.g. Cash on hand'}" value="${esc(w.name || '')}" required>`)}
  ${card ? `${field('Bank or issuer', `<input name="bank" maxlength="80" placeholder="e.g. BDO, BPI, GCash" value="${esc(w.bank || '')}">`)}
  ${w.id ? '' : `<fieldset class="field"><legend>Card type</legend><div class="seg">${[['debit', 'Debit'], ['credit', 'Credit']].map(([v, l]) => `<label><input type="radio" name="card_type" value="${v}" ${v === 'debit' ? 'checked' : ''}><span>${l}</span></label>`).join('')}</div></fieldset>`}
  ${field('Last 4 digits', `<input name="last4" inputmode="numeric" pattern="[0-9]{4}" maxlength="4" autocomplete="off" placeholder="1234" value="${esc(w.last4 || '')}" required>`, 'Only the last 4 digits. Never enter the full card number, expiry or CVV.')}
  <div class="only-credit" ${credit ? '' : 'hidden'}>${field('Credit limit', `<input name="credit_limit" type="number" inputmode="decimal" step="0.01" min="0.01" placeholder="₱ 0.00" value="${w.credit_limit ?? ''}">`, 'Optional. Lets Gastos show your available credit.')}</div>` : ''}
  ${w.id ? '<p class="note">To correct the balance, open the wallet and tap Adjust.</p>' : `<label class="field"><span id="ballbl">${card ? 'Current balance' : 'Cash on hand now'}</span><input name="opening_balance" type="number" inputmode="decimal" step="0.01" min="0" placeholder="₱ 0.00" value="0"><small>Where this wallet starts today. Transactions you link to it change it from here.</small></label>`}
  <button class="btn lg">${w.id ? 'Save changes' : card ? 'Add card' : 'Add wallet'}</button></form>`;
};
V.addwallet = async () => ({ title: S.wk === 'card' ? 'Add a card' : 'Add a cash wallet', back: 1, narrow: 1, html: walletForm({}) });
V.editwallet = async () => ({ title: 'Edit wallet', back: 1, narrow: 1, html: walletForm(await api(`wallets/${S.wid}`)) });

const P = {};
V.plan = async () => ({ title: 'Plan', sub: 'Budgets, bills & savings goals', nav: 1, right: meBtn(), html: seg([['budgets', 'Budgets'], ['bills', 'Bills'], ['goals', 'Goals']], S.plan, k => `data-tab="plan" data-plan="${k}"`) + await P[S.plan]() });
P.budgets = async () => {
  const b = S.budgets = await api('budgets'), full = !isPrem() && b.length >= 3;
  const add = !manageFinances() ? '' : full ? lock('Unlimited budgets with Premium', 'The Free plan includes 3 budgets') : `<button class="btn ${b.length ? 'ghost' : ''}" data-act="budget">${I.plus}Set a budget</button>`;
  if (!b.length) return `<div class="card">${empty('🧮', 'No budgets yet', manageFinances() ? 'Set a monthly limit per category and Gastos will warn you when you get close.' : "Your family Parent or owner hasn't set any budgets yet.", add)}</div>`;
  const lim = sum(b, x => x.monthly_limit), sp = sum(b, x => x.spent);
  return `<div class="card stack"><div class="between"><span><small class="mu">Spent this month</small><h2>${peso(sp)}</h2></span><span class="mu small">of ${peso(lim)}</span></div>${bar(sp / lim * 100, sp >= lim ? 'over' : sp >= lim * .8 ? 'warn' : '')}</div>
  <div class="card list">${b.map(x => manageFinances() ? `<button class="item" data-act="budget" data-id="${x.id}">${budgetRow(x)}</button>` : `<div class="item">${budgetRow(x)}</div>`).join('')}</div>${add}`;
};
P.bills = async () => {
  const b = S.bills = await api('bills'), add = manageFinances() ? `<button class="btn ${b.length ? 'ghost' : ''}" data-go="addbill">${I.plus}Add a bill</button>` : '';
  if (!b.length) return `<div class="card">${empty('✅', 'All caught up', 'No unpaid bills. Add bills like rent, Meralco or tuition so nobody forgets.', add)}</div>`;
  const over = b.filter(x => days(x.due) < 0).length;
  return `<div class="stats">${stat('Total unpaid', peso(sum(b, x => x.amount)))}${stat('Overdue', over, over ? 'tx-out' : '')}${stat('Next due', fdate(b[0].due))}</div><div class="card list">${b.map(x => billRow(x, 1)).join('')}</div>${add}${manageFinances() ? '' : '<p class="note center">Only a Parent or family owner can manage bills.</p>'}`;
};
P.goals = async () => {
  const g = S.goals = await api('goals'), add = manageFinances() ? `<button class="btn ${g.length ? 'ghost' : ''}" data-go="addgoal">${I.plus}Create a goal</button>` : '';
  if (!g.length) return `<div class="card">${empty('🎯', 'Start a savings goal', 'Emergency fund, tuition, a family trip: save for it together and watch the progress.', add)}</div>`;
  return g.map(x => { const p = Math.min(100, Math.round(x.saved * 100 / x.target)); return `<div class="card goal"><span class="ring" style="--p:${p}"><span>${p}%</span></span><span class="grow"><b>${esc(x.name)}</b><small>${peso(x.saved)} of ${peso(x.target)}</small><small>${p >= 100 ? '🎉 Goal reached!' : `${peso(x.target - x.saved)} to go`}</small></span><button class="btn sm soft" data-act="fund" data-id="${x.id}">${I.plus}Add</button></div>`; }).join('') + add;
};

const billForm = b => `<form data-f="savebill" class="stack">${b.id ? `<input type="hidden" name="id" value="${b.id}">` : ''}${field('Bill name', `<input name="name" maxlength="120" placeholder="e.g. Meralco, PLDT, Rent" value="${esc(b.name || '')}" required>`)}<div class="two">${field('Amount', money('amount', b.amount ?? ''))}${field('Due date', `<input name="due" type="date" value="${b.due || today()}" required>`)}</div><p class="note">Marking a bill as paid records it as a <b>Bills</b> expense automatically.</p><button class="btn lg">${b.id ? 'Save changes' : 'Add bill'}</button>${b.id ? `<button type="button" class="btn text-danger" data-act="delbill" data-id="${b.id}">${I.trash}Delete bill</button>` : ''}</form>`;
V.addbill = async () => ({ title: 'Add a bill', back: 1, narrow: 1, html: billForm({}) });
V.editbill = async () => ({ title: 'Edit bill', back: 1, narrow: 1, html: billForm(await api(`bills/${S.id}`)) });
V.addgoal = async () => ({ title: 'New savings goal', back: 1, narrow: 1, html: `<form data-f="addgoal" class="stack"><div class="card">${empty('🎯', 'What are you saving for?', 'Everyone in the family can contribute to a goal.')}</div>${field('Goal name', '<input name="name" maxlength="120" placeholder="e.g. Emergency fund" required>')}${field('Target amount', money('target', '', 'min="1"'))}<button class="btn lg">Create goal</button></form>` });

V.members = async () => {
  await loadMe();
  const f = S.me.family;
  return { title: esc(f.name), sub: 'Your family', nav: 1, right: meBtn(), html: `<div class="card fam-hero"><span class="avs">${f.members.slice(0, 5).map(m => av(m.name)).join('')}</span><span class="grow"><b>${f.members.length} member${f.members.length === 1 ? '' : 's'}</b><small>${f.plan === 'premium' ? 'Premium' : 'Free'} plan · up to ${f.limit} members</small></span>${f.plan === 'free' && owner() ? `<button class="btn sm soft" data-go="premium">${I.crown}Upgrade</button>` : ''}</div>
  ${owner() ? inviteForm() : '<p class="note">Only the family owner can invite or remove members.</p>'}<h3 class="sec">Members</h3>${memberList()}${inviteList()}` };
};

V.reports = async () => {
  const r = await api('reports'), m = r.month, y = r.year, ms = Object.entries(r.months);
  const mx = Math.max(1, ...ms.map(([, v]) => Math.abs(v.income - v.expense)));
  return { title: 'Reports', sub: `${new Date().getFullYear()} overview`, nav: 1, right: meBtn(), html: `<div class="grid"><div class="col">
  <div class="card">${cardH('This month')}<div class="stats">${stat('Income', peso(m.income), 'tx-in')}${stat('Spending', peso(m.expense), 'tx-out')}${stat('Net', peso(m.balance), m.balance < 0 ? 'tx-out' : '')}</div></div>
  <div class="card">${cardH('Where the money went')}${catBreakdown(r.category_totals, m.expense)}</div></div><div class="col">
  <div class="card">${cardH('This year')}<div class="stats">${stat('Income', kpeso(y.income), 'tx-in')}${stat('Spending', kpeso(y.expense), 'tx-out')}</div><h3 class="sec" style="margin:18px 0 8px">Net by month</h3>${ms.map(([k, v]) => { const n = v.income - v.expense; return `<div class="nrow"><span>${new Date(2000, k - 1).toLocaleDateString('en-PH', { month: 'short' })}</span><span class="nbar"><i class="${n < 0 ? 'neg' : ''}" style="width:${Math.abs(n) / mx * 50}%"></i></span><b class="${n < 0 ? 'tx-out' : ''}">${kpeso(n)}</b></div>`; }).join('')}</div>
  <div class="card goal"><span class="ring" style="--p:${Math.min(100, r.savings)}"><span>${r.savings}%</span></span><span class="grow"><b>Savings progress</b><small>Across all family goals</small></span></div>
  ${r.advanced ? advanced(r.advanced, r.category_totals) : lock('Unlock advanced analytics', 'Spending pace, who spent what, and month-to-month changes')}
  ${isPrem() ? `<button class="btn ghost" data-act="export">${I.dl}Export all transactions (CSV)</button>` : lock('Export to CSV with Premium', 'Download your full transaction history')}</div></div>` };
};
const advanced = (a, now) => {
  const people = Object.entries(a.by_member).sort((x, y) => y[1] - x[1]), top = Math.max(1, ...people.map(p => p[1]));
  const cats = [...new Set([...Object.keys(now), ...Object.keys(a.last_month)])].sort((x, y) => (now[y] || 0) - (now[x] || 0));
  const change = c => { const n = now[c] || 0, p = a.last_month[c] || 0; if (!p) return '<span class="badge">New</span>'; const pct = Math.round((n - p) / p * 100); return `<span class="small ${pct > 0 ? 'tx-out' : 'tx-in'}">${pct > 0 ? '▲' : pct < 0 ? '▼' : ''} ${Math.abs(pct)}%</span>`; };
  return `<div class="card">${cardH('Spending pace', '<span class="badge gold">Premium</span>')}<div class="stats">${stat('Daily average', peso(Math.round(a.daily_average)))}${stat('Projected this month', peso(Math.round(a.projected)), a.last_month_total && a.projected > a.last_month_total ? 'tx-out' : '')}${stat('Last month', peso(a.last_month_total))}</div></div>
  <div class="card">${cardH('Who spent what this month')}${people.length ? `<div class="stack">${people.map(([n, v]) => `<div class="brow">${av(n)}<span class="grow"><span class="between"><b>${esc(n)}</b><span class="amt">${peso(v)}</span></span>${bar(v / top * 100)}</span></div>`).join('')}</div>` : '<p class="note">No expenses recorded this month yet.</p>'}</div>
  <div class="card">${cardH('Compared with last month')}${cats.length ? `<div class="list">${cats.map(c => `<div class="item">${catIco(c)}<span class="grow"><b>${esc(c)}</b><small>${peso(now[c] || 0)} vs ${peso(a.last_month[c] || 0)}</small></span>${change(c)}</div>`).join('')}</div>` : '<p class="note">Nothing to compare yet.</p>'}</div>`;
};

const menu = (go, icon, title, sub = '') => `<button class="item" data-go="${go}"><span class="ico">${icon}</span><span class="grow"><b>${title}</b>${sub ? `<small>${sub}</small>` : ''}</span>${I.next}</button>`;
V.profile = async () => {
  const f = S.me.family;
  return { title: 'Profile', back: 1, narrow: 1, html: `<div class="card profile-head"><label class="avatar-edit" title="Change photo">${av(S.me.name, S.avatar, 'lg')}<span class="cam">${I.camera}</span><input type="file" accept="image/jpeg,image/png,image/webp" class="vh" data-avatar aria-label="Change profile photo"></label><span class="grow"><b style="font-size:18px">${esc(S.me.name)}</b><small>${esc(S.me.email)}</small>${f ? `<small>${esc(f.name)} · ${f.owner ? 'Owner' : esc(f.role)}</small>` : ''}${S.avatar ? '<button class="link" style="align-self:flex-start;margin-top:4px" data-act="rmavatar">Remove photo</button>' : ''}</span></div>
  <form data-f="profile" class="card stack"><h3>Personal details</h3>${field('Full name', `<input name="name" maxlength="120" value="${esc(S.me.name)}" required>`)}${field('Email', `<input name="email" type="email" value="${esc(S.me.email)}" required>`, 'Changing your email requires your current password below.')}
  <details class="pwbox"><summary>Password &amp; security</summary><div class="stack">${field('Current password', pw('current_password', 'Your current password', 'autocomplete="current-password"'))}${field('New password', pw('new_password', 'Leave blank to keep it', 'minlength="8" autocomplete="new-password"'))}</div></details>
  <button class="btn">Save changes</button></form>
  <div class="card list">${f ? menu('premium', I.crown, 'Gastos Premium', f.plan === 'premium' ? 'Your family is on Premium' : `Free plan · up to ${f.limit} members`) : ''}${menu('wallets', I.wallet, 'Wallets', 'Cash & cards')}${menu('reports', I.chart, 'Reports & export')}${menu('partners', I.brief, 'Partner services')}</div>
  <button class="btn ghost" data-act="signout">${I.logout}Sign out</button>` };
};

const FEATS = ['Up to 10 family members', 'Unlimited budgets', 'Expense approval: you approve members\' expenses', 'Bill reminders on your Home screen', 'Advanced analytics in Reports', 'Receipt scanning that reads the total', 'CSV export of all transactions'];
V.premium = async () => {
  const f = S.me.family, isPrem = f.plan === 'premium', free = ['Up to 4 family members', '3 budgets', 'Bills & savings goals', 'Transactions & reports'];
  const card = (name, price, per, feats, cur, cls) => `<div class="tier ${cls} ${cur ? 'current' : ''}">${cur ? `<span class="badge ok">${I.check}Current plan</span>` : cls === 'prem' ? '<span class="badge gold">Recommended</span>' : ''}<h3>${name}</h3><p class="tprice"><b>${price}</b> <span>${per}</span></p><ul class="feat">${feats.map(x => `<li>${I.check}${x}</li>`).join('')}</ul></div>`;
  const cmp = [['Family members', '4', '10'], ['Budgets', '3', 'Unlimited'], ['Bills & savings goals', '✓', '✓'], ['Expense approval', '—', '✓'], ['Bill reminders', '—', '✓'], ['Advanced analytics', '—', '✓'], ['Receipt scanning', '—', '✓'], ['Data export', '—', '✓']];
  return { title: 'Membership', back: 1, narrow: 1, html: `<section class="prem-hero"><span class="crown">${I.crown}</span><h2>More room for the whole family</h2><p class="mu">You're on the <b>${isPrem ? 'Premium' : 'Free'}</b> plan${isPrem ? '' : '. Upgrade for bigger households.'}</p></section>
  <div class="tiers">${card('Free', '₱0', 'forever', free, !isPrem, 'free')}${card('Premium', '₱99', 'per month', FEATS, isPrem, 'prem')}</div>
  ${isPrem ? `<div class="card goal"><span class="cat" style="--h:150">✅</span><span class="grow"><b>You're on Premium</b><small>All Premium features are unlocked for ${esc(f.name)}.</small></span></div>${owner() ? `<button class="btn ghost" data-act="downgrade">Switch back to Free</button>` : ''}` : `<div class="plans"><div class="plan"><small>Monthly</small><b>₱99</b><span>per month</span></div><div class="plan best"><span class="badge gold">Save 16%</span><small>Yearly</small><b>₱999</b><span>per year</span></div></div>${owner() ? `<button class="btn lg" data-act="upgrade">${I.crown}Upgrade to Premium</button>` : '<p class="note center">Ask your family owner to upgrade.</p>'}`}
  <div class="card"><h3>Free vs Premium</h3><table class="cmp"><tr><th></th><th>Free</th><th class="pc">Premium</th></tr>${cmp.map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td><td class="pc">${r[2]}</td></tr>`).join('')}</table></div>` };
};
V.partners = async () => ({ title: 'Partner services', back: 1, narrow: 1, html: `<p class="note">Optional services from participating partners. Gastos never shares your data without your permission.</p><div class="card list">${[['🏦', 'Banks & digital wallets', 'Access participating financial services'], ['🛡️', 'Insurance', 'Explore participating insurance providers'], ['🛒', 'Utilities & groceries', 'Household service offers and referrals'], ['🎓', 'Education', 'Participating school and tuition services']].map((a, i) => `<div class="item"><span class="cat" style="--h:${i * 80 + 20}">${a[0]}</span><span class="grow"><b>${a[1]}</b><small>${a[2]}</small></span></div>`).join('')}</div>` });

/* ---------- Rendering & navigation ---------- */
const TABS = [['home', 'Home', 'home'], ['tx', 'Activity', 'list'], ['plan', 'Plan', 'plan'], ['members', 'Family', 'users']];
const nav = () => {
  const a = t => `<button data-tab="${t[0]}" class="tab ${S.view === t[0] ? 'on' : ''}" ${S.view === t[0] ? 'aria-current="page"' : ''}>${I[t[2]]}<span>${t[1]}</span></button>`;
  return `<nav class="nav" aria-label="Main">${a(TABS[0])}${a(TABS[1])}<button class="fab" data-go="addtx" data-k="expense" aria-label="Add transaction">${I.plus}</button>${TABS.slice(2).map(a).join('')}</nav>`;
};
async function render() {
  const view = S.view, pg = document.getElementById('progress'), slow = setTimeout(() => pg.className = 'on', 120);
  try {
    const v = await V[view]();
    if (view !== S.view) return;
    const back = v.back || (!v.nav && S.stack.length);
    app.className = v.bare ? 'bare' : v.nav ? 'withnav' : '';
    app.innerHTML = v.bare ? `<main class="bare">${v.html}</main>` : (v.nav ? nav() : '') +
      `<div class="page ${v.narrow ? 'narrow' : ''}"><header class="top">${back ? `<button class="iconbtn" data-back aria-label="Back">${I.back}</button>` : ''}<div class="ttl">${v.sub ? `<small>${v.sub}</small>` : ''}<h1>${v.title}</h1></div>${v.right || ''}</header><main>${v.html}</main></div>`;
    const t = document.createElement('div'); t.innerHTML = v.title || '';
    document.title = (t.textContent ? t.textContent + ' · ' : '') + 'Gastos';
    scrollTo(0, 0);
    app.querySelector('[autofocus]')?.focus();
  } catch (e) { toast(e.message, 1); if (!localStorage.t && view !== 'welcome') { S.view = 'welcome'; S.stack = []; render(); } }
  finally { clearTimeout(slow); pg.className = ''; }
}
// Every go() adds a browser history entry, so the phone's Back button walks back through screens.
const go = v => { closeSheet(); S.stack.push(S.view); S.view = v; history.pushState(null, ''); render(); };
const tab = v => { closeSheet(); S.stack = []; S.view = v; render(); };
const back = () => { closeSheet(); if (S.stack.length) return history.back(); S.view = S.me ? (S.me.family ? 'home' : 'family') : 'welcome'; render(); };
addEventListener('popstate', () => {
  closeSheet();
  if (S.stack.length) S.view = S.stack.pop();
  else if (S.me?.family && S.view !== 'home') S.view = 'home';
  else return history.back(); // an entry left over from before tab() reset the stack: keep going
  render();
});
async function loadMe() { const [me, p] = await Promise.all([api('me'), api('profile')]); S.me = me; S.avatar = p.avatar_data; }
async function enter() { await loadMe(); S.stack = []; S.view = S.inviteInfo ? 'join' : S.me.family ? 'home' : 'family'; render(); }

async function copy(text) { try { await navigator.clipboard.writeText(text); toast('Link copied'); } catch { toast('Copy failed: select the link and copy it manually', 1); } }
const showLink = (link, email) => sheet(`<h3>Share the invite link</h3><p class="mu">Email delivery isn't set up, so send this link to <b>${esc(email)}</b> yourself (Messenger, Viber or SMS work great). It expires in 7 days.</p><input id="lnk" value="${esc(link)}" readonly onclick="this.select()"><div class="actions">${navigator.share ? `<button class="btn ghost" data-act="sharelink">${I.share}Share</button>` : ''}<button class="btn" data-act="copyfield">${I.copy}Copy link</button></div>`);
async function pickAvatar(file) {
  const img = await createImageBitmap(file), n = Math.min(img.width, img.height), c = document.createElement('canvas');
  c.width = c.height = Math.min(320, n);
  c.getContext('2d').drawImage(img, (img.width - n) / 2, (img.height - n) / 2, n, n, 0, 0, c.width, c.height);
  await api('profile', 'PUT', { avatar_data: c.toDataURL('image/jpeg', .85) }); await loadMe(); toast('Photo updated'); render();
}

/* ---------- Receipt scanning (Premium) ---------- */
const OCR_SRC = 'https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js';
const loadOcr = () => window.Tesseract ? Promise.resolve() : new Promise((ok, no) => document.head.append(Object.assign(document.createElement('script'), { src: OCR_SRC, onload: ok, onerror: no })));
// The receipt's total: the biggest peso amount on a "total"/"amount due" line, else the biggest amount anywhere.
const receiptTotal = text => {
  const amounts = l => (l.match(/\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2}/g) || []).map(n => +n.replace(/,/g, ''));
  const lines = text.split('\n'), keyed = lines.filter(l => /total|amount due|amt due/i.test(l) && !/sub ?total|vatable|vat amount|change|tender/i.test(l)).flatMap(amounts);
  const all = keyed.length ? keyed : lines.flatMap(amounts);
  return all.length ? Math.max(...all) : null;
};
function setReceipt(form, url) {
  if (!form.receipt_data) form.append(Object.assign(document.createElement('input'), { type: 'hidden', name: 'receipt_data' }));
  form.receipt_data.value = url;
  document.getElementById('rcpt').innerHTML = receiptBlock(url);
}
async function scanReceipt(file, form) {
  const img = await createImageBitmap(file), k = Math.min(1, 1200 / Math.max(img.width, img.height)), c = document.createElement('canvas');
  c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
  c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
  setReceipt(form, c.toDataURL('image/jpeg', .8));
  toast('Reading the receipt…');
  let total = null;
  try { await loadOcr(); total = receiptTotal((await Tesseract.recognize(c, 'eng')).data.text); }
  catch { return toast('Receipt attached. Reading it needs an internet connection, so enter the amount yourself.', 1); }
  if (!form.isConnected) return;
  if (!total) return toast('Receipt attached, but the total was unclear. Enter the amount yourself.', 1);
  form.amount.value = total; toast(`Found the total: ${peso(total)}. Check it before saving.`);
}

/* ---------- Form submissions ---------- */
const F = {
  async signup(d) { if (d.password !== d.password2) throw new Error('Passwords do not match'); delete d.password2; localStorage.t = (await api('signup', 'POST', d)).token; S.invite = S.inviteInfo = null; await enter(); },
  async signin(d) { localStorage.t = (await api('signin', 'POST', d)).token; await enter(); },
  async forgot(d) { await api('password-reset/request', 'POST', d); S.resetSent = d.email; render(); },
  async reset(d) { if (d.password !== d.password2) throw new Error('Passwords do not match'); await api('password-reset/complete', 'POST', { token: S.reset, password: d.password }); S.reset = null; toast('Password updated. Please sign in.'); S.stack = []; S.view = 'signin'; render(); },
  async family(d) { await api('family', 'POST', d); await loadMe(); S.stack = []; S.view = 'invite'; render(); },
  async invite(d, f) {
    const r = await api('invite', 'POST', d); f.reset(); await loadMe(); await render();
    r.invitation.delivery === 'sent' ? toast(`Invitation emailed to ${d.email}`) : showLink(r.invitation.link, d.email);
  },
  async savetx({ id, ...d }) { const r = await api(id ? `transactions/${id}` : 'transactions', id ? 'PUT' : 'POST', d); toast(r.status === 'pending' ? 'Sent to the family owner for approval' : id ? 'Changes saved' : 'Transaction added'); back(); },
  async upgrade(d) { await api('upgrade', 'POST', d); closeSheet(); await loadMe(); toast('Welcome to Premium! 🎉'); render(); },
  async savebill({ id, ...d }) { await api(id ? `bills/${id}` : 'bills', id ? 'PUT' : 'POST', d); toast(id ? 'Bill updated' : 'Bill added'); S.plan = 'bills'; back(); },
  async addgoal(d) { await api('goals', 'POST', d); toast('Goal created'); S.plan = 'goals'; back(); },
  async savewallet({ id, ...d }) { await api(id ? `wallets/${id}` : 'wallets', id ? 'PUT' : 'POST', d); toast(id ? 'Wallet updated' : 'Wallet added'); back(); },
  async walletadjust(d) { await api(`wallets/${d.id}/adjust`, 'POST', { amount: d.amount }); closeSheet(); toast('Balance updated'); render(); },
  async savebudget({ id, ...d }) { await api(id ? `budgets/${id}` : 'budgets', id ? 'PUT' : 'POST', d); closeSheet(); toast('Budget saved'); render(); },
  async fund(d) { const g = S.goals.find(x => x.id == d.id); await api(`goals/${d.id}/add`, 'POST', { amount: d.amount }); closeSheet(); toast(`Added ${peso(d.amount)} to ${g?.name || 'goal'}`); render(); },
  async profile(d) {
    const b = { name: d.name, email: d.email };
    if (d.current_password) b.current_password = d.current_password;
    if (d.new_password) b.new_password = d.new_password;
    const r = await api('profile', 'PUT', b);
    if (r.token) localStorage.t = r.token;
    await loadMe(); toast('Profile updated'); render();
  },
};

/* ---------- Click actions ---------- */
const A = {
  finish: () => tab('home'),
  toSignin() { S.resetSent = null; S.stack = []; S.view = 'signin'; render(); },
  signout() { localStorage.removeItem('t'); S.me = S.avatar = null; tab('welcome'); },
  peek(_, el) { const i = el.previousElementSibling, show = i.type === 'password'; i.type = show ? 'text' : 'password'; el.textContent = show ? 'Hide' : 'Show'; el.setAttribute('aria-label', show ? 'Hide password' : 'Show password'); },
  async accept() { await api(`invitations/${encodeURIComponent(S.invite)}/accept`, 'POST'); toast(`Welcome to ${S.inviteInfo.family}!`); S.invite = S.inviteInfo = null; await enter(); },
  async pay(id) {
    const b = S.bills.find(x => x.id == id);
    if (!await ask(`Mark ${esc(b?.name || 'bill')} as paid?`, `This records ${peso(b?.amount)} as a Bills expense dated today.`, 'Mark as paid')) return;
    await api(`bills/${id}/pay`, 'POST'); toast('Bill marked as paid'); render();
  },
  async delbill(id) { if (!await ask('Delete this bill?', 'It will be removed from your family\'s reminders.', 'Delete', 1)) return; await api(`bills/${id}`, 'DELETE'); toast('Bill deleted'); back(); },
  async deltx(id) { if (!await ask('Delete this transaction?', 'This can\'t be undone and will update your family\'s totals.', 'Delete', 1)) return; await api(`transactions/${id}`, 'DELETE'); toast('Transaction deleted'); back(); },
  budget(id) {
    const x = S.budgets.find(b => b.id == id) || {}, cats = [...CATS.expense];
    if (x.category && !cats.includes(x.category)) cats.push(x.category);
    sheet(`<h3>${x.id ? 'Edit budget' : 'Set a monthly budget'}</h3><form data-f="savebudget" class="stack">${x.id ? `<input type="hidden" name="id" value="${x.id}">` : ''}${field('Category', `<select name="category">${cats.map(c => `<option value="${esc(c)}" ${c === x.category ? 'selected' : ''}>${EMO[c] || '🏷️'} ${esc(c)}</option>`).join('')}</select>`)}${field('Monthly limit', money('monthly_limit', x.monthly_limit ?? ''))}<div class="actions"><button type="button" class="btn ghost" data-close>Cancel</button><button class="btn">Save budget</button></div>${x.id ? `<button type="button" class="btn text-danger" data-act="delbudget" data-id="${x.id}">${I.trash}Remove budget</button>` : ''}</form>`);
  },
  walletadjust(id) {
    const w = S.wd, credit = isCredit(w), cur = Math.max(0, credit ? w.owed : w.balance);
    sheet(`<h3>${credit ? 'Update amount owed' : 'Adjust balance'}</h3><p class="mu">${credit ? `Gastos shows ${peso(w.owed)} owed on ${esc(w.name)}. Enter what your statement says now.` : `Gastos shows ${peso(w.balance)} in ${esc(w.name)}. Enter what you actually have now.`} This corrects the balance without adding a transaction.</p><form data-f="walletadjust" class="stack"><input type="hidden" name="id" value="${id}"><label class="amount"><span>₱</span><input name="amount" type="number" inputmode="decimal" step="0.01" min="0" placeholder="0" value="${cur}" aria-label="New amount" required></label><div class="actions"><button type="button" class="btn ghost" data-close>Cancel</button><button class="btn">Save</button></div></form>`);
  },
  async delwallet(id) { if (!await ask('Delete this wallet?', 'Its transactions stay in your history, but they will no longer be linked to a wallet.', 'Delete', 1)) return; await api(`wallets/${id}`, 'DELETE'); toast('Wallet deleted'); back(); },
  async delbudget(id) { if (!await ask('Remove this budget?', 'Your transactions stay; only the monthly limit is removed.', 'Remove', 1)) return; await api(`budgets/${id}`, 'DELETE'); toast('Budget removed'); render(); },
  fund(id) {
    const g = S.goals.find(x => x.id == id);
    sheet(`<h3>Add to ${esc(g.name)}</h3><p class="mu">${peso(g.saved)} saved of ${peso(g.target)}</p><form data-f="fund" class="stack"><input type="hidden" name="id" value="${id}"><label class="amount"><span>₱</span><input name="amount" type="number" inputmode="decimal" step="0.01" min="0.01" placeholder="0" aria-label="Amount" required></label><div class="chips">${[100, 500, 1000, 5000].map(v => `<button type="button" class="chip" data-act="quick" data-id="${v}">+${peso(v)}</button>`).join('')}</div><div class="actions"><button type="button" class="btn ghost" data-close>Cancel</button><button class="btn">Add savings</button></div></form>`);
  },
  quick(v, el) { const i = el.closest('form').amount; i.value = (+i.value || 0) + +v; },
  async removemember(id) { const m = S.me.family.members.find(x => x.id == id); if (!await ask(`Remove ${esc(m.name)}?`, 'They will lose access to your family. Their past transactions stay in your history.', 'Remove', 1)) return; await api(`family/members/${id}`, 'DELETE'); await loadMe(); toast(`${m.name} was removed`); render(); },
  async copylink(id) { await copy(S.me.family.invites.find(i => i.id == id).link); },
  copyfield() { copy(document.getElementById('lnk').value); },
  async sharelink() { try { await navigator.share({ title: 'Join our family on Gastos', url: document.getElementById('lnk').value }); } catch { } },
  async resend(id) { const i = S.me.family.invites.find(x => x.id == id), r = await api(`invitations/${id}/resend`, 'POST'); await loadMe(); await render(); r.delivery === 'sent' ? toast('Invitation re-sent') : showLink(r.link, i.email); },
  async revoke(id) { if (!await ask('Cancel this invitation?', 'The link will stop working.', 'Cancel invite', 1)) return; await api(`invitations/${id}/revoke`, 'POST'); await loadMe(); toast('Invitation cancelled'); render(); },
  async rmavatar() { await api('profile', 'PUT', { avatar_data: '' }); await loadMe(); toast('Photo removed'); render(); },
  upgrade() {
    sheet(`<h3>Upgrade to Premium</h3><form data-f="upgrade" class="stack"><fieldset class="field"><legend>Billing</legend><div class="seg"><label><input type="radio" name="period" value="monthly" checked><span>₱99 / month</span></label><label><input type="radio" name="period" value="annual"><span>₱999 / year</span></label></div></fieldset><p class="note">Demo checkout: no real payment is made. Premium unlocks right away for everyone in ${esc(S.me.family.name)}.</p><div class="actions"><button type="button" class="btn ghost" data-close>Cancel</button><button class="btn">${I.crown}Confirm upgrade</button></div></form>`);
  },
  async downgrade() { if (!await ask('Switch back to Free?', 'Premium features lock again. Your data stays, including receipts and extra budgets.', 'Switch to Free', 1)) return; await api('downgrade', 'POST'); await loadMe(); toast('Your family is now on the Free plan'); render(); },
  async approve(id) { await api(`transactions/${id}/approve`, 'POST'); toast('Expense approved'); render(); },
  async reject(id) { if (!await ask('Reject this expense?', 'It won\'t count in your family\'s totals. The member can edit it and send it again.', 'Reject', 1)) return; await api(`transactions/${id}/reject`, 'POST'); toast('Expense rejected'); render(); },
  async receipt(id) { const t = await api(`transactions/${id}`); sheet(`<h3>Receipt</h3><p class="mu">${esc(t.note || t.category)} · ${peso(t.amount)}</p><img class="rimg full" src="${esc(t.receipt_data)}" alt="Receipt photo"><button class="btn ghost" data-close>Close</button>`); },
  rmreceipt(_, el) { setReceipt(el.closest('form'), ''); },
  async export() { const b = await api('export'), l = document.createElement('a'); l.href = URL.createObjectURL(b); l.download = `gastos-${today()}.csv`; l.click(); toast('Export downloaded'); },
};

/* ---------- Event wiring ---------- */
document.addEventListener('click', async e => {
  const el = e.target.closest('[data-go],[data-back],[data-act],[data-tab],[data-filter]'); if (!el) return;
  try {
    if (el.dataset.k) S.k = el.dataset.k;
    if (el.dataset.wk) S.wk = el.dataset.wk;
    if (el.dataset.wid) S.wid = el.dataset.wid;
    if (el.dataset.go === 'addtx') S.w = el.dataset.w || null;
    if (el.dataset.plan) S.plan = el.dataset.plan;
    if (el.dataset.filter) { S.filter = el.dataset.filter; document.querySelectorAll('[data-filter]').forEach(b => b.classList.toggle('on', b === el)); document.getElementById('txlist').innerHTML = txList(); }
    else if (el.dataset.go) { if (el.dataset.id) S.id = el.dataset.id; go(el.dataset.go); }
    else if (el.dataset.tab) tab(el.dataset.tab);
    else if (el.hasAttribute('data-back')) back();
    else await A[el.dataset.act](el.dataset.id, el);
  } catch (x) { toast(x.message, 1); }
});
document.addEventListener('submit', async e => {
  e.preventDefault();
  const f = e.target, b = e.submitter || f.querySelector('button:not([type=button])');
  if (b) { b.disabled = true; b.classList.add('busy'); }
  try { await F[f.dataset.f](Object.fromEntries(new FormData(f)), f); } catch (x) { toast(x.message, 1); }
  finally { if (b) { b.disabled = false; b.classList.remove('busy'); } }
});
document.addEventListener('change', e => {
  const t = e.target;
  if (t.matches('[data-member-role]')) {
    const oldRole = t.dataset.currentRole, member = S.me?.family?.members.find(m => String(m.id) === t.dataset.id);
    t.disabled = true;
    api(`family/members/${encodeURIComponent(t.dataset.id)}/role`, 'PUT', { role: t.value })
      .then(async () => { await loadMe(); toast(`${member?.name || 'Member'} is now ${t.value}`); render(); })
      .catch(x => { t.value = oldRole; toast(x.message, 1); })
      .finally(() => { t.disabled = false; });
    return;
  }
  if (t.name === 'kind' && t.form?.dataset.f === 'savetx') document.getElementById('catchips').innerHTML = catChips(t.value);
  if (t.name === 'card_type' && t.form?.dataset.f === 'savewallet') { t.form.querySelector('.only-credit').hidden = t.value !== 'credit'; document.getElementById('ballbl').textContent = t.value === 'credit' ? 'Amount owed now' : 'Current balance'; }
  if (t.matches('[data-avatar]') && t.files[0]) pickAvatar(t.files[0]).catch(x => toast(x.message, 1));
  if (t.matches('[data-receipt]') && t.files[0]) scanReceipt(t.files[0], t.form).catch(x => toast(x.message, 1));
});
document.addEventListener('input', e => { if (e.target.matches('[data-search]')) { S.q = e.target.value; document.getElementById('txlist').innerHTML = txList(); } });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSheet(); });

(async () => {
  const q = new URLSearchParams(location.search);
  S.invite = q.get('invite'); S.reset = q.get('reset');
  if (S.invite || S.reset) history.replaceState(null, '', location.pathname);
  if (S.invite) { try { S.inviteInfo = await api(`invitations/${encodeURIComponent(S.invite)}`); } catch (e) { S.invite = null; toast(e.message, 1); } }
  if (S.reset) { S.view = 'reset'; return render(); }
  if (localStorage.t) { try { await enter(); return; } catch (e) { } }
  if (S.inviteInfo) S.view = 'join';
  render();
})();

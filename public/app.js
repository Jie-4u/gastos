const app = document.getElementById('app');
const S = { view: 'welcome', me: null, stack: [], k: 'expense' };
const peso = n => '₱' + Number(n).toLocaleString('en-PH', { maximumFractionDigits: 2 });
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const today = () => new Date().toISOString().slice(0, 10);
function toast(m) { const t = document.getElementById('toast'); t.textContent = m; t.style.display = 'block'; setTimeout(() => t.style.display = 'none', 2800); }
async function api(p, m = 'GET', b) {
  const r = await fetch('/api/' + p, { method: m, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + (localStorage.t || '') }, body: b ? JSON.stringify(b) : undefined });
  if (p === 'export' && r.ok) return r.blob();
  const d = await r.json().catch(() => ({}));
  if (r.status === 401 && p !== 'signin') { localStorage.removeItem('t'); S.view = 'welcome'; }
  if (!r.ok) throw new Error(d.error || 'Something went wrong');
  return d;
}
const lbl = d => { const t = today(), y = new Date(Date.now() - 864e5).toISOString().slice(0, 10); return d === t ? 'Today' : d === y ? 'Yesterday' : d; };
const bar = p => `<div class="bar"><i style="width:${Math.min(100, p)}%"></i></div>`;
const row = (a, b) => `<div class="row"><span>${a}</span><span>${b}</span></div>`;

const V = {};
V.welcome = async () => ({ bare: 1, html: `<h1 class="logo">GASTOS</h1><button class="btn" data-go="signup">Create Account</button><button class="btn alt" data-go="signin">Sign In</button>` });
V.signup = async () => ({ title: 'Create Account', html: `<form data-f="signup"><input name="name" placeholder="Enter your name" required><input name="email" type="email" placeholder="you@example.com" required><input name="password" type="password" placeholder="Create a password" minlength="6" required><input name="password2" type="password" placeholder="Repeat your password" required><a class="lnk" data-go="signin">Already have an account? Sign In</a><button class="btn">Create Account</button></form>` });
V.signin = async () => ({ title: 'Welcome Back', html: `<form data-f="signin"><label>Email</label><input name="email" type="email" placeholder="you@example.com" required><label>Password</label><input name="password" type="password" placeholder="Enter your password" required><a class="lnk" onclick="toast('Password reset is not available yet')">Forgot password?</a><a class="lnk" data-go="signup">New to Gastos? Create Account</a><button class="btn">Sign In</button></form>` });
V.family = async () => ({ title: 'Set Up Your Family', html: `<form data-f="family"><label>Family Name</label><input name="name" placeholder="e.g. Furio Family" required><label>Your Role</label><select name="role"><option>Parent</option><option>Member</option></select><p class="mu">Create your family space to start tracking money together.</p><button class="btn">Continue</button></form>` });
V.invite = async () => {
  const f = S.me.family;
  return { title: 'Add Family Members', back: 1, html: `<form data-f="invite"><input name="email" type="email" placeholder="family@example.com" required><label>Member Email</label><button class="btn alt">Send Invite</button></form><p class="mu">Invite up to ${f.limit} members on the ${f.plan === 'free' ? 'Free' : 'Premium'} Plan.</p><div class="card"><b>Family Members</b>${f.members.map(m => `<span class="sm">${esc(m.name)} • ${m.owner ? 'Owner' : esc(m.role)}</span>`).join('')}${f.invites.map(e => `<span class="sm">${esc(e)} • Invited</span>`).join('')}</div><button class="btn" data-act="finish">Finish Setup</button>` };
};
V.home = async () => {
  const d = await api('dashboard'), cats = Object.entries(d.cats).sort((a, b) => b[1] - a[1]);
  return { title: 'Gastos', nav: 1, right: '<button class="ico" data-go="profile">👤</button>', html: `<p class="fam">${esc(S.me.family.name)}</p>
  <div class="card"><b>This Month</b>${row('Income', `<span class="inc">${peso(d.income)}</span>`)}${row('Expenses', `<span class="exp">${peso(d.expense)}</span>`)}${row('Balance', peso(d.balance))}</div>
  <div class="card"><b>Quick Actions</b><div class="chips"><a data-go="addtx" data-k="income">+ Add Income</a><a data-go="addtx" data-k="expense">– Add Expense</a><a data-tab="bills">Bill Reminder</a><a data-tab="savings">Savings Goal</a></div></div>
  <div class="card"><b>Monthly Summary</b><span class="sm">${cats.length ? cats.map(([k, v]) => `${esc(k)} ${v}%`).join(' &nbsp; ') : 'No expenses yet this month.'}</span></div>
  <button class="btn alt" data-go="reports">View Full Dashboard</button><button class="btn alt" data-go="partners">Partner Services</button>` };
};
V.tx = async () => {
  const r = await api('transactions');
  return { title: 'Transactions', nav: 1, html: (r.map(t => `<div class="card"><b>${lbl(t.date)} • ${esc(t.note || t.category)}</b><span class="sm">${t.kind === 'income' ? 'Income' : esc(t.category === 'Bills' ? 'Bill' : 'Expense')} &nbsp; <span class="${t.kind === 'income' ? 'inc' : 'exp'}">${t.kind === 'income' ? '+' : '−'}${peso(t.amount)}</span></span></div>`).join('') || '<p class="mu">No transactions yet.</p>') + `<button class="btn" data-go="addtx" data-k="expense">+ Add Transaction</button>` };
};
V.addtx = async () => ({ title: S.k === 'income' ? 'Add Income' : 'Add Expense', back: 1, html: `<form data-f="addtx"><label>Type</label><select name="kind"><option value="expense" ${S.k !== 'income' ? 'selected' : ''}>Expense</option><option value="income" ${S.k === 'income' ? 'selected' : ''}>Income</option></select><label>Amount</label><input name="amount" type="number" step="0.01" min="0.01" placeholder="₱ 0.00" required><label>Category</label><select name="category"><option>Food</option><option>Bills</option><option>Tuition</option><option>Allowance</option><option>Salary</option><option>Other</option></select><label>Date</label><input name="date" type="date" value="${today()}"><label>Note</label><input name="note" placeholder="What was this for?"><button class="btn">Save</button></form>` });
V.bills = async () => {
  const b = await api('bills');
  return { title: 'Bills & Reminders', nav: 1, html: (b.map(x => `<div class="card"><div class="row"><b>${esc(x.name)}</b><button class="btn sm" data-act="pay" data-id="${x.id}">Mark paid</button></div><span class="sm">Due ${x.due} • ${peso(x.amount)}</span></div>`).join('') || '<p class="mu">No unpaid bills.</p>') + `<button class="btn" data-go="addbill">+ Add Bill</button>` };
};
V.addbill = async () => ({ title: 'Add Bill', back: 1, html: `<form data-f="addbill"><label>Name</label><input name="name" placeholder="e.g. Electricity" required><label>Amount</label><input name="amount" type="number" step="0.01" min="0.01" required><label>Due date</label><input name="due" type="date" value="${today()}"><button class="btn">Save Bill</button></form>` });
V.savings = async () => {
  const g = await api('goals');
  return { title: 'Savings Goals', nav: 1, html: (g.map(x => { const p = Math.round(x.saved * 100 / x.target); return `<div class="card"><div class="row"><b>${esc(x.name)}</b><button class="btn sm" data-act="fund" data-id="${x.id}">+ Add</button></div><span class="sm">${peso(x.saved)} / ${peso(x.target)}<br>${p}% complete</span>${bar(p)}</div>`; }).join('') || '<p class="mu">No goals yet.</p>') + `<button class="btn" data-go="addgoal">+ Create Goal</button>` };
};
V.addgoal = async () => ({ title: 'Create Goal', back: 1, html: `<form data-f="addgoal"><label>Goal name</label><input name="name" placeholder="e.g. Emergency Fund" required><label>Target amount</label><input name="target" type="number" step="0.01" min="1" required><button class="btn">Create Goal</button></form>` });
V.members = async () => {
  const f = S.me.family;
  return { title: 'Family Members', nav: 1, html: `<p class="mu">${f.plan === 'free' ? 'Free' : 'Premium'} Plan: up to ${f.limit} members</p>${f.members.map(m => `<div class="card"><b>${esc(m.name)}</b><span class="sm">${m.owner ? 'Owner • Full access' : 'Member • Can add expenses'}</span></div>`).join('')}${f.invites.map(e => `<div class="card"><b>${esc(e)}</b><span class="sm">Invite pending</span></div>`).join('')}<button class="btn" data-go="invite">+ Add Member</button>` };
};
V.premium = async () => ({ title: 'Gastos Premium', back: 1, html: `<h2>Family Premium</h2><p class="price">₱99 / month or ₱999 / year</p><p class="sm">Up to 10 members • Unlimited budgets • Expense approval • Bill reminders • Advanced analytics • Receipt scanning • Reports • Data export • Priority support</p>${S.me.family.plan === 'premium' ? '<div class="card"><b>✓ You are on Premium</b></div>' : '<button class="btn" data-act="upgrade">Upgrade to Premium</button><p class="mu">Demo mode: no payment is taken.</p>'}<button class="btn alt" data-go="addons">Optional Add-ons</button>` });
V.addons = async () => ({ title: 'Optional Add-ons', back: 1, html: [['Extra Family Members', 20], ['Advanced Financial Reports', 49], ['Extra Receipt Storage', 29], ['Premium Financial Challenges', 19]].map(a => `<div class="card"><b>${a[0]}</b><span class="sm">₱${a[1]} / month</span></div>`).join('') });
V.partners = async () => ({ title: 'Partner Services', back: 1, html: `<p class="mu">Optional services from participating partners.</p>` + [['Banks & Digital Wallets', 'Access participating financial services'], ['Insurance', 'Explore participating insurance providers'], ['Utilities & Groceries', 'Household service offers and referrals'], ['Education', 'Participating school and tuition services']].map(a => `<div class="card"><b>${a[0]}</b><span class="sm">${a[1]}</span></div>`).join('') });
V.reports = async () => {
  const r = await api('reports'), m = r.month, y = r.year;
  return { title: 'Financial Reports', back: 1, html: `<div class="card"><b>Monthly Report</b><span class="sm">Income ${peso(m.income)}<br>Spending ${peso(m.expense)}<br>By category: ${Object.entries(m.cats).map(([k, v]) => `${esc(k)} ${v}%`).join(', ') || '—'}<br>Savings progress ${r.savings}%</span></div>
  <div class="card"><b>Yearly Report</b><span class="sm">Annual income ${peso(y.income)}<br>Annual spending ${peso(y.expense)}<br>${Object.entries(r.months).map(([k, v]) => `Month ${k}: ${peso(v.income - v.expense)}`).join('<br>')}</span></div><button class="btn alt" data-act="export">Export Data (CSV)</button>` };
};
V.profile = async () => {
  const f = S.me.family;
  return { title: 'Profile', back: 1, html: `<div class="card"><b>${esc(S.me.name)}</b><span class="sm">${esc(S.me.email)}<br>${esc(f.name)} • ${f.owner ? 'Owner' : 'Member'}</span></div><div class="card"><b>Plan</b><span class="sm">${f.plan === 'free' ? 'Free' : 'Premium'} Plan • 1 family • Up to ${f.limit} members</span></div><button class="btn" data-go="premium">Upgrade to Premium</button><button class="btn alt" data-go="reports">Reports</button><button class="btn alt" data-act="signout">Sign Out</button>` };
};

const TABS = [['home', 'Home'], ['tx', 'Transactions'], ['bills', 'Bills'], ['savings', 'Savings'], ['members', 'Family']];
async function render() {
  try {
    const v = await V[S.view]();
    app.innerHTML = (v.bare ? '' : `<header>${v.back || (!v.nav && S.stack.length) ? '<button class="back" data-back>‹</button>' : ''}<h2>${v.title}</h2>${v.right || ''}</header>`) + `<main class="${v.bare ? 'bare' : ''}">${v.html}</main>` + (v.nav ? `<nav>${TABS.map(t => `<a data-tab="${t[0]}" class="${S.view === t[0] ? 'on' : ''}">${t[1]}</a>`).join('')}</nav>` : '');
    scrollTo(0, 0);
  } catch (e) { toast(e.message); if (!localStorage.t) { S.view = 'welcome'; render(); } }
}
const go = v => { S.stack.push(S.view); S.view = v; render(); };
const tab = v => { S.stack = []; S.view = v; render(); };
async function loadMe() { S.me = await api('me'); }
async function enter() { await loadMe(); S.stack = []; S.view = S.me.family ? 'home' : 'family'; render(); }

const F = {
  async signup(d) { if (d.password !== d.password2) throw new Error('Passwords do not match'); localStorage.t = (await api('signup', 'POST', d)).token; await enter(); },
  async signin(d) { localStorage.t = (await api('signin', 'POST', d)).token; await enter(); },
  async family(d) { await api('family', 'POST', d); await loadMe(); S.stack = []; S.view = 'invite'; render(); },
  async invite(d) { await api('invite', 'POST', d); toast('Invite sent'); await loadMe(); render(); },
  async addtx(d) { await api('transactions', 'POST', d); toast('Saved'); tab('tx'); },
  async addbill(d) { await api('bills', 'POST', d); tab('bills'); },
  async addgoal(d) { await api('goals', 'POST', d); tab('savings'); },
};
const A = {
  finish: () => tab('home'),
  signout() { localStorage.removeItem('t'); S.me = null; tab('welcome'); },
  async pay(id) { await api(`bills/${id}/pay`, 'POST'); toast('Marked as paid'); render(); },
  async fund(id) { const a = prompt('Amount to add (₱)'); if (!a) return; await api(`goals/${id}/add`, 'POST', { amount: a }); render(); },
  async upgrade() { await api('upgrade', 'POST'); await loadMe(); toast('You are now Premium'); render(); },
  async export() { const b = await api('export'), l = document.createElement('a'); l.href = URL.createObjectURL(b); l.download = 'gastos.csv'; l.click(); },
};
document.addEventListener('click', async e => {
  const el = e.target.closest('[data-go],[data-back],[data-act],[data-tab]'); if (!el) return;
  try {
    if (el.dataset.k) S.k = el.dataset.k;
    if (el.dataset.go) go(el.dataset.go);
    else if (el.dataset.tab) tab(el.dataset.tab);
    else if (el.hasAttribute('data-back')) { S.view = S.stack.pop() || 'home'; render(); }
    else await A[el.dataset.act](el.dataset.id);
  } catch (x) { toast(x.message); }
});
document.addEventListener('submit', async e => {
  e.preventDefault();
  try { await F[e.target.dataset.f](Object.fromEntries(new FormData(e.target))); } catch (x) { toast(x.message); }
});
(async () => { if (localStorage.t) { try { await enter(); return; } catch (e) { } } render(); })();

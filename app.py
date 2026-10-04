import os, csv, io
from datetime import date
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, Response, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature

app = Flask(__name__, static_folder="public", static_url_path="")
url = os.environ.get("DATABASE_URL", "sqlite:///gastos.db")
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql://", 1)
app.config.update(SQLALCHEMY_DATABASE_URI=url,
                  SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True})
db = SQLAlchemy(app)
ser = URLSafeTimedSerializer(os.environ.get("SECRET_KEY", "dev-secret-change-me"))
LIMIT = {"free": 4, "premium": 10}


class Family(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    plan = db.Column(db.String(20), default="free")


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    pw = db.Column(db.String(300), nullable=False)
    role = db.Column(db.String(40), default="Member")
    is_owner = db.Column(db.Boolean, default=False)
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"))


class Invite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String(200), nullable=False)


class Tx(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, index=True)
    user_id = db.Column(db.Integer)
    kind = db.Column(db.String(10))  # income | expense
    amount = db.Column(db.Float)
    category = db.Column(db.String(60))
    note = db.Column(db.String(200), default="")
    date = db.Column(db.Date, default=date.today)


class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, index=True)
    name = db.Column(db.String(120))
    amount = db.Column(db.Float)
    due = db.Column(db.Date)
    paid = db.Column(db.Boolean, default=False)


class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, index=True)
    name = db.Column(db.String(120))
    target = db.Column(db.Float)
    saved = db.Column(db.Float, default=0)


with app.app_context():
    db.create_all()


def err(m, c=400):
    return jsonify(error=m), c


def auth(f):
    @wraps(f)
    def w(*a, **k):
        try:
            uid = ser.loads(request.headers.get("Authorization", "")[7:], max_age=2592000)
        except BadSignature:
            return err("Please sign in", 401)
        g.u = db.session.get(User, uid)
        if not g.u:
            return err("Please sign in", 401)
        return f(*a, **k)
    return w


def fam(f):
    @wraps(f)
    @auth
    def w(*a, **k):
        if not g.u.family_id:
            return err("Create a family first")
        g.f = db.session.get(Family, g.u.family_id)
        return f(*a, **k)
    return w


def token(u):
    return ser.dumps(u.id)


@app.get("/")
def home():
    return send_from_directory("public", "index.html")


@app.post("/api/signup")
def signup():
    d = request.get_json() or {}
    name, email, pw = d.get("name", "").strip(), d.get("email", "").strip().lower(), d.get("password", "")
    if not name or "@" not in email or len(pw) < 6:
        return err("Enter a name, valid email and a password of 6+ characters")
    if User.query.filter_by(email=email).first():
        return err("Email already registered")
    u = User(name=name, email=email, pw=generate_password_hash(pw))
    inv = Invite.query.filter_by(email=email).first()
    if inv:  # joined by invitation
        u.family_id = inv.family_id
        db.session.delete(inv)
    db.session.add(u)
    db.session.commit()
    return jsonify(token=token(u))


@app.post("/api/signin")
def signin():
    d = request.get_json() or {}
    u = User.query.filter_by(email=d.get("email", "").strip().lower()).first()
    if not u or not check_password_hash(u.pw, d.get("password", "")):
        return err("Wrong email or password", 401)
    return jsonify(token=token(u))


@app.get("/api/me")
@auth
def me():
    u, out = g.u, {"name": g.u.name, "email": g.u.email, "family": None}
    if u.family_id:
        f = db.session.get(Family, u.family_id)
        out["family"] = {"name": f.name, "plan": f.plan, "limit": LIMIT[f.plan], "owner": u.is_owner,
                         "members": [{"name": m.name, "role": m.role, "owner": m.is_owner}
                                     for m in User.query.filter_by(family_id=f.id)],
                         "invites": [i.email for i in Invite.query.filter_by(family_id=f.id)]}
    return jsonify(out)


@app.post("/api/family")
@auth
def make_family():
    d = request.get_json() or {}
    if g.u.family_id:
        return err("You already have a family")
    if not d.get("name", "").strip():
        return err("Family name required")
    f = Family(name=d["name"].strip())
    db.session.add(f)
    db.session.flush()
    g.u.family_id, g.u.is_owner, g.u.role = f.id, True, d.get("role") or "Parent"
    db.session.commit()
    return jsonify(ok=1)


@app.post("/api/invite")
@fam
def invite():
    email = (request.get_json() or {}).get("email", "").strip().lower()
    if "@" not in email:
        return err("Enter a valid email")
    used = User.query.filter_by(family_id=g.f.id).count() + Invite.query.filter_by(family_id=g.f.id).count()
    if used >= LIMIT[g.f.plan]:
        return err(f"{g.f.plan.title()} plan allows up to {LIMIT[g.f.plan]} members. Upgrade for more.")
    u = User.query.filter_by(email=email).first()
    if u and not u.family_id:
        u.family_id = g.f.id
    elif u:
        return err("That person is already in a family")
    else:
        db.session.add(Invite(family_id=g.f.id, email=email))
    db.session.commit()
    return jsonify(ok=1)


@app.post("/api/upgrade")
@fam
def upgrade():  # demo only: no payment is taken
    if not g.u.is_owner:
        return err("Only the owner can upgrade")
    g.f.plan = "premium"
    db.session.commit()
    return jsonify(ok=1)


def num(v):
    try:
        x = float(v)
        if x <= 0:
            raise ValueError
        return x
    except (TypeError, ValueError):
        raise ValueError("Enter an amount greater than 0")


def pdate(s):
    try:
        return date.fromisoformat(s) if s else date.today()
    except ValueError:
        return date.today()


@app.route("/api/transactions", methods=["GET", "POST"])
@fam
def txs():
    if request.method == "POST":
        d = request.get_json() or {}
        try:
            amt = num(d.get("amount"))
        except ValueError as e:
            return err(str(e))
        kind = "income" if d.get("kind") == "income" else "expense"
        db.session.add(Tx(family_id=g.f.id, user_id=g.u.id, kind=kind, amount=amt,
                          category=d.get("category") or "Other", note=(d.get("note") or "")[:200],
                          date=pdate(d.get("date"))))
        db.session.commit()
        return jsonify(ok=1)
    rows = Tx.query.filter_by(family_id=g.f.id).order_by(Tx.date.desc(), Tx.id.desc()).limit(100)
    return jsonify([{"kind": r.kind, "amount": r.amount, "category": r.category,
                     "note": r.note, "date": r.date.isoformat()} for r in rows])


def summarize(rows):
    inc = sum(r.amount for r in rows if r.kind == "income")
    exp = sum(r.amount for r in rows if r.kind == "expense")
    cats = {}
    for r in rows:
        if r.kind == "expense":
            cats[r.category] = cats.get(r.category, 0) + r.amount
    return {"income": inc, "expense": exp, "balance": inc - exp,
            "cats": {k: round(v * 100 / exp) for k, v in cats.items()} if exp else {}}


def year_rows(fid, y):
    return [r for r in Tx.query.filter_by(family_id=fid) if r.date.year == y]


@app.get("/api/dashboard")
@fam
def dash():
    t = date.today()
    return jsonify(summarize([r for r in year_rows(g.f.id, t.year) if r.date.month == t.month]))


@app.get("/api/reports")
@fam
def reports():
    t = date.today()
    rows = year_rows(g.f.id, t.year)
    goals = Goal.query.filter_by(family_id=g.f.id).all()
    tgt = sum(x.target for x in goals)
    months = {m: summarize([r for r in rows if r.date.month == m]) for m in range(1, t.month + 1)}
    return jsonify(month=summarize([r for r in rows if r.date.month == t.month]),
                   year=summarize(rows), months=months,
                   savings=round(sum(x.saved for x in goals) * 100 / tgt) if tgt else 0)


@app.get("/api/export")
@fam
def export():
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["date", "type", "category", "amount", "note"])
    for r in Tx.query.filter_by(family_id=g.f.id).order_by(Tx.date):
        w.writerow([r.date, r.kind, r.category, r.amount, r.note])
    return Response(out.getvalue(), mimetype="text/csv")


@app.route("/api/bills", methods=["GET", "POST"])
@fam
def bills():
    if request.method == "POST":
        d = request.get_json() or {}
        try:
            amt = num(d.get("amount"))
        except ValueError as e:
            return err(str(e))
        if not d.get("name"):
            return err("Bill name required")
        db.session.add(Bill(family_id=g.f.id, name=d["name"], amount=amt, due=pdate(d.get("due"))))
        db.session.commit()
        return jsonify(ok=1)
    rows = Bill.query.filter_by(family_id=g.f.id, paid=False).order_by(Bill.due)
    return jsonify([{"id": b.id, "name": b.name, "amount": b.amount, "due": b.due.isoformat()} for b in rows])


@app.post("/api/bills/<int:i>/pay")
@fam
def pay(i):
    b = Bill.query.filter_by(id=i, family_id=g.f.id).first_or_404()
    b.paid = True
    db.session.add(Tx(family_id=g.f.id, user_id=g.u.id, kind="expense", amount=b.amount,
                      category="Bills", note=b.name, date=date.today()))
    db.session.commit()
    return jsonify(ok=1)


@app.route("/api/goals", methods=["GET", "POST"])
@fam
def goals():
    if request.method == "POST":
        d = request.get_json() or {}
        try:
            tgt = num(d.get("target"))
        except ValueError as e:
            return err(str(e))
        if not d.get("name"):
            return err("Goal name required")
        db.session.add(Goal(family_id=g.f.id, name=d["name"], target=tgt, saved=0))
        db.session.commit()
        return jsonify(ok=1)
    return jsonify([{"id": x.id, "name": x.name, "target": x.target, "saved": x.saved}
                    for x in Goal.query.filter_by(family_id=g.f.id)])


@app.post("/api/goals/<int:i>/add")
@fam
def goal_add(i):
    x = Goal.query.filter_by(id=i, family_id=g.f.id).first_or_404()
    try:
        x.saved += num((request.get_json() or {}).get("amount"))
    except ValueError as e:
        return err(str(e))
    db.session.commit()
    return jsonify(ok=1)


if __name__ == "__main__":
    app.run(debug=True)

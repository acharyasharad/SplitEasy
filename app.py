from flask import Flask, jsonify, request, render_template
import sqlite3, os

app = Flask(__name__)
DB = "splitter.db"

# ── Database setup ─────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS groups (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS members (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                name     TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES groups(id)
            );
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id    INTEGER NOT NULL,
                paid_by     INTEGER NOT NULL,
                description TEXT NOT NULL,
                amount      REAL NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id)  REFERENCES groups(id),
                FOREIGN KEY (paid_by)   REFERENCES members(id)
            );
            CREATE TABLE IF NOT EXISTS expense_splits (
                expense_id INTEGER NOT NULL,
                member_id  INTEGER NOT NULL,
                share      REAL NOT NULL,
                PRIMARY KEY (expense_id, member_id)
            );
        """)

init_db()

# ── Helper: calculate who owes whom ───────────────────────────────────────────
def calculate_balances(group_id):
    db = get_db()

    members = {r["id"]: r["name"] for r in
               db.execute("SELECT id, name FROM members WHERE group_id=?", (group_id,))}

    # Net balance per member (positive = owed money, negative = owes money)
    balances = {mid: 0.0 for mid in members}

    expenses = db.execute(
        "SELECT id, paid_by, amount FROM expenses WHERE group_id=?", (group_id,)
    ).fetchall()

    for exp in expenses:
        balances[exp["paid_by"]] += exp["amount"]  # payer gets credit
        splits = db.execute(
            "SELECT member_id, share FROM expense_splits WHERE expense_id=?", (exp["id"],)
        ).fetchall()
        for s in splits:
            balances[s["member_id"]] -= s["share"]  # each member owes their share

    # Simplify debts (greedy algorithm)
    creditors = sorted([(v, k) for k, v in balances.items() if v > 0.001], reverse=True)
    debtors   = sorted([(abs(v), k) for k, v in balances.items() if v < -0.001], reverse=True)

    settlements = []
    i, j = 0, 0
    while i < len(creditors) and j < len(debtors):
        credit_amt, creditor = creditors[i]
        debt_amt,   debtor   = debtors[j]
        amount = round(min(credit_amt, debt_amt), 2)
        settlements.append({
            "from":        members[debtor],
            "to":          members[creditor],
            "amount":      amount,
            "from_id":     debtor,
            "to_id":       creditor,
        })
        creditors[i] = (round(credit_amt - amount, 2), creditor)
        debtors[j]   = (round(debt_amt   - amount, 2), debtor)
        if creditors[i][0] < 0.001: i += 1
        if debtors[j][0]   < 0.001: j += 1

    return {
        "balances":    {members[k]: round(v, 2) for k, v in balances.items()},
        "settlements": settlements,
    }

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# Groups
@app.route("/api/groups", methods=["GET"])
def get_groups():
    db = get_db()
    groups = db.execute("SELECT * FROM groups ORDER BY created_at DESC").fetchall()
    return jsonify([dict(g) for g in groups])

@app.route("/api/groups", methods=["POST"])
def create_group():
    data = request.json
    if not data.get("name"):
        return jsonify({"error": "Group name required"}), 400
    db = get_db()
    cur = db.execute("INSERT INTO groups (name) VALUES (?)", (data["name"],))
    db.commit()
    return jsonify({"id": cur.lastrowid, "name": data["name"]}), 201

@app.route("/api/groups/<int:gid>", methods=["DELETE"])
def delete_group(gid):
    db = get_db()
    db.execute("DELETE FROM expense_splits WHERE expense_id IN (SELECT id FROM expenses WHERE group_id=?)", (gid,))
    db.execute("DELETE FROM expenses WHERE group_id=?", (gid,))
    db.execute("DELETE FROM members WHERE group_id=?", (gid,))
    db.execute("DELETE FROM groups WHERE id=?", (gid,))
    db.commit()
    return jsonify({"deleted": True})

# Members
@app.route("/api/groups/<int:gid>/members", methods=["GET"])
def get_members(gid):
    db = get_db()
    members = db.execute("SELECT * FROM members WHERE group_id=?", (gid,)).fetchall()
    return jsonify([dict(m) for m in members])

@app.route("/api/groups/<int:gid>/members", methods=["POST"])
def add_member(gid):
    data = request.json
    if not data.get("name"):
        return jsonify({"error": "Member name required"}), 400
    db = get_db()
    cur = db.execute("INSERT INTO members (group_id, name) VALUES (?,?)", (gid, data["name"]))
    db.commit()
    return jsonify({"id": cur.lastrowid, "name": data["name"]}), 201

# Expenses
@app.route("/api/groups/<int:gid>/expenses", methods=["GET"])
def get_expenses(gid):
    db = get_db()
    exps = db.execute("""
        SELECT e.id, e.description, e.amount, e.created_at, m.name as paid_by_name
        FROM expenses e JOIN members m ON e.paid_by = m.id
        WHERE e.group_id=? ORDER BY e.created_at DESC
    """, (gid,)).fetchall()
    return jsonify([dict(e) for e in exps])

@app.route("/api/groups/<int:gid>/expenses", methods=["POST"])
def add_expense(gid):
    data = request.json
    if not all([data.get("description"), data.get("amount"), data.get("paid_by"), data.get("split_among")]):
        return jsonify({"error": "Missing fields"}), 400

    amount      = float(data["amount"])
    split_among = data["split_among"]   # list of member IDs
    share       = round(amount / len(split_among), 2)

    db = get_db()
    cur = db.execute(
        "INSERT INTO expenses (group_id, paid_by, description, amount) VALUES (?,?,?,?)",
        (gid, data["paid_by"], data["description"], amount)
    )
    exp_id = cur.lastrowid
    for mid in split_among:
        db.execute("INSERT INTO expense_splits VALUES (?,?,?)", (exp_id, mid, share))
    db.commit()
    return jsonify({"id": exp_id}), 201

@app.route("/api/expenses/<int:eid>", methods=["DELETE"])
def delete_expense(eid):
    db = get_db()
    db.execute("DELETE FROM expense_splits WHERE expense_id=?", (eid,))
    db.execute("DELETE FROM expenses WHERE id=?", (eid,))
    db.commit()
    return jsonify({"deleted": True})

# Balances / settlements
@app.route("/api/groups/<int:gid>/balances")
def get_balances(gid):
    return jsonify(calculate_balances(gid))

if __name__ == "__main__":
    app.run(debug=True, port=8081)

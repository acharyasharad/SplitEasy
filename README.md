# 💸 SplitEasy — Group Expense Splitter

A full-stack web app to split expenses among friends for trips, dinners, or any group activity. Like a mini Splitwise — built with Python Flask + SQLite.

---

## ✨ Features

- 📁 Create multiple groups (Goa Trip, Dinner, etc.)
- 👥 Add members to each group
- 💰 Log expenses with who paid and who shares the cost
- 🧮 Auto-calculates the simplest way to settle up (minimizes transactions)
- 📊 Shows net balance per person (+/- how much they owe or get back)
- 🗑️ Delete expenses or entire groups

---

## 🛠 Tech Stack

| Layer    | Technology           |
|----------|----------------------|
| Backend  | Python, Flask        |
| Database | SQLite               |
| Frontend | HTML, CSS, Vanilla JS|

---

## 🚀 Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Open **http://127.0.0.1:8081** in your browser.

---

## 📁 Project Structure

```
splitter/
├── app.py              # Flask backend — routes, SQLite, settlement algorithm
├── templates/
│   └── index.html      # Full frontend — groups, expenses, settle up
├── requirements.txt
└── README.md
```

---

## 🧮 How the Settlement Algorithm Works

1. Calculate each person's **net balance** (total paid − total share owed)
2. Separate into **creditors** (positive balance) and **debtors** (negative)
3. Use a **greedy algorithm** to match debtors to creditors, minimizing the number of transactions
4. Result: the simplest possible set of payments to settle all debts

Example: 3 people, 5 expenses → settled in just 2 transactions instead of 5.

---

## 💡 How to Extend

- Add **date filters** for expenses
- Add **currency selector**
- Add **export to PDF** feature
- Add **user authentication** so groups persist per user

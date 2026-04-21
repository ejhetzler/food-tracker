from flask import Flask, render_template, request, redirect
import csv
import os
from datetime import datetime
from collections import Counter, defaultdict

app = Flask(__name__)

FILE_NAME = "expenses.csv"
HEADERS = ["date", "item", "meal", "source", "amount", "reference"]

# Old category → (meal, source) mapping for migration
CATEGORY_MAP = {
    "Breakfast":          ("Breakfast", "Eating Out"),
    "Lunch":              ("Lunch",     "Eating Out"),
    "Dinner":             ("Dinner",    "Eating Out"),
    "Snack":              ("Snack",     "Eating Out"),
    "Drink":              ("Drink",     "Eating Out"),
    "Groceries":          ("",          "Grocery Shopping"),
    "Home Cooked":        ("",          "From Groceries"),
    "Groceries (Buying)": ("",          "Grocery Shopping"),
    "Groceries (Eating)": ("",          "From Groceries"),
}


def migrate_if_needed():
    if not os.path.exists(FILE_NAME):
        with open(FILE_NAME, mode="w", newline="") as f:
            csv.writer(f).writerow(HEADERS)
        return
    with open(FILE_NAME, mode="r") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if "category" in fields and "meal" not in fields:
            rows = list(reader)
    if "category" in fields and "meal" not in fields:
        new_rows = []
        for row in rows:
            meal, source = CATEGORY_MAP.get(row.get("category", ""), ("", "Eating Out"))
            new_rows.append({
                "date":      row["date"],
                "item":      row["item"],
                "meal":      meal,
                "source":    source,
                "amount":    row["amount"],
                "reference": row.get("reference", ""),
            })
        with open(FILE_NAME, mode="w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(new_rows)


migrate_if_needed()


def read_expenses():
    expenses = []
    with open(FILE_NAME, mode="r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["amount"] = float(row["amount"])
            row.setdefault("meal", "")
            row.setdefault("source", "Eating Out")
            row.setdefault("reference", "")
            expenses.append(row)
    return expenses


def is_spending(e):
    return e["source"] != "From Groceries"


@app.route("/")
def index():
    expenses = read_expenses()
    today = datetime.today().strftime("%Y-%m-%d")
    today_total = sum(e["amount"] for e in expenses if e["date"] == today and is_spending(e))
    grocery_runs = [e for e in expenses if e["source"] == "Grocery Shopping"]
    recent = list(reversed(expenses))[:10]
    return render_template(
        "index.html",
        expenses=recent,
        today_total=round(today_total, 2),
        today=today,
        grocery_runs=grocery_runs,
    )


@app.route("/add", methods=["POST"])
def add_expense():
    date      = request.form["date"]
    item      = request.form["item"]
    meal      = request.form.get("meal", "")
    source    = request.form["source"]
    reference = request.form.get("reference", "")
    amount    = "0.00" if source == "From Groceries" else request.form.get("amount", "0.00")

    with open(FILE_NAME, mode="a", newline="") as f:
        csv.writer(f).writerow([date, item, meal, source, amount, reference])

    return redirect("/")


@app.route("/history")
def history():
    expenses = list(reversed(read_expenses()))
    return render_template("history.html", expenses=expenses)


@app.route("/stats")
def stats():
    expenses = read_expenses()
    spending = [e for e in expenses if is_spending(e)]

    # Monthly totals — last 6 months
    monthly = defaultdict(float)
    for e in spending:
        monthly[e["date"][:7]] += e["amount"]
    all_months = sorted(monthly.keys())[-6:]
    monthly_values = [round(monthly[m], 2) for m in all_months]

    # Spending by meal (exclude Grocery Shopping)
    meal_totals = defaultdict(float)
    for e in spending:
        if e["source"] != "Grocery Shopping" and e["meal"]:
            meal_totals[e["meal"]] += e["amount"]
    meal_totals = dict(sorted(meal_totals.items(), key=lambda x: -x[1]))

    # Eating Out vs From Groceries (grocery shopping is its own bucket)
    source_totals = defaultdict(float)
    for e in spending:
        source_totals[e["source"]] += e["amount"]
    source_totals = dict(sorted(source_totals.items(), key=lambda x: -x[1]))

    # Top 5 most frequent items
    item_counter = Counter(e["item"] for e in spending)
    top_items = item_counter.most_common(5)

    total_spent     = round(sum(e["amount"] for e in spending), 2)
    this_month_key  = datetime.today().strftime("%Y-%m")
    this_month      = round(sum(e["amount"] for e in spending if e["date"][:7] == this_month_key), 2)
    biggest         = max(spending, key=lambda x: x["amount"], default=None)
    total_entries   = len(expenses)

    return render_template(
        "stats.html",
        monthly_labels=all_months,
        monthly_values=monthly_values,
        meal_totals=meal_totals,
        source_totals=source_totals,
        top_items=top_items,
        total_spent=total_spent,
        this_month=this_month,
        biggest=biggest,
        total_entries=total_entries,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

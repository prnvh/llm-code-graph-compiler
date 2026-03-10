"""
benchmark/fixtures/generate_fixtures.py

Generates all fixture files used by the benchmark task suite.
Run once from the project root before benchmarking:
    python benchmark/fixtures/generate_fixtures.py

Fixtures created
────────────────
CSV / JSON
    people.csv          10 rows  (1 null salary)
    employees.csv       23 rows  (1 null salary, 3 duplicate rows)
    customers.csv       20 rows
    predictions.csv     30 rows  (1 null score)
    sales.csv           40 rows  (2 exact duplicates → 38 after dedup)
    events.json         50 records
    products.json       25 rows

SQLite databases
    existing.db         records table — 20 rows (15 value > 10, 5 value <= 10)
    scores.db           students table — 30 rows (20 score > 70)
                        courses table  —  5 rows

Exact row counts for criteria
    sales.csv total:              40 rows
    sales.csv revenue > 100:      27 rows  (both duplicate rows exceed threshold)
    sales.csv after dedup:        38 rows
    products.json total:          25 rows
    products.json price > 50:     15 rows
    existing.db records:          20 rows (15 value > 10)
    scores.db students:           30 rows (20 score > 70)
    scores.db courses:             5 rows
"""

import csv
import json
import os
import random
import sqlite3
from pathlib import Path

import pandas as pd

FIXTURE_DIR = Path(__file__).parent
random.seed(42)


# ─────────────────────────────────────────────────────────────────────────────
# CSV / JSON fixtures
# ─────────────────────────────────────────────────────────────────────────────

def create_people_csv():
    people = pd.DataFrame({
        "name":   ["Alice", "Bob", "Carol", "Dave", "Eve",
                   "Frank", "Grace", "Heidi", "Ivan", "Judy"],
        "age":    [29, 22, 35, 41, 25, 33, 28, 45, 19, 37],
        "city":   ["NYC", "LA", "NYC", "Chicago", "LA",
                   "NYC", "Chicago", "LA", "NYC", "Chicago"],
        "region": ["East", "West", "East", "Central", "West",
                   "East", "Central", "West", "East", "Central"],
        "salary": [55000, 38000, 72000, 91000, 42000,
                   67000, 51000, 88000, 31000, 74000],
    })
    people.loc[4, "salary"] = None
    people.to_csv(FIXTURE_DIR / "people.csv", index=False)
    print(f"  [OK] people.csv — {len(people)} rows (1 null salary)")


def create_employees_csv():
    departments = ["Engineering", "Marketing", "Sales", "HR", "Engineering", "Sales"]
    regions = ["East", "West", "Central"]
    employees = pd.DataFrame({
        "name":       [f"Employee_{i}" for i in range(20)],
        "department": [departments[i % len(departments)] for i in range(20)],
        "region":     [regions[i % len(regions)] for i in range(20)],
        "salary":     [random.randint(30000, 100000) for _ in range(20)],
        "tenure":     [random.randint(1, 10) for _ in range(20)],
    })
    employees.loc[3, "salary"] = None
    duplicates = employees.iloc[:3].copy()
    employees = pd.concat([employees, duplicates], ignore_index=True)
    employees.to_csv(FIXTURE_DIR / "employees.csv", index=False)
    print(f"  [OK] employees.csv — {len(employees)} rows (1 null salary, 3 duplicate rows)")


def create_customers_csv():
    customers = pd.DataFrame({
        "name":        [f"Customer_{i}" for i in range(20)],
        "status":      [random.choice(["active", "active", "inactive"]) for _ in range(20)],
        "signup_date": pd.date_range("2023-01-01", periods=20, freq="ME").strftime("%Y-%m-%d").tolist(),
        "region":      [random.choice(["East", "West", "Central"]) for _ in range(20)],
    })
    customers.to_csv(FIXTURE_DIR / "customers.csv", index=False)
    print(f"  [OK] customers.csv — {len(customers)} rows")


def create_predictions_csv():
    predictions = pd.DataFrame({
        "name":  [f"Item_{i}" for i in range(30)],
        "score": [round(random.uniform(0.0, 1.0), 3) for _ in range(30)],
        "label": [random.choice(["A", "B", "C"]) for _ in range(30)],
    })
    predictions.loc[5, "score"] = None
    predictions.to_csv(FIXTURE_DIR / "predictions.csv", index=False)
    print(f"  [OK] predictions.csv — {len(predictions)} rows (1 null score)")


def create_sales_csv():
    """
    40 rows total, 2 exact duplicates (→ 38 after dedup).
    revenue > 100: 27 rows (25 unique + both duplicate rows exceed threshold).
    """
    rows = []
    row_id = 1

    # Electronics: 12 revenue > 100, 3 revenue <= 100
    for i in range(15):
        revenue = round(120 + i * 15.3, 2) if i < 12 else round(40 + i * 4.1, 2)
        rows.append([row_id, f"Product_E{i+1:02d}", "Electronics", revenue, random.randint(1, 50)])
        row_id += 1

    # Clothing: 7 revenue > 100, 3 revenue <= 100
    for i in range(10):
        revenue = round(105 + i * 8.7, 2) if i < 7 else round(35 + i * 5.2, 2)
        rows.append([row_id, f"Product_C{i+1:02d}", "Clothing", revenue, random.randint(1, 30)])
        row_id += 1

    # Food: 6 revenue > 100, 7 revenue <= 100
    for i in range(13):
        revenue = round(110 + i * 9.1, 2) if i < 6 else round(20 + i * 4.3, 2)
        rows.append([row_id, f"Product_F{i+1:02d}", "Food", revenue, random.randint(5, 100)])
        row_id += 1

    # 2 exact duplicates — rows 0 and 1 both have revenue > 100,
    # so total revenue > 100 is 25 unique + 2 duplicates = 27.
    for src in (rows[0], rows[1]):
        rows.append([row_id, src[1], src[2], src[3], src[4]])
        row_id += 1

    assert len(rows) == 40
    over_100 = sum(1 for r in rows if r[3] > 100)
    assert over_100 == 27, f"Expected 27 rows with revenue > 100, got {over_100}"

    with open(FIXTURE_DIR / "sales.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "product", "category", "revenue", "quantity"])
        writer.writerows(rows)

    print(f"  [OK] sales.csv — {len(rows)} rows ({over_100} revenue > 100, 2 duplicates)")


def create_events_json():
    event_types = ["click", "view", "purchase", "signup", "logout"]
    events = [
        {
            "event_id":   i,
            "event_type": random.choice(event_types),
            "user_id":    random.randint(1000, 1099),
            "timestamp":  f"2024-0{random.randint(1,9)}-{random.randint(10,28)}T{random.randint(0,23):02d}:00:00Z",
            "value":      round(random.uniform(0, 500), 2),
        }
        for i in range(50)
    ]
    with open(FIXTURE_DIR / "events.json", "w") as f:
        json.dump(events, f, indent=2)
    print(f"  [OK] events.json — {len(events)} records")


def create_products_json():
    """25 rows; first 15 have price > 50."""
    categories = ["A"] * 10 + ["B"] * 8 + ["C"] * 7
    products = []
    for i, cat in enumerate(categories, start=1):
        price    = round(55 + i * 7.3, 2) if i <= 15 else round(10 + (i - 15) * 3.8, 2)
        in_stock = i % 3 != 0
        products.append({"id": i, "name": f"Product_{i:03d}", "category": cat,
                         "price": price, "in_stock": in_stock})

    assert len(products) == 25
    over_50 = sum(1 for p in products if p["price"] > 50)
    assert over_50 == 15, f"Expected 15 products with price > 50, got {over_50}"

    with open(FIXTURE_DIR / "products.json", "w") as f:
        json.dump(products, f, indent=2)
    print(f"  [OK] products.json — {len(products)} rows ({over_50} price > 50)")


# ─────────────────────────────────────────────────────────────────────────────
# SQLite fixtures
# ─────────────────────────────────────────────────────────────────────────────

def create_existing_db():
    """records table: 20 rows (15 value > 10, 5 value <= 10)."""
    path = FIXTURE_DIR / "existing.db"
    path.unlink(missing_ok=True)

    conn = sqlite3.connect(path)
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE records (
            id       INTEGER PRIMARY KEY,
            name     TEXT    NOT NULL,
            value    REAL    NOT NULL,
            category TEXT    NOT NULL
        )
    """)

    categories = ["alpha", "beta", "gamma"]
    rows = []
    for i in range(1, 16):   # value > 10
        rows.append((i, f"record_{i:02d}", round(10.5 + (i * 3.7) % 89.3, 2), categories[(i-1) % 3]))
    for i in range(16, 21):  # value <= 10
        rows.append((i, f"record_{i:02d}", round(1.0  + (i * 1.3) % 8.9,  2), categories[(i-1) % 3]))

    cur.executemany("INSERT INTO records VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()
    print(f"  [OK] existing.db — {len(rows)} rows (15 value > 10, 5 value <= 10)")


def create_scores_db():
    """
    students table: 30 rows, 20 with score > 70.
    courses table:   5 rows.
    """
    path = FIXTURE_DIR / "scores.db"
    path.unlink(missing_ok=True)

    conn = sqlite3.connect(path)
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE students (
            id        INTEGER PRIMARY KEY,
            name      TEXT    NOT NULL,
            grade     TEXT    NOT NULL,
            score     REAL    NOT NULL,
            course_id INTEGER NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE courses (
            id         INTEGER PRIMARY KEY,
            name       TEXT    NOT NULL,
            department TEXT    NOT NULL
        )
    """)

    courses = [
        (1, "Mathematics", "Science"),
        (2, "English",     "Humanities"),
        (3, "Physics",     "Science"),
        (4, "History",     "Humanities"),
        (5, "Biology",     "Science"),
    ]
    cur.executemany("INSERT INTO courses VALUES (?, ?, ?)", courses)

    # A=8 (score 82-99), B=12 (score 71-79), C=10 (score 50-64) → 20 score > 70
    grade_pool = ["A"] * 8 + ["B"] * 12 + ["C"] * 10
    random.shuffle(grade_pool)

    students = []
    for i in range(1, 31):
        grade = grade_pool[i - 1]
        if grade == "A":
            score = round(random.uniform(82, 99), 1)
        elif grade == "B":
            score = round(random.uniform(71, 79), 1)
        else:
            score = round(random.uniform(50, 64), 1)
        students.append((i, f"Student_{i:02d}", grade, score, random.randint(1, 5)))

    cur.executemany("INSERT INTO students VALUES (?, ?, ?, ?, ?)", students)
    conn.commit()
    conn.close()

    over_70 = sum(1 for s in students if s[3] > 70)
    print(f"  [OK] scores.db — students: {len(students)} rows ({over_70} score > 70), "
          f"courses: {len(courses)} rows")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Writing fixtures to: {FIXTURE_DIR.resolve()}\n")

    print("CSV / JSON")
    create_people_csv()
    create_employees_csv()
    create_customers_csv()
    create_predictions_csv()
    create_sales_csv()
    create_events_json()
    create_products_json()

    print("\nSQLite")
    create_existing_db()
    create_scores_db()

    print("\nAll fixtures ready.")
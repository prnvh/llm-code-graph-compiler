"""
benchmark/create_fixtures.py

Creates all fixture files for the benchmark suite.
Run once from the project root before running any benchmarks:
    python benchmark/create_fixtures.py

Fixtures created:
    benchmark/fixtures/existing.db     — SQLite, records(id, name, value, category), 20 rows
    benchmark/fixtures/scores.db       — SQLite, students(30) + grades(5) tables
    benchmark/fixtures/sales.csv       — 40 rows: id, product, category, revenue, quantity
    benchmark/fixtures/products.json   — 25 rows: id, name, category, price, in_stock

Existing fixtures left untouched:
    benchmark/fixtures/predictions.csv  (30 rows)
    benchmark/fixtures/employees.csv    (23 rows)
    benchmark/fixtures/events.json      (50 rows)
    benchmark/fixtures/regions.csv

Exact row counts (for criteria):
    existing.db records:          20 rows total, 15 rows WHERE value > 10
    scores.db students:           30 rows total, 20 rows WHERE score > 70
    scores.db grades:             5 rows (one per letter grade)
    sales.csv:                    40 rows total (includes 2 exact duplicates → 38 after dedup)
    sales.csv revenue > 100:      25 rows
    products.json:                25 rows total
    products.json price > 50:     15 rows
"""

import os
import json
import sqlite3
import csv
import random
from pathlib import Path

FIXTURE_DIR = Path("benchmark/fixtures")
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

random.seed(42)  # reproducible


# ─────────────────────────────────────────────────────────────────────
# existing.db  (20 rows: 15 with value > 10, 5 with value <= 10)
# ─────────────────────────────────────────────────────────────────────

def create_existing_db():
    path = FIXTURE_DIR / "existing.db"
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE records (
            id       INTEGER PRIMARY KEY,
            name     TEXT    NOT NULL,
            value    REAL    NOT NULL,
            category TEXT    NOT NULL
        )
    """)

    categories = ["alpha", "beta", "gamma"]
    # 15 rows with value > 10
    rows = []
    for i in range(1, 16):
        cat = categories[(i - 1) % 3]
        val = round(10.5 + (i * 3.7) % 89.3, 2)  # all > 10
        rows.append((i, f"record_{i:02d}", val, cat))

    # 5 rows with value <= 10
    for i in range(16, 21):
        cat = categories[(i - 1) % 3]
        val = round(1.0 + (i * 1.3) % 8.9, 2)  # all <= 10
        rows.append((i, f"record_{i:02d}", val, cat))

    cur.executemany("INSERT INTO records VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()
    print(f"  [OK] existing.db — {len(rows)} rows (15 value > 10, 5 value <= 10)")


# ─────────────────────────────────────────────────────────────────────
# scores.db  (students: 30 rows, grades: 5 rows)
# ─────────────────────────────────────────────────────────────────────

def create_scores_db():
    path = FIXTURE_DIR / "scores.db"
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE students (
            id         INTEGER PRIMARY KEY,
            name       TEXT    NOT NULL,
            grade      TEXT    NOT NULL,
            score      REAL    NOT NULL,
            course_id  INTEGER NOT NULL
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

    # Grade distribution: A=8, B=12, C=10
    grade_pool = ["A"] * 8 + ["B"] * 12 + ["C"] * 10
    random.shuffle(grade_pool)

    students = []
    for i in range(1, 31):
        grade = grade_pool[i - 1]
        # A → score 80-100, B → 65-79, C → 50-64; 20 rows have score > 70
        if grade == "A":
            score = round(random.uniform(82, 99), 1)
        elif grade == "B":
            # 12 B students: make 12 of them have score > 70
            score = round(random.uniform(71, 79), 1)
        else:
            score = round(random.uniform(50, 64), 1)

        course_id = random.randint(1, 5)
        students.append((i, f"Student_{i:02d}", grade, score, course_id))

    cur.executemany("INSERT INTO students VALUES (?, ?, ?, ?, ?)", students)
    conn.commit()
    conn.close()

    over_70 = sum(1 for s in students if s[3] > 70)
    print(f"  [OK] scores.db — students: {len(students)} rows ({over_70} score > 70), courses: {len(courses)} rows")


# ─────────────────────────────────────────────────────────────────────
# sales.csv  (40 rows, 2 exact duplicates → 38 unique)
# revenue > 100: exactly 25 rows
# ─────────────────────────────────────────────────────────────────────

def create_sales_csv():
    path = FIXTURE_DIR / "sales.csv"

    categories = {
        "Electronics": 15,
        "Clothing":    10,
        "Food":        13,   # 13 base + 2 duplicates from this category
    }

    rows = []
    row_id = 1

    # Electronics: revenue > 100 (12 rows) + <= 100 (3 rows)
    for i in range(15):
        revenue = round(120 + i * 15.3, 2) if i < 12 else round(40 + i * 4.1, 2)
        quantity = random.randint(1, 50)
        rows.append([row_id, f"Product_E{i+1:02d}", "Electronics", revenue, quantity])
        row_id += 1

    # Clothing: revenue > 100 (7 rows) + <= 100 (3 rows)
    for i in range(10):
        revenue = round(105 + i * 8.7, 2) if i < 7 else round(35 + i * 5.2, 2)
        quantity = random.randint(1, 30)
        rows.append([row_id, f"Product_C{i+1:02d}", "Clothing", revenue, quantity])
        row_id += 1

    # Food: revenue > 100 (6 rows) + <= 100 (7 rows) → 13 rows
    for i in range(13):
        revenue = round(110 + i * 9.1, 2) if i < 6 else round(20 + i * 4.3, 2)
        quantity = random.randint(5, 100)
        rows.append([row_id, f"Product_F{i+1:02d}", "Food", revenue, quantity])
        row_id += 1

    # 2 exact duplicates (copy rows 1 and 2)
    dup1 = [row_id,     rows[0][1], rows[0][2], rows[0][3], rows[0][4]]
    dup2 = [row_id + 1, rows[1][1], rows[1][2], rows[1][3], rows[1][4]]
    # Make them true duplicates (same values, different id would not be a dup on full row)
    # For DataDeduplicator (which drops full-row dups), make them identical on all non-id cols
    rows.append([row_id,     rows[0][1], rows[0][2], rows[0][3], rows[0][4]])
    rows.append([row_id + 1, rows[1][1], rows[1][2], rows[1][3], rows[1][4]])

    assert len(rows) == 40

    over_100 = sum(1 for r in rows if r[3] > 100)

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "product", "category", "revenue", "quantity"])
        writer.writerows(rows)

    print(f"  [OK] sales.csv — {len(rows)} rows ({over_100} revenue > 100, 2 duplicates)")


# ─────────────────────────────────────────────────────────────────────
# products.json  (25 rows, price > 50: exactly 15 rows)
# ─────────────────────────────────────────────────────────────────────

def create_products_json():
    path = FIXTURE_DIR / "products.json"

    # category A:10, B:8, C:7
    categories = ["A"] * 10 + ["B"] * 8 + ["C"] * 7

    products = []
    for i, cat in enumerate(categories, start=1):
        # price > 50: first 15 rows; price <= 50: last 10
        if i <= 15:
            price = round(55 + i * 7.3, 2)
        else:
            price = round(10 + (i - 15) * 3.8, 2)

        in_stock = i % 3 != 0   # ~2/3 in stock

        products.append({
            "id":       i,
            "name":     f"Product_{i:03d}",
            "category": cat,
            "price":    price,
            "in_stock": in_stock,
        })

    assert len(products) == 25
    over_50 = sum(1 for p in products if p["price"] > 50)

    with open(path, "w") as f:
        json.dump(products, f, indent=2)

    print(f"  [OK] products.json — {len(products)} rows ({over_50} price > 50)")


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Creating benchmark fixtures...\n")
    create_existing_db()
    create_scores_db()
    create_sales_csv()
    create_products_json()
    print("\nAll fixtures created successfully.")
    print(f"Location: {FIXTURE_DIR.resolve()}")
import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

# Safe UTF-8 output on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

app = Flask(__name__)

# Allow the Netlify frontend and local development to call the API.
CORS(app, resources={r"/*": {"origins": "*"}})

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required.")


def get_db_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    """Create the PostgreSQL tables if they do not already exist."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bills (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT NOT NULL DEFAULT 'Other',
                    date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id BIGSERIAL PRIMARY KEY,
                    bill_id BIGINT,
                    description TEXT NOT NULL,
                    amount NUMERIC(12, 2) NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                    category TEXT NOT NULL DEFAULT 'Other',
                    date DATE NOT NULL,
                    CONSTRAINT fk_transactions_bill
                        FOREIGN KEY (bill_id)
                        REFERENCES bills(id)
                        ON DELETE CASCADE
                );
            """)

            # Preserve the existing application's category migration.
            cur.execute("""
                UPDATE transactions
                SET category = 'Shopping'
                WHERE category = 'Bills';
            """)

            cur.execute("""
                UPDATE bills
                SET category = 'Shopping'
                WHERE category = 'Bills';
            """)

        conn.commit()
        print("✅ PostgreSQL database initialized.")
    except Exception as e:
        conn.rollback()
        print(f"❌ PostgreSQL initialization error: {e}")
        raise
    finally:
        conn.close()


def serialize_transaction(row):
    row_dict = dict(row)
    row_dict["id"] = int(row_dict["id"])
    row_dict["_id"] = str(row_dict["id"])
    row_dict["amount"] = float(row_dict["amount"])
    if row_dict.get("bill_id") is not None:
        row_dict["bill_id"] = int(row_dict["bill_id"])
    return row_dict


def serialize_bill(row):
    bill = dict(row)
    bill["id"] = int(bill["id"])
    bill["total_expense"] = float(bill["total_expense"] or 0)
    bill["total_income"] = float(bill["total_income"] or 0)
    bill["net_balance"] = float(bill["net_balance"] or 0)
    bill["total_amount"] = bill["total_expense"]
    bill["item_count"] = int(bill["item_count"] or 0)
    return bill


# ----------------- Root & Health -----------------

@app.route("/")
def home():
    return jsonify({"message": "Welcome to the Personal Finance Tracker API!"})


# ----------------- Bills Management -----------------

@app.route("/bills", methods=["GET"])
def get_bills():
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        b.id,
                        b.name,
                        b.category,
                        b.date,
                        b.created_at,
                        COUNT(t.id) AS item_count,
                        COALESCE(
                            SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END),
                            0
                        ) AS total_expense,
                        COALESCE(
                            SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END),
                            0
                        ) AS total_income,
                        COALESCE(
                            SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE -t.amount END),
                            0
                        ) AS net_balance
                    FROM bills b
                    LEFT JOIN transactions t ON t.bill_id = b.id
                    GROUP BY b.id
                    ORDER BY b.date DESC, b.id DESC
                """)
                rows = cur.fetchall()

                bills = []
                for row in rows:
                    bill = serialize_bill(row)

                    cur.execute("""
                        SELECT id, bill_id, description, amount, type, category, date
                        FROM transactions
                        WHERE bill_id = %s
                        ORDER BY id ASC
                    """, (bill["id"],))

                    bill["items"] = [
                        serialize_transaction(item) for item in cur.fetchall()
                    ]
                    bills.append(bill)

            return jsonify({"bills": bills}), 200
        finally:
            conn.close()

    except Exception as e:
        print(f"❌ Error fetching bills: {e}")
        return jsonify({"error": "Failed to fetch bills"}), 500


@app.route("/bills", methods=["POST"])
def create_bill():
    try:
        data = request.get_json(force=True)

        if not data or not data.get("name"):
            return jsonify({"error": "Bill name is required"}), 400

        name = data["name"].strip()
        category = data.get("category", "Other")
        date = data.get("date") or __import__("datetime").date.today().isoformat()

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO bills (name, category, date)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (name, category, date))

                bill_id = cur.fetchone()["id"]

            conn.commit()
            return jsonify({
                "message": "Bill created successfully",
                "id": int(bill_id),
                "name": name
            }), 201
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    except Exception as e:
        print(f"❌ Error creating bill: {e}")
        return jsonify({"error": "Failed to create bill"}), 500


@app.route("/bills/<int:bill_id>", methods=["GET"])
def get_bill_detail(bill_id):
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, description, category, date, created_at
                    FROM bills
                    WHERE id = %s
                """, (bill_id,))
                bill_row = cur.fetchone()

                if not bill_row:
                    return jsonify({"error": "Bill not found"}), 404

                bill = dict(bill_row)
                bill["id"] = int(bill["id"])

                cur.execute("""
                    SELECT id, bill_id, description, amount, type, category, date
                    FROM transactions
                    WHERE bill_id = %s
                    ORDER BY date DESC, id DESC
                """, (bill_id,))

                items = [
                    serialize_transaction(row) for row in cur.fetchall()
                ]

                total_expense = sum(
                    item["amount"] for item in items if item["type"] == "expense"
                )
                total_income = sum(
                    item["amount"] for item in items if item["type"] == "income"
                )

                bill["total_expense"] = total_expense
                bill["total_income"] = total_income
                bill["net_balance"] = total_income - total_expense
                bill["total_amount"] = total_expense
                bill["items"] = items

                return jsonify({"bill": bill}), 200
        finally:
            conn.close()

    except Exception as e:
        print(f"❌ Error retrieving bill details: {e}")
        return jsonify({"error": "Failed to retrieve bill details"}), 500


@app.route("/bills/<int:bill_id>", methods=["PUT"])
def update_bill(bill_id):
    try:
        data = request.get_json(force=True)

        if not data or not data.get("name"):
            return jsonify({"error": "Bill name is required"}), 400

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE bills
                    SET name = %s, category = %s, date = %s
                    WHERE id = %s
                """, (
                    data["name"].strip(),
                    data.get("category", "Other"),
                    data.get("date", ""),
                    bill_id
                ))

                if cur.rowcount == 0:
                    conn.rollback()
                    return jsonify({"error": "Bill not found"}), 404

            conn.commit()
            return jsonify({"message": "Bill updated successfully"}), 200
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    except Exception as e:
        print(f"❌ Error updating bill: {e}")
        return jsonify({"error": "Failed to update bill"}), 500


@app.route("/bills/<int:bill_id>", methods=["DELETE"])
def delete_bill(bill_id):
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM bills WHERE id = %s",
                    (bill_id,)
                )

                if cur.rowcount == 0:
                    conn.rollback()
                    return jsonify({"error": "Bill not found"}), 404

            # transactions are removed automatically by ON DELETE CASCADE.
            conn.commit()
            return jsonify({
                "message": "Bill and its items deleted successfully"
            }), 200
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    except Exception as e:
        print(f"❌ Error deleting bill: {e}")
        return jsonify({"error": "Failed to delete bill"}), 500


# ----------------- Transactions Management -----------------

@app.route("/add", methods=["POST"])
def add_transaction():
    try:
        data = request.get_json(force=True)

        if not data:
            return jsonify({"error": "No data provided"}), 400

        bill_name = (data.get("bill_name") or "").strip()
        bill_id = data.get("bill_id")
        date = data.get("date") or __import__("datetime").date.today().isoformat()
        category = data.get("category", "Other")

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Resolve or create bill.
                if bill_name:
                    cur.execute(
                        "SELECT id FROM bills WHERE LOWER(name) = LOWER(%s) LIMIT 1",
                        (bill_name,)
                    )
                    existing = cur.fetchone()

                    if existing:
                        bill_id = existing["id"]
                    else:
                        cur.execute("""
                            INSERT INTO bills (name, category, date)
                            VALUES (%s, %s, %s)
                            RETURNING id
                        """, (bill_name, category, date))
                        bill_id = cur.fetchone()["id"]

                elif bill_id in ("", None, "null"):
                    bill_id = None
                else:
                    bill_id = int(bill_id)

                # Multiple items.
                items = data.get("items")

                if items and isinstance(items, list):
                    inserted_ids = []

                    for item in items:
                        item_desc = (item.get("description") or "").strip()
                        if not item_desc:
                            continue

                        try:
                            item_amount = float(item.get("amount", 0))
                        except (ValueError, TypeError):
                            continue

                        if item_amount <= 0:
                            continue

                        item_type = item.get("type", "expense")
                        if item_type not in ["income", "expense"]:
                            item_type = "expense"

                        item_cat = item.get("category") or category
                        item_date = item.get("date") or date

                        cur.execute("""
                            INSERT INTO transactions
                                (bill_id, description, amount, type, category, date)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id
                        """, (
                            bill_id,
                            item_desc,
                            item_amount,
                            item_type,
                            item_cat,
                            item_date
                        ))

                        inserted_ids.append(int(cur.fetchone()["id"]))

                    conn.commit()

                    return jsonify({
                        "message": f"{len(inserted_ids)} items added successfully",
                        "bill_id": int(bill_id) if bill_id is not None else None,
                        "inserted_ids": inserted_ids
                    }), 201

                # Single item.
                required_fields = ["description", "amount", "type"]

                if not all(key in data for key in required_fields):
                    conn.rollback()
                    return jsonify({
                        "error": "Missing required fields for single item"
                    }), 400

                amount = float(data["amount"])

                if amount <= 0:
                    conn.rollback()
                    return jsonify({"error": "Amount must be positive"}), 400

                item_type = data["type"]

                if item_type not in ["income", "expense"]:
                    conn.rollback()
                    return jsonify({"error": "Invalid type"}), 400

                cur.execute("""
                    INSERT INTO transactions
                        (bill_id, description, amount, type, category, date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    bill_id,
                    data["description"],
                    amount,
                    item_type,
                    category,
                    date
                ))

                inserted_id = cur.fetchone()["id"]

            conn.commit()

            return jsonify({
                "message": "Transaction added successfully",
                "id": str(inserted_id),
                "bill_id": int(bill_id) if bill_id is not None else None
            }), 201

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    except Exception as e:
        print(f"❌ Error while adding transaction: {e}")
        return jsonify({"error": "Failed to add transaction"}), 500


@app.route("/transactions", methods=["GET"])
def get_transactions():
    try:
        bill_id = request.args.get("bill_id")

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                if bill_id and bill_id not in ("all", "", "null"):
                    cur.execute("""
                        SELECT
                            t.id,
                            t.bill_id,
                            t.description,
                            t.amount,
                            t.type,
                            t.category,
                            t.date,
                            b.name AS bill_name
                        FROM transactions t
                        LEFT JOIN bills b ON t.bill_id = b.id
                        WHERE t.bill_id = %s
                        ORDER BY t.date DESC, t.id DESC
                    """, (int(bill_id),))
                else:
                    cur.execute("""
                        SELECT
                            t.id,
                            t.bill_id,
                            t.description,
                            t.amount,
                            t.type,
                            t.category,
                            t.date,
                            b.name AS bill_name
                        FROM transactions t
                        LEFT JOIN bills b ON t.bill_id = b.id
                        ORDER BY t.date DESC, t.id DESC
                    """)

                transactions = [
                    serialize_transaction(row) for row in cur.fetchall()
                ]

            return jsonify({"transactions": transactions}), 200
        finally:
            conn.close()

    except Exception as e:
        print(f"❌ Error while retrieving transactions: {e}")
        return jsonify({"error": "Failed to fetch transactions"}), 500


@app.route("/transaction/<int:transaction_id>", methods=["PUT"])
def update_transaction(transaction_id):
    try:
        data = request.get_json(force=True)

        required_fields = ["description", "amount", "type", "date"]

        if not data or not all(key in data for key in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        amount = float(data["amount"])

        if amount <= 0:
            return jsonify({"error": "Amount must be positive"}), 400

        bill_id = data.get("bill_id")
        bill_name = (data.get("bill_name") or "").strip()

        conn = get_db_connection()

        try:
            with conn.cursor() as cur:
                if bill_name:
                    cur.execute(
                        "SELECT id FROM bills WHERE LOWER(name) = LOWER(%s) LIMIT 1",
                        (bill_name,)
                    )
                    existing = cur.fetchone()

                    if existing:
                        bill_id = existing["id"]
                    else:
                        cur.execute("""
                            INSERT INTO bills (name, category, date)
                            VALUES (%s, %s, %s)
                            RETURNING id
                        """, (
                            bill_name,
                            data.get("category", "Other"),
                            data["date"]
                        ))
                        bill_id = cur.fetchone()["id"]

                elif bill_id in ("", None, "null"):
                    bill_id = None
                else:
                    bill_id = int(bill_id)

                cur.execute("""
                    UPDATE transactions
                    SET
                        description = %s,
                        amount = %s,
                        type = %s,
                        category = %s,
                        date = %s,
                        bill_id = %s
                    WHERE id = %s
                """, (
                    data["description"],
                    amount,
                    data["type"],
                    data.get("category", "Other"),
                    data["date"],
                    bill_id,
                    transaction_id
                ))

                if cur.rowcount == 0:
                    conn.rollback()
                    return jsonify({"error": "Transaction not found"}), 404

            conn.commit()

            return jsonify({
                "message": "Transaction updated successfully"
            }), 200

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    except Exception as e:
        print(f"❌ Error updating transaction: {e}")
        return jsonify({"error": "Failed to update transaction"}), 500


@app.route("/transaction/<int:transaction_id>", methods=["DELETE"])
def delete_transaction(transaction_id):
    try:
        conn = get_db_connection()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM transactions WHERE id = %s",
                    (transaction_id,)
                )

                if cur.rowcount == 0:
                    conn.rollback()
                    return jsonify({"error": "Transaction not found"}), 404

            conn.commit()
            return jsonify({"message": "Transaction deleted"}), 200

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    except Exception as e:
        print(f"❌ Error while deleting transaction: {e}")
        return jsonify({"error": "Failed to delete transaction"}), 500


@app.route("/delete", methods=["DELETE"])
def delete_transactions():
    try:
        conn = get_db_connection()

        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM transactions")
                deleted_count = cur.rowcount

            conn.commit()

            return jsonify({
                "message": f"{deleted_count} transactions deleted."
            }), 200

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    except Exception as e:
        print(f"❌ Error while deleting transactions: {e}")
        return jsonify({"error": "Failed to delete transactions"}), 500


# ----------------- Balance & Analytics -----------------

@app.route("/balance", methods=["GET"])
def calculate_balance():
    try:
        bill_id = request.args.get("bill_id")

        conn = get_db_connection()

        try:
            with conn.cursor() as cur:
                if bill_id and bill_id not in ("all", "", "null"):
                    cur.execute("""
                        SELECT
                            COALESCE(
                                SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END),
                                0
                            ) AS total_income,
                            COALESCE(
                                SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END),
                                0
                            ) AS total_expense
                        FROM transactions
                        WHERE bill_id = %s
                    """, (int(bill_id),))
                else:
                    cur.execute("""
                        SELECT
                            COALESCE(
                                SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END),
                                0
                            ) AS total_income,
                            COALESCE(
                                SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END),
                                0
                            ) AS total_expense
                        FROM transactions
                    """)

                row = cur.fetchone()

            total_income = float(row["total_income"])
            total_expense = float(row["total_expense"])
            balance = total_income - total_expense

            return jsonify({
                "balance": balance,
                "totalIncome": total_income,
                "totalExpense": total_expense
            }), 200

        finally:
            conn.close()

    except Exception as e:
        print(f"❌ Error while calculating balance: {e}")
        return jsonify({"error": "Failed to calculate balance"}), 500


@app.route("/analytics", methods=["GET"])
def get_analytics():
    try:
        bill_id = request.args.get("bill_id")

        conn = get_db_connection()

        try:
            with conn.cursor() as cur:
                if bill_id and bill_id not in ("all", "", "null"):
                    cur.execute("""
                        SELECT
                            category,
                            COALESCE(SUM(amount), 0) AS total
                        FROM transactions
                        WHERE type = 'expense' AND bill_id = %s
                        GROUP BY category
                        ORDER BY total DESC
                    """, (int(bill_id),))
                    categories = [
                        {
                            "category": row["category"],
                            "total": float(row["total"])
                        }
                        for row in cur.fetchall()
                    ]

                    cur.execute("""
                        SELECT
                            type,
                            COALESCE(SUM(amount), 0) AS total
                        FROM transactions
                        WHERE bill_id = %s
                        GROUP BY type
                    """, (int(bill_id),))
                else:
                    cur.execute("""
                        SELECT
                            category,
                            COALESCE(SUM(amount), 0) AS total
                        FROM transactions
                        WHERE type = 'expense'
                        GROUP BY category
                        ORDER BY total DESC
                    """)
                    categories = [
                        {
                            "category": row["category"],
                            "total": float(row["total"])
                        }
                        for row in cur.fetchall()
                    ]

                    cur.execute("""
                        SELECT
                            type,
                            COALESCE(SUM(amount), 0) AS total
                        FROM transactions
                        GROUP BY type
                    """)

                totals = {
                    row["type"]: float(row["total"])
                    for row in cur.fetchall()
                }

            income = totals.get("income", 0.0)
            expense = totals.get("expense", 0.0)

            return jsonify({
                "categories": categories,
                "income": income,
                "expense": expense,
                "balance": income - expense
            }), 200

        finally:
            conn.close()

    except Exception as e:
        print(f"❌ Error getting analytics: {e}")
        return jsonify({"error": "Failed to get analytics"}), 500


@app.route("/reports", methods=["GET"])
def get_reports():
    try:
        conn = get_db_connection()

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        id,
                        bill_id,
                        description,
                        amount,
                        type,
                        category,
                        date
                    FROM transactions
                    ORDER BY date DESC, id DESC
                """)

                transactions = [
                    serialize_transaction(row) for row in cur.fetchall()
                ]

            return jsonify({"transactions": transactions}), 200

        finally:
            conn.close()

    except Exception as e:
        return jsonify({
            "error": f"Failed to generate reports: {str(e)}"
        }), 500


# Initialize tables when the service starts.
init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

import os
import sys
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Ensure safe UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allows Netlify and local origins

# Database configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "finance_tracker.db")
DATABASE_PATH = os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Initialize the SQLite database with bills and transactions tables."""
    conn = get_db_connection()
    try:
        with conn:
            # 1. Create bills table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT NOT NULL DEFAULT 'Other',
                    date TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Create transactions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_id INTEGER,
                    description TEXT NOT NULL,
                    amount REAL NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                    category TEXT NOT NULL DEFAULT 'Other',
                    date TEXT NOT NULL,
                    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
                );
            """)

            # Check if bill_id column exists in transactions (in case table was created previously without it)
            cursor = conn.execute("PRAGMA table_info(transactions);")
            columns = [row["name"] for row in cursor.fetchall()]
            if "bill_id" not in columns:
                conn.execute("ALTER TABLE transactions ADD COLUMN bill_id INTEGER REFERENCES bills(id) ON DELETE CASCADE;")
                print("✅ Added 'bill_id' column to transactions table")

            # Clean up / migrate any old 'Bills' category to 'Shopping'
            conn.execute("UPDATE transactions SET category = 'Shopping' WHERE category = 'Bills';")
            conn.execute("UPDATE bills SET category = 'Shopping' WHERE category = 'Bills';")

        print(f"✅ SQLite Database initialized at: {DATABASE_PATH}")
    except Exception as e:
        print(f"❌ SQLite initialization error: {e}")
    finally:
        conn.close()

# Initialize database tables on app load
init_db()

def serialize_transaction(row):
    """Serialize a SQLite Row to a dictionary with both 'id' and '_id' for frontend compatibility."""
    row_dict = dict(row)
    row_dict["_id"] = str(row_dict["id"])
    return row_dict

# ----------------- Root & Health -----------------

@app.route('/')
def home():
    print("📍 Home route accessed")
    return jsonify({"message": "Welcome to the Personal Finance Tracker API!"})

# ----------------- Bills Management -----------------

@app.route('/bills', methods=['GET'])
def get_bills():
    """List all stored bills with separate total_expense, total_income, and embedded items."""
    print("📍 Get bills route accessed")
    try:
        conn = get_db_connection()
        try:
            query = """
                SELECT 
                    b.id, b.name, b.category, b.date, b.created_at,
                    COUNT(t.id) AS item_count,
                    COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) AS total_expense,
                    COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) AS total_income,
                    COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE -t.amount END), 0) AS net_balance
                FROM bills b
                LEFT JOIN transactions t ON t.bill_id = b.id
                GROUP BY b.id
                ORDER BY b.date DESC, b.id DESC
            """
            cursor = conn.execute(query)
            bills = []
            for row in cursor.fetchall():
                b = dict(row)
                b["total_amount"] = b["total_expense"]  # default display amount
                item_cur = conn.execute("SELECT * FROM transactions WHERE bill_id = ? ORDER BY id ASC", (b["id"],))
                b["items"] = [serialize_transaction(r) for r in item_cur.fetchall()]
                bills.append(b)
        finally:
            conn.close()

        print(f"📋 Returning {len(bills)} bills")
        return jsonify({"bills": bills}), 200
    except Exception as e:
        print(f"❌ Error fetching bills: {e}")
        return jsonify({"error": "Failed to fetch bills"}), 500

@app.route('/bills', methods=['POST'])
def create_bill():
    """Create a new bill with a name, category, and date (no description needed)."""
    print("📍 Create bill route accessed")
    try:
        data = request.get_json(force=True)
        if not data or not data.get("name"):
            return jsonify({"error": "Bill name is required"}), 400

        name = data["name"].strip()
        category = data.get("category", "Other")
        date = data.get("date", "")
        if not date:
            from datetime import date as d
            date = d.today().isoformat()

        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.execute(
                    "INSERT INTO bills (name, category, date) VALUES (?, ?, ?)",
                    (name, category, date)
                )
                bill_id = cursor.lastrowid
            print(f"✅ Bill created: '{name}' (ID: {bill_id})")
            return jsonify({"message": "Bill created successfully", "id": bill_id, "name": name}), 201
        finally:
            conn.close()
    except Exception as e:
        print(f"❌ Error creating bill: {e}")
        return jsonify({"error": "Failed to create bill"}), 500

@app.route('/bills/<int:bill_id>', methods=['GET'])
def get_bill_detail(bill_id):
    """Retrieve full details of a bill along with its items and separately calculated expense and income."""
    print(f"📍 Get bill details: ID {bill_id}")
    try:
        conn = get_db_connection()
        try:
            cursor = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,))
            bill_row = cursor.fetchone()
            if not bill_row:
                return jsonify({"error": "Bill not found"}), 404

            bill = dict(bill_row)
            items_cursor = conn.execute(
                "SELECT * FROM transactions WHERE bill_id = ? ORDER BY date DESC, id DESC",
                (bill_id,)
            )
            items = [serialize_transaction(r) for r in items_cursor.fetchall()]
            
            # Separate income and expense calculations for this bill
            total_expense = sum(item["amount"] for item in items if item["type"] == "expense")
            total_income = sum(item["amount"] for item in items if item["type"] == "income")
            net_balance = total_income - total_expense

            bill["total_expense"] = total_expense
            bill["total_income"] = total_income
            bill["net_balance"] = net_balance
            bill["total_amount"] = total_expense  # For backward-compatibility
            bill["items"] = items
        finally:
            conn.close()

        return jsonify({"bill": bill}), 200
    except Exception as e:
        print(f"❌ Error retrieving bill details: {e}")
        return jsonify({"error": "Failed to retrieve bill details"}), 500

@app.route('/bills/<int:bill_id>', methods=['PUT'])
def update_bill(bill_id):
    """Update details of a bill (name, category, date)."""
    print(f"📍 Update bill: ID {bill_id}")
    try:
        data = request.get_json(force=True)
        if not data or not data.get("name"):
            return jsonify({"error": "Bill name is required"}), 400

        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE bills 
                    SET name = ?, category = ?, date = ?
                    WHERE id = ?
                    """,
                    (data["name"].strip(), data.get("category", "Other"), data.get("date", ""), bill_id)
                )
                if cursor.rowcount == 0:
                    return jsonify({"error": "Bill not found"}), 404
            print(f"✅ Bill updated: ID {bill_id}")
            return jsonify({"message": "Bill updated successfully"}), 200
        finally:
            conn.close()
    except Exception as e:
        print(f"❌ Error updating bill: {e}")
        return jsonify({"error": "Failed to update bill"}), 500

@app.route('/bills/<int:bill_id>', methods=['DELETE'])
def delete_bill(bill_id):
    """Delete a bill and all its associated line items (cascade delete)."""
    print(f"📍 Delete bill: ID {bill_id}")
    try:
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("DELETE FROM transactions WHERE bill_id = ?", (bill_id,))
                cursor = conn.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
                if cursor.rowcount == 0:
                    return jsonify({"error": "Bill not found"}), 404
            print(f"✅ Bill and associated items deleted: ID {bill_id}")
            return jsonify({"message": "Bill and its items deleted successfully"}), 200
        finally:
            conn.close()
    except Exception as e:
        print(f"❌ Error deleting bill: {e}")
        return jsonify({"error": "Failed to delete bill"}), 500

# ----------------- Transactions Management -----------------

@app.route('/add', methods=['POST'])
def add_transaction():
    """Add a single transaction or multiple items in a single bill at once."""
    print("📍 Add transaction/items route accessed")
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "No data provided"}), 400

        bill_name = (data.get("bill_name") or "").strip()
        bill_id = data.get("bill_id")
        date = data.get("date") or ""
        if not date:
            from datetime import date as d
            date = d.today().isoformat()
        category = data.get("category", "Other")

        conn = get_db_connection()
        try:
            with conn:
                # 1. Resolve or create the bill if bill_name is provided
                if bill_name:
                    cur = conn.execute("SELECT id FROM bills WHERE LOWER(name) = LOWER(?)", (bill_name,))
                    existing = cur.fetchone()
                    if existing:
                        bill_id = existing["id"]
                    else:
                        new_b_cur = conn.execute(
                            "INSERT INTO bills (name, category, date) VALUES (?, ?, ?)",
                            (bill_name, category, date)
                        )
                        bill_id = new_b_cur.lastrowid
                        print(f"✅ Auto-created new bill: '{bill_name}' (ID: {bill_id})")
                elif bill_id in ("", None, "null"):
                    bill_id = None
                else:
                    bill_id = int(bill_id)

                # 2. Check if multiple items are submitted
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

                        cur = conn.execute(
                            """
                            INSERT INTO transactions (bill_id, description, amount, type, category, date)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (bill_id, item_desc, item_amount, item_type, item_cat, item_date)
                        )
                        inserted_ids.append(cur.lastrowid)

                    print(f"✅ Added {len(inserted_ids)} items to Bill ID: {bill_id}")
                    return jsonify({
                        "message": f"{len(inserted_ids)} items added successfully",
                        "bill_id": bill_id,
                        "inserted_ids": inserted_ids
                    }), 201

                # 3. Otherwise handle single item
                required_fields = ["description", "amount", "type"]
                if not all(key in data for key in required_fields):
                    return jsonify({"error": "Missing required fields for single item"}), 400

                amount = float(data["amount"])
                if amount <= 0:
                    return jsonify({"error": "Amount must be positive"}), 400

                item_type = data["type"]
                if item_type not in ["income", "expense"]:
                    return jsonify({"error": "Invalid type"}), 400

                cursor = conn.execute(
                    """
                    INSERT INTO transactions (bill_id, description, amount, type, category, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (bill_id, data["description"], amount, item_type, category, date)
                )
                inserted_id = cursor.lastrowid
            print(f"✅ Transaction added: ID {inserted_id} (Bill ID: {bill_id})")
            return jsonify({
                "message": "Transaction added successfully", 
                "id": str(inserted_id),
                "bill_id": bill_id
            }), 201
        finally:
            conn.close()
    except Exception as e:
        print(f"❌ Error while adding transaction: {e}")
        return jsonify({"error": "Failed to add transaction"}), 500

@app.route('/transactions', methods=['GET'])
def get_transactions():
    """Get all transactions or filter by bill_id, including linked bill name."""
    print("📍 Transactions route accessed")
    try:
        bill_id = request.args.get('bill_id')
        conn = get_db_connection()
        try:
            if bill_id and bill_id not in ('all', '', 'null'):
                query = """
                    SELECT t.*, b.name AS bill_name
                    FROM transactions t
                    LEFT JOIN bills b ON t.bill_id = b.id
                    WHERE t.bill_id = ?
                    ORDER BY t.date DESC, t.id DESC
                """
                cursor = conn.execute(query, (bill_id,))
            else:
                query = """
                    SELECT t.*, b.name AS bill_name
                    FROM transactions t
                    LEFT JOIN bills b ON t.bill_id = b.id
                    ORDER BY t.date DESC, t.id DESC
                """
                cursor = conn.execute(query)

            transactions = [serialize_transaction(row) for row in cursor.fetchall()]
        finally:
            conn.close()

        print(f"📊 Returning {len(transactions)} transactions")
        return jsonify({"transactions": transactions}), 200
    except Exception as e:
        print(f"❌ Error while retrieving transactions: {e}")
        return jsonify({"error": "Failed to fetch transactions"}), 500

@app.route('/transaction/<int:transaction_id>', methods=['PUT'])
def update_transaction(transaction_id):
    """Modify an existing transaction/line item."""
    print(f"📍 Update transaction route: ID {transaction_id}")
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
            with conn:
                if bill_name:
                    cur = conn.execute("SELECT id FROM bills WHERE LOWER(name) = LOWER(?)", (bill_name,))
                    existing = cur.fetchone()
                    if existing:
                        bill_id = existing["id"]
                    else:
                        new_b_cur = conn.execute(
                            "INSERT INTO bills (name, category, date) VALUES (?, ?, ?)",
                            (bill_name, data.get("category", "Other"), data["date"])
                        )
                        bill_id = new_b_cur.lastrowid
                elif bill_id in ("", None, "null"):
                    bill_id = None
                else:
                    bill_id = int(bill_id)

                cursor = conn.execute(
                    """
                    UPDATE transactions
                    SET description = ?, amount = ?, type = ?, category = ?, date = ?, bill_id = ?
                    WHERE id = ?
                    """,
                    (data["description"], amount, data["type"], 
                     data.get("category", "Other"), data["date"], bill_id, transaction_id)
                )
                if cursor.rowcount == 0:
                    return jsonify({"error": "Transaction not found"}), 404
            print(f"✅ Transaction updated: ID {transaction_id}")
            return jsonify({"message": "Transaction updated successfully"}), 200
        finally:
            conn.close()
    except Exception as e:
        print(f"❌ Error updating transaction: {e}")
        return jsonify({"error": "Failed to update transaction"}), 500

@app.route('/transaction/<transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    print(f"📍 Delete transaction route accessed: {transaction_id}")
    try:
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
                if cursor.rowcount == 0:
                    return jsonify({"error": "Transaction not found"}), 404
            print(f"✅ Transaction deleted: ID {transaction_id}")
            return jsonify({"message": "Transaction deleted"}), 200
        finally:
            conn.close()
    except Exception as e:
        print(f"❌ Error while deleting transaction: {e}")
        return jsonify({"error": "Failed to delete transaction"}), 500

@app.route('/delete', methods=['DELETE'])
def delete_transactions():
    print("📍 Delete all transactions route accessed")
    try:
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM transactions")
                deleted_count = cursor.rowcount
            print(f"✅ Deleted {deleted_count} transactions")
            return jsonify({"message": f"{deleted_count} transactions deleted."}), 200
        finally:
            conn.close()
    except Exception as e:
        print(f"❌ Error while deleting transactions: {e}")
        return jsonify({"error": "Failed to delete transactions"}), 500

# ----------------- Live Analytics & Balance -----------------

@app.route('/balance', methods=['GET'])
def calculate_balance():
    print("📍 Balance route accessed")
    try:
        bill_id = request.args.get('bill_id')
        conn = get_db_connection()
        try:
            if bill_id and bill_id not in ('all', '', 'null'):
                cursor = conn.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) AS total_income,
                        COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) AS total_expense
                    FROM transactions
                    WHERE bill_id = ?
                """, (bill_id,))
            else:
                cursor = conn.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) AS total_income,
                        COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) AS total_expense
                    FROM transactions
                """)
            row = cursor.fetchone()
            total_income = float(row["total_income"])
            total_expense = float(row["total_expense"])
            balance = total_income - total_expense
        finally:
            conn.close()

        print(f"💰 Balance: {balance}, Income: {total_income}, Expense: {total_expense}")
        return jsonify({
            "balance": balance,
            "totalIncome": total_income,
            "totalExpense": total_expense
        }), 200
    except Exception as e:
        print(f"❌ Error while calculating balance: {e}")
        return jsonify({"error": "Failed to calculate balance"}), 500

@app.route('/analytics', methods=['GET'])
def get_analytics():
    """Returns real-time aggregated data for live charts on the right side of the dashboard."""
    print("📍 Analytics route accessed")
    try:
        bill_id = request.args.get('bill_id')
        conn = get_db_connection()
        try:
            # 1. Expense Breakdown by Category
            if bill_id and bill_id not in ('all', '', 'null'):
                cat_cur = conn.execute("""
                    SELECT category, COALESCE(SUM(amount), 0) AS total
                    FROM transactions
                    WHERE type = 'expense' AND bill_id = ?
                    GROUP BY category
                    ORDER BY total DESC
                """, (bill_id,))
                
                type_cur = conn.execute("""
                    SELECT type, COALESCE(SUM(amount), 0) AS total
                    FROM transactions
                    WHERE bill_id = ?
                    GROUP BY type
                """, (bill_id,))
            else:
                cat_cur = conn.execute("""
                    SELECT category, COALESCE(SUM(amount), 0) AS total
                    FROM transactions
                    WHERE type = 'expense'
                    GROUP BY category
                    ORDER BY total DESC
                """)
                
                type_cur = conn.execute("""
                    SELECT type, COALESCE(SUM(amount), 0) AS total
                    FROM transactions
                    GROUP BY type
                """)

            categories = [{"category": row["category"], "total": float(row["total"])} for row in cat_cur.fetchall()]
            totals = {row["type"]: float(row["total"]) for row in type_cur.fetchall()}
            income = totals.get("income", 0.0)
            expense = totals.get("expense", 0.0)
        finally:
            conn.close()

        return jsonify({
            "categories": categories,
            "income": income,
            "expense": expense,
            "balance": income - expense
        }), 200
    except Exception as e:
        print(f"❌ Error getting analytics: {e}")
        return jsonify({"error": "Failed to get analytics"}), 500

@app.route('/reports', methods=['GET'])
def get_reports():
    print("📍 Reports route accessed")
    try:
        conn = get_db_connection()
        try:
            cursor = conn.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC")
            transactions = [serialize_transaction(row) for row in cursor.fetchall()]
        finally:
            conn.close()
        return jsonify({"transactions": transactions}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to generate reports: {str(e)}"}), 500

# Startup route display
print("🚀 Starting Flask app...")
with app.test_request_context():
    print("📋 Registered routes:")
    for rule in app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        print(f"   {rule.endpoint}: {rule} ({methods})")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
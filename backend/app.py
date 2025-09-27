from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
from dateutil import parser
from dateutil.rrule import rrule, DAILY, MONTHLY

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# MongoDB Configuration
MONGO_URI = "mongodb+srv://likhil:sai123456@cluster0.njvur.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client.finance_tracker
    transactions_collection = db.transactions
    client.server_info()
    print("✅ Connected to MongoDB")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

def serialize_transaction(transaction):
    transaction["_id"] = str(transaction["_id"])
    return transaction

@app.route('/')
def home():
    print("📍 Home route accessed")
    return jsonify({"message": "Welcome to the Personal Finance Tracker API!"})

@app.route('/add', methods=['POST'])
def add_transaction():
    print("📍 Add transaction route accessed")
    try:
        data = request.get_json(force=True)
        required_fields = ["description", "amount", "type", "category", "date"]
        if not data or not all(key in data for key in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        if data["type"] not in ["income", "expense"] or data["category"] not in ["Food", "Transport", "Salary", "Entertainment", "Bills", "Other"]:
            return jsonify({"error": "Invalid type or category"}), 400

        if data["amount"] <= 0:
            return jsonify({"error": "Amount must be positive"}), 400

        result = transactions_collection.insert_one(data)
        print(f"✅ Transaction added: {str(result.inserted_id)}")
        return jsonify({"message": "Transaction added successfully", "id": str(result.inserted_id)}), 201
    except Exception as e:
        print(f"❌ Error while adding transaction: {e}")
        return jsonify({"error": "Failed to add transaction"}), 500

@app.route('/transactions', methods=['GET'])
def get_transactions():
    print("📍 Transactions route accessed")
    try:
        transactions = list(transactions_collection.find({}))
        transactions = [serialize_transaction(t) for t in transactions]
        print(f"📊 Returning {len(transactions)} transactions")
        return jsonify({"transactions": transactions}), 200
    except Exception as e:
        print(f"❌ Error while retrieving transactions: {e}")
        return jsonify({"error": "Failed to fetch transactions"}), 500

@app.route('/transaction/<transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    print(f"📍 Delete transaction route accessed: {transaction_id}")
    try:
        result = transactions_collection.delete_one({"_id": ObjectId(transaction_id)})
        if result.deleted_count == 0:
            return jsonify({"error": "Transaction not found"}), 404
        print(f"✅ Transaction deleted: {transaction_id}")
        return jsonify({"message": "Transaction deleted"}), 200
    except Exception as e:
        print(f"❌ Error while deleting transaction: {e}")
        return jsonify({"error": "Failed to delete transaction"}), 500

@app.route('/delete', methods=['DELETE'])
def delete_transactions():
    print("📍 Delete all transactions route accessed")
    try:
        result = transactions_collection.delete_many({})
        print(f"✅ Deleted {result.deleted_count} transactions")
        return jsonify({"message": f"{result.deleted_count} transactions deleted."}), 200
    except Exception as e:
        print(f"❌ Error while deleting transactions: {e}")
        return jsonify({"error": "Failed to delete transactions"}), 500

@app.route('/balance', methods=['GET'])
def calculate_balance():
    print("📍 Balance route accessed")
    try:
        transactions = list(transactions_collection.find({}))
        total_income = sum(t["amount"] for t in transactions if t["type"] == "income")
        total_expense = sum(t["amount"] for t in transactions if t["type"] == "expense")
        balance = total_income - total_expense

        print(f"💰 Balance: {balance}, Income: {total_income}, Expense: {total_expense}")
        return jsonify({
            "balance": balance,
            "totalIncome": total_income,
            "totalExpense": total_expense
        }), 200
    except Exception as e:
        print(f"❌ Error while calculating balance: {e}")
        return jsonify({"error": "Failed to calculate balance"}), 500

@app.route('/reports', methods=['GET'])
def get_reports():
    print("📍 Reports route accessed")
    try:
        period = request.args.get('period', 'monthly')
        print(f"📈 Generating reports for period: {period}")
        if period != 'monthly':
            return jsonify({"error": "Only monthly period supported"}), 400

        transactions = list(transactions_collection.find({}))
        print(f"📊 Processing {len(transactions)} transactions for reports")

        # Expense by Category (exclude Salary for expenses)
        expense_by_category = [
            {"category": cat, "total": sum(t["amount"] for t in transactions if t["type"] == "expense" and t["category"] == cat)}
            for cat in ["Food", "Transport", "Entertainment", "Bills", "Other"]
        ]
        expense_by_category = [item for item in expense_by_category if item["total"] > 0]
        print(f"📈 Expense by category: {expense_by_category}")

        # Balance Over Time (last 30 days)
        today = datetime.now().date()
        start_date = today - timedelta(days=30)
        balance_over_time = []
        current_balance = 0
        for dt in rrule(DAILY, dtstart=start_date, until=today):
            date_str = dt.strftime("%Y-%m-%d")
            daily_income = sum(t["amount"] for t in transactions if t["type"] == "income" and parser.parse(t["date"]).date() == dt.date())
            daily_expense = sum(t["amount"] for t in transactions if t["type"] == "expense" and parser.parse(t["date"]).date() == dt.date())
            current_balance += daily_income - daily_expense
            balance_over_time.append({"date": date_str, "balance": current_balance})
        print(f"📈 Balance over time: {len(balance_over_time)} days")

        # Monthly Income vs Expenses (last 6 months)
        monthly_summary = []
        for dt in rrule(MONTHLY, dtstart=today - timedelta(days=180), until=today):
            month_str = dt.strftime("%Y-%m")
            monthly_income = sum(t["amount"] for t in transactions if t["type"] == "income" and t["date"].startswith(month_str))
            monthly_expense = sum(t["amount"] for t in transactions if t["type"] == "expense" and t["date"].startswith(month_str))
            monthly_summary.append({"month": month_str, "income": monthly_income, "expense": monthly_expense})
        print(f"📈 Monthly summary: {len(monthly_summary)} months")

        response = {
            "expenseByCategory": expense_by_category,
            "balanceOverTime": balance_over_time,
            "monthlySummary": monthly_summary
        }
        print(f"✅ Reports generated: {response}")
        return jsonify(response), 200
    except Exception as e:
        print(f"❌ Error while generating reports: {e}")
        return jsonify({"error": "Failed to generate reports"}), 500

# Log all registered routes on startup
print("🚀 Starting Flask app...")
with app.test_request_context():
    print("📋 Registered routes:")
    for rule in app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        print(f"   {rule.endpoint}: {rule} ({methods})")

if __name__ == '__main__':
    app.run(debug=True)
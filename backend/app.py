from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
import os  # For PORT binding

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allows Netlify origin

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
        required_fields = ["description", "amount", "type", "date"]
        if not data or not all(key in data for key in required_fields):
            return jsonify({"error": "Missing required fields"}), 400

        if data["type"] not in ["income", "expense"]:
            return jsonify({"error": "Invalid type"}), 400

        if data["amount"] <= 0:
            return jsonify({"error": "Amount must be positive"}), 400

        # Ensure category exists, default to "Other" if missing
        data["category"] = data.get("category", "Other")
        if data["category"] not in ["Food", "Transport", "Salary", "Entertainment", "Bills", "Other"]:
            data["category"] = "Other"

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
        transactions = [serialize_transaction(t) for t in transactions]
        print(f"📊 Returning {len(transactions)} transactions for reports")
        return jsonify({"transactions": transactions}), 200
    except Exception as e:
        print(f"❌ Error while generating reports: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to generate reports: {str(e)}"}), 500

# Log all registered routes on startup
print("🚀 Starting Flask app...")
with app.test_request_context():
    print("📋 Registered routes:")
    for rule in app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        print(f"   {rule.endpoint}: {rule} ({methods})")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)  # Bind to 0.0.0.0 for Render
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
import os
import jwt
import bcrypt
import random
import string
from dotenv import load_dotenv
from functools import wraps

# Load environment variables
load_dotenv()
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://finatrack.netlify.app"}})

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-key")
MONGO_URI = os.getenv("MONGO_URI")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client.finance_tracker
    users_collection = db.users
    transactions_collection = db.transactions
    client.server_info()
    print("✅ Connected to MongoDB")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")
    exit(1)

def generate_transcode(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        transcode = request.headers.get('X-Transcode')
        if not transcode:
            return jsonify({"error": "Transcode required"}), 401
        user = users_collection.find_one({"transcode": transcode})
        if not user:
            return jsonify({"error": "Invalid transcode"}), 401
        request.user = str(user["_id"])
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def home():
    print("📍 Home route accessed")
    return jsonify({"message": "Welcome to the Personal Finance Tracker API!"})

@app.route('/validate', methods=['POST'])
def validate_transcode():
    print("📍 Validate transcode route accessed")
    try:
        data = request.get_json(force=True)
        transcode = data.get('transcode')

        if not transcode:
            return jsonify({"error": "Transcode is required"}), 400

        user = users_collection.find_one({"transcode": transcode})
        if not user:
            # Generate a new transcode and user if not found
            new_transcode = generate_transcode()
            user_id = users_collection.insert_one({"transcode": new_transcode}).inserted_id
            print(f"✅ New user created with transcode: {new_transcode}")
            return jsonify({"transcode": new_transcode, "user_id": str(user_id)}), 201
        else:
            print(f"✅ Transcode validated for user: {str(user['_id'])}")
            return jsonify({"user_id": str(user["_id"])}), 200
    except Exception as e:
        print(f"❌ Error while validating transcode: {e}")
        return jsonify({"error": "Validation failed"}), 500

@app.route('/add', methods=['POST'])
@require_auth
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

        data["category"] = data.get("category", "Other")
        if data["category"] not in ["Food", "Transport", "Salary", "Entertainment", "Bills", "Other"]:
            data["category"] = "Other"

        data["user_id"] = request.user
        result = transactions_collection.insert_one(data)
        print(f"✅ Transaction added: {str(result.inserted_id)}")
        return jsonify({"message": "Transaction added successfully", "id": str(result.inserted_id)}), 201
    except Exception as e:
        print(f"❌ Error while adding transaction: {e}")
        return jsonify({"error": "Failed to add transaction"}), 500

@app.route('/transactions', methods=['GET'])
@require_auth
def get_transactions():
    print("📍 Transactions route accessed")
    try:
        transactions = list(transactions_collection.find({"user_id": request.user}))
        transactions = [serialize_transaction(t) for t in transactions]
        print(f"📊 Returning {len(transactions)} transactions")
        return jsonify({"transactions": transactions}), 200
    except Exception as e:
        print(f"❌ Error while retrieving transactions: {e}")
        return jsonify({"error": "Failed to fetch transactions"}), 500

@app.route('/transaction/<transaction_id>', methods=['DELETE'])
@require_auth
def delete_transaction(transaction_id):
    print(f"📍 Delete transaction route accessed: {transaction_id}")
    try:
        result = transactions_collection.delete_one({"_id": ObjectId(transaction_id), "user_id": request.user})
        if result.deleted_count == 0:
            return jsonify({"error": "Transaction not found or unauthorized"}), 404
        print(f"✅ Transaction deleted: {transaction_id}")
        return jsonify({"message": "Transaction deleted"}), 200
    except Exception as e:
        print(f"❌ Error while deleting transaction: {e}")
        return jsonify({"error": "Failed to delete transaction"}), 500

@app.route('/delete', methods=['DELETE'])
@require_auth
def delete_transactions():
    print("📍 Delete all transactions route accessed")
    try:
        result = transactions_collection.delete_many({"user_id": request.user})
        print(f"✅ Deleted {result.deleted_count} transactions")
        return jsonify({"message": f"{result.deleted_count} transactions deleted."}), 200
    except Exception as e:
        print(f"❌ Error while deleting transactions: {e}")
        return jsonify({"error": "Failed to delete transactions"}), 500

@app.route('/balance', methods=['GET'])
@require_auth
def calculate_balance():
    print("📍 Balance route accessed")
    try:
        transactions = list(transactions_collection.find({"user_id": request.user}))
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

def serialize_transaction(transaction):
    transaction["_id"] = str(transaction["_id"])
    return transaction

# Log all registered routes on startup
print("🚀 Starting Flask app...")
with app.test_request_context():
    print("📋 Registered routes:")
    for rule in app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        print(f"   {rule.endpoint}: {rule} ({methods})")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
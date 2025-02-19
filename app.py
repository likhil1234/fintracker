from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow CORS for all origins

# ✅ MongoDB Configuration
MONGO_URI = "mongodb+srv://likhil:sai123456@cluster0.njvur.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)  # Timeout if MongoDB is unreachable
    db = client.finance_tracker  # Database name
    transactions_collection = db.transactions  # Collection name
    client.server_info()  # Test MongoDB connection
    print("✅ Connected to MongoDB")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

# ✅ API Routes
@app.route('/')
def home():
    return jsonify({"message": "Welcome to the Personal Finance Tracker API!"})

@app.route('/add', methods=['POST'])
def add_transaction():
    """
    Add a new transaction to the database.
    """
    try:
        data = request.get_json(force=True)
        print("📥 Received data:", data)  # Debugging

        # Validate data
        if not data or not all(key in data for key in ("description", "amount", "type", "date")):
            return jsonify({"error": "Invalid data format"}), 400

        # Insert transaction into database
        transaction_id = transactions_collection.insert_one(data).inserted_id
        return jsonify({"message": "Transaction added successfully", "id": str(transaction_id)}), 201
    except Exception as e:
        print(f"❌ Error while adding transaction: {e}")
        return jsonify({"error": "Failed to add transaction"}), 500

@app.route('/transactions', methods=['GET'])
def get_transactions():
    """
    Retrieve all transactions from the database.
    """
    try:
        transactions = list(transactions_collection.find({}, {"_id": 0}))  # Exclude MongoDB's _id
        return jsonify({"transactions": transactions}), 200
    except Exception as e:
        print(f"❌ Error while retrieving transactions: {e}")
        return jsonify({"error": "Failed to fetch transactions"}), 500

@app.route('/delete', methods=['DELETE'])
def delete_transactions():
    """
    Delete all transactions from the database.
    """
    try:
        result = transactions_collection.delete_many({})
        return jsonify({"message": f"{result.deleted_count} transactions deleted."}), 200
    except Exception as e:
        print(f"❌ Error while deleting transactions: {e}")
        return jsonify({"error": "Failed to delete transactions"}), 500

@app.route('/balance', methods=['GET'])
def calculate_balance():
    """
    Calculate and return the total balance, income, and expenses.
    """
    try:
        transactions = list(transactions_collection.find({}, {"_id": 0}))
        total_income = sum(txn["amount"] for txn in transactions if txn["type"] == "income")
        total_expense = sum(txn["amount"] for txn in transactions if txn["type"] == "expense")
        balance = total_income - total_expense

        return jsonify({
            "balance": balance,
            "totalIncome": total_income,
            "totalExpense": total_expense
        }), 200
    except Exception as e:
        print(f"❌ Error while calculating balance: {e}")
        return jsonify({"error": "Failed to calculate balance"}), 500

# ✅ Run the app
if __name__ == '__main__':
    app.run(debug=True)

const API_BASE = "https://fintracker-afa0.onrender.com";

async function loadTransactions() {
    try {
        const res = await fetch(`${API_BASE}/transactions`);
        const data = await res.json();

        const transactionList = document.getElementById('transactionList');
        transactionList.innerHTML = "";

        data.transactions.forEach(txn => {
            const li = document.createElement('li');
            li.classList.add('list-group-item', 'd-flex', 'justify-content-between', 'align-items-center');
            li.innerHTML = `
                ${txn.date}: ${txn.type === 'income' ? '+' : '-'}Rs${txn.amount} (${txn.description}, ${txn.category})
                <button class="btn btn-danger btn-sm" onclick="deleteTransaction('${txn._id}')">Delete</button>
            `;
            transactionList.appendChild(li);
        });
    } catch (err) {
        console.error("❌ Failed to load transactions", err);
    }
}

async function loadBalance() {
    try {
        const res = await fetch(`${API_BASE}/balance`);
        const data = await res.json();
        document.getElementById('balance').textContent = `Rs${data.balance.toFixed(2)}`;
        document.getElementById('totalIncome').textContent = `Rs${data.totalIncome.toFixed(2)}`;
        document.getElementById('totalExpense').textContent = `Rs${data.totalExpense.toFixed(2)}`;
    } catch (err) {
        console.error("❌ Failed to load balance", err);
    }
}

async function deleteTransaction(id) {
    if (!confirm("Are you sure you want to delete this transaction?")) return;

    try {
        const res = await fetch(`${API_BASE}/transaction/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error("Delete failed");
        loadTransactions();
        loadBalance();
        loadReports();
    } catch (err) {
        console.error("❌ Error deleting transaction", err);
    }
}

document.getElementById('transactionForm').addEventListener('submit', async function (e) {
    e.preventDefault();

    const description = document.getElementById('description').value;
    const amount = parseFloat(document.getElementById('amount').value);
    const type = document.getElementById('type').value;
    const category = document.getElementById('category').value;
    const date = document.getElementById('date').value;

    const transaction = { description, amount, type, category, date };

    try {
        const response = await fetch(`${API_BASE}/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(transaction)
        });

        if (!response.ok) throw new Error('Failed to add transaction');

        document.getElementById('transactionForm').reset();
        loadTransactions();
        loadBalance();
        loadReports();
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to add transaction. Please try again.');
    }
});

let expenseVsIncomeChart;

async function loadReports() {
    try {
        const res = await fetch(`${API_BASE}/transactions`); // Fetch all transactions
        if (!res.ok) {
            const errorText = await res.text();
            console.error("❌ API Error Response:", errorText);
            throw new Error(`HTTP ${res.status}: ${errorText.substring(0, 100)}...`);
        }
        const data = await res.json();

        // Sort transactions by date to find the last transaction
        const sortedTransactions = data.transactions.sort((a, b) => new Date(b.date) - new Date(a.date));
        const lastTransactionDate = sortedTransactions.length ? sortedTransactions[0].date : new Date().toISOString().split('T')[0];

        // Calculate cumulative totals up to the last transaction
        const totals = sortedTransactions.reduce((acc, txn) => {
            if (new Date(txn.date) <= new Date(lastTransactionDate)) {
                acc.income += txn.type === 'income' ? txn.amount : 0;
                acc.expense += txn.type === 'expense' ? txn.amount : 0;
            }
            return acc;
        }, { income: 0, expense: 0 });

        // Bar Chart: Expense vs Income
        const ctx = document.getElementById('expenseVsIncomeChart').getContext('2d');
        if (expenseVsIncomeChart) expenseVsIncomeChart.destroy();
        expenseVsIncomeChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Up to Last Transaction (' + lastTransactionDate + ')'],
                datasets: [
                    {
                        label: 'Income',
                        data: [totals.income],
                        backgroundColor: '#36A2EB'
                    },
                    {
                        label: 'Expense',
                        data: [totals.expense],
                        backgroundColor: '#FF6384'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false, // Allows custom size control
                aspectRatio: 2, // Sets a fixed aspect ratio (width:height = 2:1)
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Amount (Rs)' },
                        ticks: { callback: value => `Rs${value}` } // Format y-axis labels
                    },
                    x: { title: { display: true, text: 'Date' } }
                },
                plugins: { legend: { position: 'top' } },
                layout: { padding: { top: 10, bottom: 10, left: 10, right: 10 } } // Add padding for stability
            }
        });
    } catch (err) {
        console.error("❌ Failed to load reports", err);
    }
}

// Load data when page starts and on tab switch
document.addEventListener('DOMContentLoaded', () => {
    loadTransactions();
    loadBalance();
    loadReports();

    // Refresh charts when switching to Reports tab
    document.querySelectorAll('.nav-link').forEach(tab => {
        tab.addEventListener('shown.bs.tab', () => {
            if (document.getElementById('reports').classList.contains('active')) {
                loadReports();
            }
        });
    });
});
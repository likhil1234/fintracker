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

let expensePieChart, balanceLineChart, monthlyBarChart;

async function loadReports() {
    try {
        const res = await fetch(`${API_BASE}/reports?period=monthly`);
        const data = await res.json();

        // Ensure tab is active and canvases exist
        const reportsTab = document.getElementById('reports');
        if (!reportsTab || !document.getElementById('expensePieChart')) {
            console.warn("Reports tab or canvases not found");
            return;
        }

        // Pie Chart: Expense by Category
        const expenseCtx = document.getElementById('expensePieChart').getContext('2d');
        if (expensePieChart) expensePieChart.destroy();
        expensePieChart = new Chart(expenseCtx, {
            type: 'pie',
            data: {
                labels: data.expenseByCategory.length ? data.expenseByCategory.map(item => item.category) : ['No Data'],
                datasets: [{
                    data: data.expenseByCategory.length ? data.expenseByCategory.map(item => item.total) : [1],
                    backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40']
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'top' } },
                maintainAspectRatio: false
            }
        });

        // Line Chart: Balance Over Time
        const balanceCtx = document.getElementById('balanceLineChart').getContext('2d');
        if (balanceLineChart) balanceLineChart.destroy();
        balanceLineChart = new Chart(balanceCtx, {
            type: 'line',
            data: {
                labels: data.balanceOverTime.length ? data.balanceOverTime.map(item => item.date) : ['No Data'],
                datasets: [{
                    label: 'Balance',
                    data: data.balanceOverTime.length ? data.balanceOverTime.map(item => item.balance) : [0],
                    borderColor: '#36A2EB',
                    fill: false
                }]
            },
            options: {
                responsive: true,
                scales: { y: { beginAtZero: false } },
                maintainAspectRatio: false
            }
        });

        // Bar Chart: Monthly Income vs Expenses
        const monthlyCtx = document.getElementById('monthlyBarChart').getContext('2d');
        if (monthlyBarChart) monthlyBarChart.destroy();
        monthlyBarChart = new Chart(monthlyCtx, {
            type: 'bar',
            data: {
                labels: data.monthlySummary.length ? data.monthlySummary.map(item => item.month) : ['No Data'],
                datasets: [
                    {
                        label: 'Income',
                        data: data.monthlySummary.length ? data.monthlySummary.map(item => item.income) : [0],
                        backgroundColor: '#36A2EB'
                    },
                    {
                        label: 'Expense',
                        data: data.monthlySummary.length ? data.monthlySummary.map(item => item.expense) : [0],
                        backgroundColor: '#FF6384'
                    }
                ]
            },
            options: {
                responsive: true,
                scales: { y: { beginAtZero: true } },
                maintainAspectRatio: false
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
        tab.addEventListener('shown.bs.tab', loadReports);
    });
});
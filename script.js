document.getElementById('transactionForm').addEventListener('submit', async function (e) {
    e.preventDefault();

    // Get form values
    const description = document.getElementById('description').value;
    const amount = parseFloat(document.getElementById('amount').value);
    const type = document.getElementById('type').value;
    const date = document.getElementById('date').value;

    // Prepare the data to send
    const transaction = {
        description,
        amount,
        type,
        date
    };

    try {
        // Send the data to the backend
        const response = await fetch('http://127.0.0.1:5000/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(transaction)
        });

        if (!response.ok) {
            throw new Error('Failed to add transaction');
        }

        const result = await response.json();
        console.log('Transaction added:', result);

        // Add transaction to the list (frontend)
        const transactionList = document.getElementById('transactionList');
        const transactionItem = document.createElement('li');
        transactionItem.classList.add('list-group-item');
        transactionItem.textContent = `${date}: ${type === 'income' ? '+' : '-'}Rs${amount} (${description})`;
        transactionList.appendChild(transactionItem);

        // Update totals
        const balanceEl = document.getElementById('balance');
        const totalIncomeEl = document.getElementById('totalIncome');
        const totalExpenseEl = document.getElementById('totalExpense');

        let balance = parseFloat(balanceEl.textContent.replace('Rs', '')) || 0;
        let totalIncome = parseFloat(totalIncomeEl.textContent.replace('Rs', '')) || 0;
        let totalExpense = parseFloat(totalExpenseEl.textContent.replace('Rs', '')) || 0;

        if (type === 'income') {
            totalIncome += amount;
            balance += amount;
        } else {
            totalExpense += amount;
            balance -= amount;
        }

        // Update the UI
        balanceEl.textContent = `Rs${balance.toFixed(2)}`;
        totalIncomeEl.textContent = `Rs${totalIncome.toFixed(2)}`;
        totalExpenseEl.textContent = `Rs${totalExpense.toFixed(2)}`;

        // Clear the form
        document.getElementById('transactionForm').reset();
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to add transaction. Please try again.');
    }
});

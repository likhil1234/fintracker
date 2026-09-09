// Auto-detect local development vs production (Netlify/Render)
const API_BASE = (window.location.hostname === "localhost" || 
                  window.location.hostname === "127.0.0.1" || 
                  window.location.protocol === "file:")
    ? "http://127.0.0.1:5000"
    : "https://fintracker-afa0.onrender.com";

console.log(`🔗 FinTracker using API: ${API_BASE}`);

// State
let allBills = [];
let categoryChartInstance = null;
let incomeVsExpenseChartInstance = null;
let itemRowCounter = 0;
let activeModalBillId = null;

// Categories palette (Bills category removed, Shopping added)
const CATEGORY_COLORS = {
    'Food': '#10b981',
    'Shopping': '#6366f1',
    'Transport': '#f59e0b',
    'Entertainment': '#ec4899',
    'Salary': '#3b82f6',
    'Other': '#9ca3af'
};

// ----------------- Initialization -----------------

document.addEventListener('DOMContentLoaded', () => {
    // Set default date to today
    const today = new Date().toISOString().split('T')[0];
    const billDateInput = document.getElementById('billDate');
    if (billDateInput) billDateInput.value = today;

    // Add initial item row in the multi-item form
    addItemRow();

    // Check API connectivity
    checkApiHealth();

    // Setup form submit handlers
    setupEventListeners();

    // Load initial dashboard data
    loadDashboard();
});

async function checkApiHealth() {
    try {
        const res = await fetch(`${API_BASE}/`, { method: 'GET' });
        const badge = document.getElementById('apiStatusBadge');
        if (res.ok) {
            badge.className = "badge badge-success py-2 px-3 mr-2";
            badge.innerHTML = `<i class="fas fa-check-circle mr-1"></i> Connected (${API_BASE.includes('127.0.0.1') ? 'Local SQLite' : 'Render'})`;
        } else {
            badge.className = "badge badge-warning py-2 px-3 mr-2";
            badge.innerHTML = `<i class="fas fa-exclamation-triangle mr-1"></i> API Warning (${res.status})`;
        }
    } catch (err) {
        const badge = document.getElementById('apiStatusBadge');
        badge.className = "badge badge-danger py-2 px-3 mr-2";
        badge.innerHTML = `<i class="fas fa-times-circle mr-1"></i> Server Offline`;
    }
}

// ----------------- Dynamic Multi-Item Rows -----------------

function addItemRow(data = {}) {
    itemRowCounter++;
    const container = document.getElementById('itemsContainer');
    const rowId = `itemRow_${itemRowCounter}`;
    const defaultCategory = document.getElementById('billCategory') ? document.getElementById('billCategory').value : 'Food';

    const row = document.createElement('div');
    row.className = 'item-row';
    row.id = rowId;

    row.innerHTML = `
        <div class="form-row align-items-center mb-1">
            <div class="col-7">
                <input type="text" class="form-control form-control-sm item-desc" placeholder="Item name / description *" value="${escapeHtml(data.description || '')}" required>
            </div>
            <div class="col-4">
                <input type="number" class="form-control form-control-sm item-amount" placeholder="Amount" step="0.01" min="0.01" value="${data.amount || ''}" oninput="calculateFormLiveTotals()" required>
            </div>
            <div class="col-1 text-right">
                <button type="button" class="btn-remove-row" onclick="removeItemRow('${rowId}')" title="Remove item">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        </div>
        <div class="form-row align-items-center">
            <div class="col-6">
                <select class="form-control form-control-sm item-type" onchange="calculateFormLiveTotals()">
                    <option value="expense" ${data.type === 'expense' ? 'selected' : ''}>Expense (-)</option>
                    <option value="income" ${data.type === 'income' ? 'selected' : ''}>Income / Credit (+)</option>
                </select>
            </div>
            <div class="col-6">
                <select class="form-control form-control-sm item-cat">
                    <option value="Food" ${ (data.category || defaultCategory) === 'Food' ? 'selected' : ''}>Food</option>
                    <option value="Shopping" ${ (data.category || defaultCategory) === 'Shopping' ? 'selected' : ''}>Shopping</option>
                    <option value="Transport" ${ (data.category || defaultCategory) === 'Transport' ? 'selected' : ''}>Transport</option>
                    <option value="Salary" ${ (data.category || defaultCategory) === 'Salary' ? 'selected' : ''}>Salary</option>
                    <option value="Entertainment" ${ (data.category || defaultCategory) === 'Entertainment' ? 'selected' : ''}>Entertainment</option>
                    <option value="Other" ${ (data.category || defaultCategory) === 'Other' ? 'selected' : ''}>Other</option>
                </select>
            </div>
        </div>
    `;

    container.appendChild(row);
    calculateFormLiveTotals();
}

function removeItemRow(rowId) {
    const container = document.getElementById('itemsContainer');
    if (container.children.length <= 1) {
        alert("At least one item is required in the bill.");
        return;
    }
    const row = document.getElementById(rowId);
    if (row) {
        row.remove();
        calculateFormLiveTotals();
    }
}

function syncItemCategories(cat) {
    document.querySelectorAll('.item-cat').forEach(select => {
        select.value = cat;
    });
}

function calculateFormLiveTotals() {
    let totalExpense = 0;
    let totalIncome = 0;

    const rows = document.querySelectorAll('.item-row');
    rows.forEach(row => {
        const amount = parseFloat(row.querySelector('.item-amount').value) || 0;
        const type = row.querySelector('.item-type').value;

        if (type === 'income') {
            totalIncome += amount;
        } else {
            totalExpense += amount;
        }
    });

    const net = totalIncome - totalExpense;
    document.getElementById('formLiveExpense').textContent = `Rs ${totalExpense.toFixed(2)}`;
    document.getElementById('formLiveIncome').textContent = `Rs ${totalIncome.toFixed(2)}`;
    document.getElementById('formLiveNet').textContent = `${net >= 0 ? '+' : '-'}Rs ${Math.abs(net).toFixed(2)}`;
}

// ----------------- Form Event Listeners -----------------

function setupEventListeners() {
    // Prevent Enter key from accidentally submitting the entire bill while typing items
    document.getElementById('multiItemBillForm').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault(); // NEVER submit on Enter key
            const target = e.target;

            if (target.classList.contains('item-desc')) {
                // Focus the amount input in the same row
                const row = target.closest('.item-row');
                if (row) {
                    const amountInput = row.querySelector('.item-amount');
                    if (amountInput) amountInput.focus();
                }
            } else if (target.classList.contains('item-amount')) {
                // Automatically append a new item row and focus its description
                addItemRow();
                const allRows = document.querySelectorAll('.item-row');
                const lastRow = allRows[allRows.length - 1];
                if (lastRow) {
                    const descInput = lastRow.querySelector('.item-desc');
                    if (descInput) descInput.focus();
                }
            } else if (target.id === 'billName') {
                const firstDesc = document.querySelector('.item-desc');
                if (firstDesc) firstDesc.focus();
            }
        }
    });

    // Edit Transaction Modal Form
    document.getElementById('editTransactionForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const txnId = document.getElementById('editTxnId').value;
        const bill_name = document.getElementById('editBillName').value.trim();
        const description = document.getElementById('editDescription').value.trim();
        const amount = parseFloat(document.getElementById('editAmount').value);
        const type = document.getElementById('editType').value;
        const category = document.getElementById('editCategory').value;
        const date = document.getElementById('editDate').value;

        try {
            const res = await fetch(`${API_BASE}/transaction/${txnId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bill_name, description, amount, type, category, date })
            });
            if (!res.ok) throw new Error("Failed to update item");

            $('#editTransactionModal').modal('hide');
            await loadDashboard();
            if (activeModalBillId) {
                openBillDetailsModal(activeModalBillId);
            }
        } catch (err) {
            console.error("Error updating item:", err);
            alert("Failed to update item.");
        }
    });

    // Edit Bill Modal Form
    document.getElementById('editBillForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const billId = document.getElementById('editBillId').value;
        const name = document.getElementById('editBillModalName').value.trim();
        const category = document.getElementById('editBillModalCategory').value;
        const date = document.getElementById('editBillModalDate').value;

        try {
            const res = await fetch(`${API_BASE}/bills/${billId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, category, date })
            });
            if (!res.ok) throw new Error("Failed to update bill");

            $('#editBillModal').modal('hide');
            await loadDashboard();
        } catch (err) {
            console.error("Error updating bill:", err);
            alert("Failed to update bill.");
        }
    });
}

// Multi-Item Bill Form Save — called explicitly by the Save button (type=button)
// This ensures Enter key CANNOT trigger this, only a deliberate button click can.
async function submitBillForm() {

    const bill_name = document.getElementById('billName').value.trim();
    const category = document.getElementById('billCategory').value;
    const date = document.getElementById('billDate').value;

    if (!bill_name) {
        alert("Please enter a bill name.");
        document.getElementById('billName').focus();
        return;
    }
    if (!date) {
        alert("Please select a date.");
        document.getElementById('billDate').focus();
        return;
    }

    // Gather all items from the dynamic rows
    const items = [];
    const rows = document.querySelectorAll('.item-row');
    rows.forEach(row => {
        const desc = row.querySelector('.item-desc').value.trim();
        const amount = parseFloat(row.querySelector('.item-amount').value);
        const type = row.querySelector('.item-type').value;
        const cat = row.querySelector('.item-cat').value;

        if (desc && amount > 0) {
            items.push({
                description: desc,
                amount: amount,
                type: type,
                category: cat,
                date: date
            });
        }
    });

    if (items.length === 0) {
        alert("Please provide at least one valid item with description and amount.");
        return;
    }

    const payload = { bill_name, category, date, items };

    try {
        const res = await fetch(`${API_BASE}/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error("Failed to save bill and items");

        // Reset items container to 1 blank row
        document.getElementById('itemsContainer').innerHTML = '';
        addItemRow();
        calculateFormLiveTotals();

        // Refresh dashboard
        await loadDashboard();
    } catch (err) {
        console.error("Error saving bill:", err);
        alert("Failed to save bill. Please check console.");
    }
}



// ----------------- Data Loading -----------------


async function loadDashboard() {
    await Promise.all([
        loadBills(),
        loadBalance(),
        loadAnalytics()
    ]);
}

async function loadBills() {
    try {
        const res = await fetch(`${API_BASE}/bills`);
        if (!res.ok) throw new Error("Failed to load bills");
        const data = await res.json();
        allBills = data.bills || [];

        // 1. Populate Datalist for single form billName autocomplete
        const datalist = document.getElementById('existingBillsList');
        datalist.innerHTML = '';
        allBills.forEach(b => {
            const opt = document.createElement('option');
            opt.value = b.name;
            datalist.appendChild(opt);
        });

        // 2. Render the Bills Directory Table
        renderBillsTable(allBills);

    } catch (err) {
        console.error("❌ Failed to load bills", err);
    }
}

function renderBillsTable(bills) {
    const tbody = document.getElementById('billsTableBody');
    tbody.innerHTML = '';
    document.getElementById('billsCountBadge').textContent = `${bills.length} bills`;
    document.getElementById('totalBillsCount').textContent = bills.length;

    if (bills.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center text-muted py-4">
                    <i class="fas fa-folder-open fa-2x mb-2 d-block text-secondary"></i>
                    No bills created yet. Add a bill with items on the left!
                </td>
            </tr>
        `;
        return;
    }

    bills.forEach(bill => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.title = 'Click to view all items in this bill';
        
        const totalExp = parseFloat(bill.total_expense || 0);
        const totalInc = parseFloat(bill.total_income || 0);
        const net = totalInc - totalExp;
        const count = bill.items ? bill.items.length : bill.item_count;

        tr.innerHTML = `
            <td>
                <span class="font-weight-bold text-primary" onclick="openBillDetailsModal(${bill.id})">
                    <i class="fas fa-file-invoice mr-1"></i>${escapeHtml(bill.name)}
                </span>
            </td>
            <td><span class="badge badge-secondary">${escapeHtml(bill.category)}</span></td>
            <td class="text-muted small">${bill.date}</td>
            <td class="text-center">
                <span class="badge badge-pill badge-info px-2 py-1" onclick="openBillDetailsModal(${bill.id})">${count} items</span>
            </td>
            <td class="text-right text-danger font-weight-bold">Rs ${totalExp.toFixed(2)}</td>
            <td class="text-right text-success font-weight-bold">Rs ${totalInc.toFixed(2)}</td>
            <td class="text-right font-weight-bold ${net >= 0 ? 'text-success' : 'text-primary'}">
                ${net >= 0 ? '+' : '-'}Rs ${Math.abs(net).toFixed(2)}
            </td>
            <td class="text-center" onclick="event.stopPropagation();">
                <button class="btn btn-primary btn-sm py-0 px-2 mr-1 shadow-sm" title="Download PDF" onclick="downloadBillPdfById(${bill.id})">
                    <i class="fas fa-file-pdf"></i>
                </button>
                <button class="btn btn-outline-info btn-sm py-0 px-1 mr-1" title="View All Items" onclick="openBillDetailsModal(${bill.id})">
                    <i class="fas fa-eye"></i>
                </button>
                <button class="btn btn-outline-danger btn-sm py-0 px-1" title="Delete Bill" onclick="deleteBillById(${bill.id})">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// ----------------- View All Items of a Bill (Requirement 2) -----------------

function openBillDetailsModal(billId) {
    const bill = allBills.find(b => String(b.id) === String(billId));
    if (!bill) return;

    activeModalBillId = bill.id;

    document.getElementById('modalBillName').innerHTML = `<i class="fas fa-file-invoice text-primary mr-2"></i>${escapeHtml(bill.name)}`;
    document.getElementById('modalBillMeta').textContent = `Category: ${bill.category} • Date: ${bill.date}`;

    const totalExp = parseFloat(bill.total_expense || 0);
    const totalInc = parseFloat(bill.total_income || 0);
    const net = totalInc - totalExp;

    document.getElementById('modalBillExpense').textContent = `Rs ${totalExp.toFixed(2)}`;
    document.getElementById('modalBillIncome').textContent = `Rs ${totalInc.toFixed(2)}`;
    document.getElementById('modalBillNet').textContent = `${net >= 0 ? '+' : '-'}Rs ${Math.abs(net).toFixed(2)}`;

    // Populate all items belonging to this bill
    const tbody = document.getElementById('modalBillItemsBody');
    tbody.innerHTML = '';

    const items = bill.items || [];
    if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-3">No items in this bill.</td></tr>`;
    } else {
        items.forEach((item, index) => {
            const tr = document.createElement('tr');
            const isIncome = item.type === 'income';
            tr.innerHTML = `
                <td>${index + 1}</td>
                <td><strong>${escapeHtml(item.description)}</strong></td>
                <td><span class="badge badge-light border">${escapeHtml(item.category)}</span></td>
                <td class="text-center">
                    <span class="badge ${isIncome ? 'badge-income' : 'badge-expense'}">
                        ${isIncome ? 'INCOME' : 'EXPENSE'}
                    </span>
                </td>
                <td class="text-right font-weight-bold ${isIncome ? 'text-success' : 'text-danger'}">
                    ${isIncome ? '+' : '-'}Rs ${parseFloat(item.amount).toFixed(2)}
                </td>
                <td class="text-center">
                    <button class="btn btn-outline-primary btn-sm py-0 px-1 mr-1" title="Edit Item" onclick="openEditItemFromModal(${item.id})">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-outline-danger btn-sm py-0 px-1" title="Delete Item" onclick="deleteItemFromModal(${item.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    $('#billDetailsModal').modal('show');
}

function addMoreItemsToActiveModalBill() {
    const bill = allBills.find(b => String(b.id) === String(activeModalBillId));
    if (!bill) return;

    $('#billDetailsModal').modal('hide');

    // Pre-fill the left form with this bill name
    document.getElementById('billName').value = bill.name;
    document.getElementById('billCategory').value = bill.category;
    document.getElementById('billDate').value = bill.date;

    // Scroll to form and focus
    const firstInput = document.querySelector('.item-desc');
    if (firstInput) {
        firstInput.focus();
    }
}

async function deleteItemFromModal(itemId) {
    if (!confirm("Are you sure you want to delete this item?")) return;

    try {
        const res = await fetch(`${API_BASE}/transaction/${itemId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error("Delete failed");

        await loadDashboard();
        if (activeModalBillId) {
            openBillDetailsModal(activeModalBillId);
        }
    } catch (err) {
        console.error("Error deleting item:", err);
        alert("Failed to delete item.");
    }
}

function openEditItemFromModal(itemId) {
    const bill = allBills.find(b => String(b.id) === String(activeModalBillId));
    if (!bill || !bill.items) return;

    const item = bill.items.find(i => String(i.id) === String(itemId));
    if (!item) return;

    document.getElementById('editTxnId').value = item.id;
    document.getElementById('editBillName').value = bill.name;
    document.getElementById('editDescription').value = item.description;
    document.getElementById('editAmount').value = item.amount;
    document.getElementById('editType').value = item.type;
    document.getElementById('editCategory').value = item.category;
    document.getElementById('editDate').value = item.date;

    $('#billDetailsModal').modal('hide');
    $('#editTransactionModal').modal('show');
}

async function deleteBillById(billId) {
    const bill = allBills.find(b => String(b.id) === String(billId));
    const billName = bill ? bill.name : 'this bill';

    if (!confirm(`Delete "${billName}" and all its items? This action cannot be undone.`)) return;

    try {
        const res = await fetch(`${API_BASE}/bills/${billId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error("Failed to delete bill");

        await loadDashboard();
    } catch (err) {
        console.error("Error deleting bill:", err);
        alert("Failed to delete bill.");
    }
}

// ----------------- Download Bill PDF (All Items Together) -----------------

function downloadModalBillPdf() {
    if (activeModalBillId) {
        downloadBillPdfById(activeModalBillId);
    }
}

async function downloadBillPdfById(billId) {
    try {
        const bill = allBills.find(b => String(b.id) === String(billId));
        if (!bill) { alert("Bill not found."); return; }

        // Access jsPDF — loaded via jspdf.umd.min.js CDN which exposes window.jspdf.jsPDF
        const jsPDFLib = (window.jspdf && window.jspdf.jsPDF)
                      || window.jsPDF
                      || (window.jspdf && window.jspdf.default);
        if (!jsPDFLib) {
            alert("PDF library not loaded. Make sure you are connected to the internet and refresh the page.");
            return;
        }

        const doc = new jsPDFLib({ unit: 'pt', format: 'a4', orientation: 'portrait' });
        const PW = doc.internal.pageSize.getWidth();   // 595.28 pt
        const PH = doc.internal.pageSize.getHeight();  // 841.89 pt
        const ML = 40, MR = 40;
        const CW = PW - ML - MR;   // content width
        let y = 50;

        // ---- Colour helpers ----
        const C = {
            indigo:  [79,  70,  229],
            gray:    [107, 114, 128],
            dark:    [17,  24,  39],
            red:     [220, 38,  38],
            green:   [5,   150, 105],
            lightBg: [249, 250, 251],
            border:  [229, 231, 235],
            headBg:  [243, 244, 246],
        };
        const setColor  = (rgb) => doc.setTextColor(...rgb);
        const setFill   = (rgb) => doc.setFillColor(...rgb);
        const setDraw   = (rgb) => doc.setDrawColor(...rgb);

        // ================================================================
        // HEADER
        // ================================================================
        doc.setFontSize(22); doc.setFont('helvetica', 'bold');
        setColor(C.indigo);
        doc.text('FINTRACKER', ML, y);

        doc.setFontSize(9); doc.setFont('helvetica', 'normal');
        setColor(C.gray);
        doc.text('Personal Finance & Expense Management', ML, y + 16);

        // Right side — bill name, date, category
        doc.setFontSize(15); doc.setFont('helvetica', 'bold');
        setColor(C.dark);
        doc.text(bill.name.toUpperCase(), PW - MR, y, { align: 'right' });

        doc.setFontSize(9); doc.setFont('helvetica', 'normal');
        setColor(C.gray);
        doc.text(`Date: ${bill.date}`, PW - MR, y + 16, { align: 'right' });
        setColor(C.indigo);
        doc.text(`Category: ${bill.category}`, PW - MR, y + 29, { align: 'right' });

        y += 48;

        // Header underline
        setDraw(C.indigo);
        doc.setLineWidth(1.5);
        doc.line(ML, y, PW - MR, y);
        y += 22;

        // ================================================================
        // TABLE HEADER
        // ================================================================
        const COL = {
            num:  ML,
            desc: ML + 26,
            cat:  ML + 250,
            type: ML + 355,
            amt:  PW - MR
        };

        setFill(C.headBg);
        doc.rect(ML, y - 13, CW, 20, 'F');

        doc.setFontSize(9.5); doc.setFont('helvetica', 'bold');
        setColor(C.dark);
        doc.text('#',            COL.num,  y);
        doc.text('Item',         COL.desc, y);
        doc.text('Category',     COL.cat,  y);
        doc.text('Type',         COL.type, y);
        doc.text('Amount (Rs)',  COL.amt,  y, { align: 'right' });

        y += 10;
        setDraw(C.border); doc.setLineWidth(0.5);
        doc.line(ML, y, PW - MR, y);
        y += 13;

        // ================================================================
        // TABLE ROWS
        // ================================================================
        const items = bill.items || [];
        doc.setFontSize(9); doc.setFont('helvetica', 'normal');

        if (items.length === 0) {
            setColor(C.gray);
            doc.text('No items in this bill.', PW / 2, y + 10, { align: 'center' });
            y += 30;
        } else {
            items.forEach((item, idx) => {
                if (y > PH - 160) { doc.addPage(); y = 50; }

                const isInc = item.type === 'income';
                const rowColor = isInc ? C.green : C.red;

                setColor(C.dark);
                doc.text(String(idx + 1), COL.num, y);

                // Truncate long descriptions
                const maxDescW = COL.cat - COL.desc - 8;
                const desc = doc.splitTextToSize(item.description, maxDescW)[0];
                doc.text(desc, COL.desc, y);

                const maxCatW = COL.type - COL.cat - 8;
                const cat = doc.splitTextToSize(item.category, maxCatW)[0];
                doc.text(cat, COL.cat, y);

                setColor(rowColor);
                doc.setFont('helvetica', 'bold');
                doc.text(isInc ? 'INCOME' : 'EXPENSE', COL.type, y);

                doc.text(
                    `${isInc ? '+' : '-'}Rs ${parseFloat(item.amount).toFixed(2)}`,
                    COL.amt, y, { align: 'right' }
                );
                doc.setFont('helvetica', 'normal');

                y += 6;
                setDraw(C.border); doc.setLineWidth(0.3);
                doc.line(ML, y, PW - MR, y);
                y += 12;
            });
        }

        y += 14;

        // ================================================================
        // SUMMARY BOX
        // ================================================================
        const totalExp = parseFloat(bill.total_expense || 0);
        const totalInc = parseFloat(bill.total_income || 0);
        const net = totalInc - totalExp;
        const boxH = 88;

        if (y + boxH > PH - 60) { doc.addPage(); y = 50; }

        setFill(C.lightBg); setDraw(C.border); doc.setLineWidth(0.6);
        doc.roundedRect(ML, y, CW, boxH, 5, 5, 'FD');

        const bx = ML + 16, bxr = PW - MR - 16;
        y += 20;

        doc.setFontSize(11);
        setColor(C.red);
        doc.setFont('helvetica', 'normal');
        doc.text('Total Expenses:', bx, y);
        doc.setFont('helvetica', 'bold');
        doc.text(`Rs ${totalExp.toFixed(2)}`, bxr, y, { align: 'right' });

        y += 20;
        setColor(C.green);
        doc.setFont('helvetica', 'normal');
        doc.text('Total Incomes / Credits:', bx, y);
        doc.setFont('helvetica', 'bold');
        doc.text(`Rs ${totalInc.toFixed(2)}`, bxr, y, { align: 'right' });

        y += 12;
        // Dashed divider
        setDraw(C.indigo); doc.setLineWidth(0.8);
        doc.setLineDashPattern([4, 3], 0);
        doc.line(bx, y, bxr, y);
        doc.setLineDashPattern([], 0);

        y += 16;
        doc.setFontSize(13); doc.setFont('helvetica', 'bold');
        setColor(C.dark);
        doc.text('Net Bill Balance:', bx, y);
        setColor(C.indigo);
        doc.text(
            `${net >= 0 ? '+' : '-'}Rs ${Math.abs(net).toFixed(2)}`,
            bxr, y, { align: 'right' }
        );

        // ================================================================
        // FOOTER
        // ================================================================
        const footerY = PH - 28;
        setDraw(C.border); doc.setLineWidth(0.5);
        doc.line(ML, footerY - 10, PW - MR, footerY - 10);
        doc.setFontSize(8); doc.setFont('helvetica', 'normal');
        setColor(C.gray);
        doc.text(
            'Generated by FinTracker  •  Thank you for keeping your finances organized!',
            PW / 2, footerY, { align: 'center' }
        );

        // Save
        const safeFilename = `Bill_${bill.name.replace(/[^a-zA-Z0-9_-]/g, '_')}_${bill.date}.pdf`;
        doc.save(safeFilename);

    } catch (err) {
        console.error("Error generating bill PDF:", err);
        alert("Failed to generate PDF: " + err.message);
    }
}



// ----------------- Live Balance & Analytics -----------------

async function loadBalance() {
    try {
        const res = await fetch(`${API_BASE}/balance`);
        if (!res.ok) throw new Error("Failed to load balance");
        const data = await res.json();

        document.getElementById('balance').textContent = `Rs ${data.balance.toFixed(2)}`;
        document.getElementById('totalIncome').textContent = `Rs ${data.totalIncome.toFixed(2)}`;
        document.getElementById('totalExpense').textContent = `Rs ${data.totalExpense.toFixed(2)}`;
    } catch (err) {
        console.error("❌ Failed to load balance", err);
    }
}

async function loadAnalytics() {
    try {
        const res = await fetch(`${API_BASE}/analytics`);
        if (!res.ok) throw new Error("Failed to load analytics");
        const data = await res.json();

        renderCategoryDonutChart(data.categories || []);
        renderIncomeVsExpenseChart(data.income || 0, data.expense || 0);
    } catch (err) {
        console.error("❌ Failed to load analytics", err);
    }
}

// ----------------- Dynamic Charts -----------------

function renderCategoryDonutChart(categories) {
    const ctx = document.getElementById('categoryDonutChart').getContext('2d');

    const labels = categories.length ? categories.map(c => c.category) : ['No Expenses'];
    const dataValues = categories.length ? categories.map(c => c.total) : [1];
    const bgColors = categories.length 
        ? categories.map(c => CATEGORY_COLORS[c.category] || '#9ca3af')
        : ['#e5e7eb'];

    if (categoryChartInstance) {
        categoryChartInstance.data.labels = labels;
        categoryChartInstance.data.datasets[0].data = dataValues;
        categoryChartInstance.data.datasets[0].backgroundColor = bgColors;
        categoryChartInstance.update();
    } else {
        categoryChartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: dataValues,
                    backgroundColor: bgColors,
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { boxWidth: 12, padding: 10, font: { size: 11 } }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                if (!categories.length) return 'No expenses';
                                return ` ${ctx.label}: Rs ${ctx.raw.toFixed(2)}`;
                            }
                        }
                    }
                },
                cutout: '65%'
            }
        });
    }
}

function renderIncomeVsExpenseChart(income, expense) {
    const ctx = document.getElementById('incomeVsExpenseChart').getContext('2d');

    if (incomeVsExpenseChartInstance) {
        incomeVsExpenseChartInstance.data.datasets[0].data = [income, expense];
        incomeVsExpenseChartInstance.update();
    } else {
        incomeVsExpenseChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Income', 'Expense'],
                datasets: [{
                    label: 'Amount (Rs)',
                    data: [income, expense],
                    backgroundColor: ['#10b981', '#ef4444'],
                    borderRadius: 6,
                    barThickness: 36
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                return ` Rs ${ctx.raw.toFixed(2)}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: value => `Rs ${value}`,
                            font: { size: 10 }
                        }
                    },
                    x: {
                        ticks: { font: { size: 11, weight: 'bold' } }
                    }
                }
            }
        });
    }
}

// Utility
function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
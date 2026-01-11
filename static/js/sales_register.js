// Sales Register Functionality
function getSalesRegisterTemplate() {
  return `
  <style>
    #toast { 
      position: fixed; 
      top: -100px; 
      left: 50%; 
      transform: translateX(-50%);
      z-index: 50; 
      padding: 1rem 1.5rem; 
      border-radius: 0.5rem; 
      font-weight: 500;
      color: white; 
      opacity: 0; 
      transition: all 0.5s ease-in-out; 
      min-width: 250px;
      text-align: center;
    }
    #toast.show { 
      top: 2rem; 
      opacity: 1; 
    }
  </style>
  <div class="animate-fade-in bg-fuel-gray rounded-2xl p-6 shadow space-y-6">
    <div>
      <p class="text-sm uppercase tracking-wide text-gray-400">Sales Management</p>
      <h2 class="text-2xl font-bold text-white">Sales Register</h2>
      <p class="text-gray-300 text-sm mt-2">Manage daily sales entries with automatic calculations.</p>
    </div>

    <div class="bg-fuel-black/40 rounded-xl p-4">
      <div class="flex justify-between items-center mb-4">
        <h3 class="text-white font-semibold">Add Sales Entry</h3>
        <button onclick="clearSalesForm()" class="text-gray-400 hover:text-white text-sm">Clear Form</button>
      </div>
      
      <form id="salesForm" class="grid gap-4">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label class="block text-gray-400 text-sm mb-1">Date</label>
            <input type="date" name="date" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" required>
          </div>
          <div>
            <label class="block text-gray-400 text-sm mb-1">Shift</label>
            <select name="shift" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none">
              <option value="Morning">Morning</option>
              <option value="Evening">Evening</option>
              <option value="Night">Night</option>
            </select>
          </div>
          <div>
            <label class="block text-gray-400 text-sm mb-1">Attendant</label>
            <input type="text" name="attendant" placeholder="Attendant Name" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" required>
          </div>
          <div>
            <label class="block text-gray-400 text-sm mb-1">Pump No.</label>
            <input type="number" name="pump_no" placeholder="1" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" required>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label class="block text-gray-400 text-sm mb-1">Opening Reading (L)</label>
            <input type="number" step="0.01" name="opening_reading" placeholder="0.00" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" required onchange="calculateSales()">
          </div>
          <div>
            <label class="block text-gray-400 text-sm mb-1">Closing Reading (L)</label>
            <input type="number" step="0.01" name="closing_reading" placeholder="0.00" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" required onchange="calculateSales()">
          </div>
          <div>
            <label class="block text-gray-400 text-sm mb-1">Test Sales (L)</label>
            <input type="number" step="0.01" name="test_sales" placeholder="0.00" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" onchange="calculateSales()">
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-gray-400 text-sm mb-1">Rate (₹/L)</label>
            <input type="number" step="0.01" name="rate" placeholder="95.50" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" required onchange="calculateSales()">
          </div>
          <div>
            <label class="block text-gray-400 text-sm mb-1">Total Sales (L)</label>
            <input type="number" step="0.01" name="total_liters_calculated" placeholder="0.00" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" readonly>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-gray-400 text-sm mb-1">Expected Amount (₹)</label>
            <input type="number" step="0.01" name="expected_amount" placeholder="0.00" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" readonly>
          </div>
          <div>
            <label class="block text-gray-400 text-sm mb-1">Actual Amount (₹)</label>
            <input type="number" step="0.01" name="actual_amount" placeholder="0.00" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" readonly>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-gray-400 text-sm mb-1">Cash Sales (₹)</label>
            <input type="number" step="0.01" name="cash_sales" placeholder="0.00" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" onchange="calculateActualAmount()">
          </div>
          <div>
            <label class="block text-gray-400 text-sm mb-1">Card Sales (₹)</label>
            <input type="number" step="0.01" name="card_sales" placeholder="0.00" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" onchange="calculateActualAmount()">
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-gray-400 text-sm mb-1">UPI Sales (₹)</label>
            <input type="number" step="0.01" name="upi_sales" placeholder="0.00" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" onchange="calculateActualAmount()">
          </div>
          <div>
            <label class="block text-gray-400 text-sm mb-1">Credit Sales (₹)</label>
            <input type="number" step="0.01" name="credit_sales" placeholder="0.00" class="w-full bg-fuel-black text-white rounded-lg p-2 focus:outline-none" onchange="calculateActualAmount()">
          </div>
        </div>

        <div class="bg-fuel-orange/20 rounded-xl p-4">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <p class="text-gray-400 text-sm">Total Sales (L)</p>
              <p id="total_liters" class="text-2xl font-bold text-white">0.00</p>
            </div>
            <div>
              <p class="text-gray-400 text-sm">Expected (₹)</p>
              <p id="expected_display" class="text-2xl font-bold text-white">0.00</p>
            </div>
            <div>
              <p class="text-gray-400 text-sm">Actual (₹)</p>
              <p id="actual_display" class="text-2xl font-bold text-white">0.00</p>
            </div>
            <div>
              <p class="text-gray-400 text-sm">Short/Excess (₹)</p>
              <p id="short_excess" class="text-2xl font-bold text-fuel-orange">0.00</p>
            </div>
          </div>
        </div>

        <div class="flex gap-4">
          <button type="submit" class="flex-1 bg-fuel-orange hover:bg-orange-500 text-white font-semibold py-3 rounded-xl transition">
            Save Sales Entry
          </button>
          <button type="button" onclick="saveAndPrint()" class="flex-1 bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-xl transition">
            Save & Print
          </button>
        </div>
      </form>
    </div>

    <div class="bg-fuel-black/40 rounded-xl p-4">
      <div class="flex justify-between items-center mb-4">
        <h3 class="text-white font-semibold">Sales History</h3>
        <div class="flex gap-2">
          <input type="date" id="filterDate" class="bg-fuel-black text-white rounded-lg p-2 text-sm" onchange="filterSales()">
          <button onclick="exportSales()" class="bg-fuel-orange hover:bg-orange-500 text-white px-3 py-2 rounded-lg text-sm">Export</button>
        </div>
      </div>
      
      <div class="overflow-x-auto">
        <table class="w-full text-white text-sm">
          <thead>
            <tr class="border-b border-gray-600">
              <th class="text-left p-2">Date</th>
              <th class="text-left p-2">Shift</th>
              <th class="text-left p-2">Attendant</th>
              <th class="text-center p-2">Pump</th>
              <th class="text-right p-2">Liters</th>
              <th class="text-right p-2">Expected (₹)</th>
              <th class="text-right p-2">Actual (₹)</th>
              <th class="text-right p-2">Mismatch (₹)</th>
              <th class="text-center p-2">Actions</th>
            </tr>
          </thead>
          <tbody id="salesTableBody">
            <tr>
              <td colspan="9" class="text-center p-4 text-gray-400">No sales records found</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>`;
}

// Sales Register Functions
function calculateSales() {
  const form = document.getElementById('salesForm');
  if (!form) return;

  const opening = parseFloat(form.opening_reading.value) || 0;
  const closing = parseFloat(form.closing_reading.value) || 0;
  const testSales = parseFloat(form.test_sales.value) || 0;
  const rate = parseFloat(form.rate.value) || 0;

  console.log('Calculating sales:', { opening, closing, testSales, rate });

  // Calculate total sales in liters
  const totalLiters = closing - opening - testSales;
  
  // Calculate expected amount based on meter readings
  const expectedAmount = totalLiters * rate;
  
  console.log('Calculated values:', { totalLiters, expectedAmount });
  
  // Update form fields
  form.total_liters_calculated.value = totalLiters.toFixed(2);
  form.expected_amount.value = expectedAmount.toFixed(2);
  
  // Update display
  document.getElementById('total_liters').textContent = totalLiters.toFixed(2);
  document.getElementById('expected_display').textContent = expectedAmount.toFixed(2);
  
  // Calculate actual amount and mismatch
  calculateActualAmount();
  
  // Get existing sales count for today
  const today = new Date().toISOString().split('T')[0];
  const existingSales = JSON.parse(localStorage.getItem('salesData') || '[]');
  const todaySales = existingSales.filter(sale => sale.date === today);
  // Note: Removed sales_count display as requested
}

function calculateActualAmount() {
  const form = document.getElementById('salesForm');
  if (!form) return;

  const cashSales = parseFloat(form.cash_sales.value) || 0;
  const cardSales = parseFloat(form.card_sales.value) || 0;
  const upiSales = parseFloat(form.upi_sales.value) || 0;
  const creditSales = parseFloat(form.credit_sales.value) || 0;
  
  console.log('Calculating actual amount:', { cashSales, cardSales, upiSales, creditSales });
  
  // Calculate actual amount entered by attendant
  const actualAmount = cashSales + cardSales + upiSales + creditSales;
  
  // Get expected amount
  const expectedAmount = parseFloat(form.expected_amount.value) || 0;
  
  // Calculate mismatch (shortage/excess)
  const mismatch = actualAmount - expectedAmount;
  
  console.log('Amount calculations:', { actualAmount, expectedAmount, mismatch });
  
  // Update form field
  form.actual_amount.value = actualAmount.toFixed(2);
  
  // Update display
  document.getElementById('actual_display').textContent = actualAmount.toFixed(2);
  document.getElementById('short_excess').textContent = mismatch.toFixed(2);
  
  // Change color based on mismatch
  const shortExcessElement = document.getElementById('short_excess');
  if (mismatch < 0) {
    shortExcessElement.className = 'text-2xl font-bold text-red-500'; // Shortage
  } else if (mismatch > 0) {
    shortExcessElement.className = 'text-2xl font-bold text-green-500'; // Excess
  } else {
    shortExcessElement.className = 'text-2xl font-bold text-fuel-orange'; // Perfect match
  }
}

function clearSalesForm() {
  const form = document.getElementById('salesForm');
  if (form) {
    form.reset();
    // Reset display values
    document.getElementById('total_liters').textContent = '0.00';
    document.getElementById('expected_display').textContent = '0.00';
    document.getElementById('actual_display').textContent = '0.00';
    document.getElementById('short_excess').textContent = '0.00';
    // Reset color
    document.getElementById('short_excess').className = 'text-2xl font-bold text-fuel-orange';
  }
}

function saveSalesEntry(formData) {
  try {
    console.log('saveSalesEntry called with formData:', formData);
    
    const salesData = JSON.parse(localStorage.getItem('salesData') || '[]');
    
    // Get form values directly from DOM elements for readonly fields
    const form = document.getElementById('salesForm');
    console.log('Form element found:', form);
    
    const totalLitersInput = form.querySelector('input[name="total_liters_calculated"]');
    const expectedAmountInput = form.querySelector('input[name="expected_amount"]');
    const actualAmountInput = form.querySelector('input[name="actual_amount"]');
    
    console.log('Readonly inputs found:', { totalLitersInput, expectedAmountInput, actualAmountInput });
    
    const totalLiters = parseFloat(totalLitersInput?.value) || 0;
    const expectedAmount = parseFloat(expectedAmountInput?.value) || 0;
    const actualAmount = parseFloat(actualAmountInput?.value) || 0;
    
    console.log('Readonly values:', { totalLiters, expectedAmount, actualAmount });
    
    const newEntry = {
      id: Date.now(),
      date: formData.get('date'),
      shift: formData.get('shift'),
      attendant: formData.get('attendant'),
      pump_no: formData.get('pump_no'),
      opening_reading: parseFloat(formData.get('opening_reading')),
      closing_reading: parseFloat(formData.get('closing_reading')),
      test_sales: parseFloat(formData.get('test_sales')),
      rate: parseFloat(formData.get('rate')),
      total_liters: totalLiters,
      expected_amount: expectedAmount,
      actual_amount: actualAmount,
      cash_sales: parseFloat(formData.get('cash_sales')),
      card_sales: parseFloat(formData.get('card_sales')),
      upi_sales: parseFloat(formData.get('upi_sales')),
      credit_sales: parseFloat(formData.get('credit_sales')),
      short_excess: parseFloat(document.getElementById('short_excess').textContent),
      created_at: new Date().toISOString()
    };
    
    console.log('New entry to be saved:', newEntry);
    
    salesData.push(newEntry);
    localStorage.setItem('salesData', JSON.stringify(salesData));
    
    console.log('Sales entry saved successfully:', newEntry);
    return newEntry;
  } catch (error) {
    console.error('Error saving sales entry:', error);
    showToast('Error saving sales entry', 'error');
    return null;
  }
}

function loadSalesHistory() {
  const salesData = JSON.parse(localStorage.getItem('salesData') || '[]');
  const tbody = document.getElementById('salesTableBody');
  
  if (!tbody) return;
  
  if (salesData.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="text-center p-4 text-gray-400">No sales records found</td></tr>';
    return;
  }
  
  // Sort by date (newest first)
  const sortedData = salesData.sort((a, b) => new Date(b.date) - new Date(a.date));
  
  tbody.innerHTML = sortedData.map(sale => `
    <tr class="border-b border-gray-700 hover:bg-fuel-black/30">
      <td class="p-2">${sale.date}</td>
      <td class="p-2">${sale.shift}</td>
      <td class="p-2">${sale.attendant}</td>
      <td class="p-2 text-center">${sale.pump_no}</td>
      <td class="p-2 text-right">${sale.total_liters.toFixed(2)}</td>
      <td class="p-2 text-right">₹${sale.expected_amount.toFixed(2)}</td>
      <td class="p-2 text-right">₹${sale.actual_amount.toFixed(2)}</td>
      <td class="p-2 text-right ${sale.short_excess < 0 ? 'text-red-500' : sale.short_excess > 0 ? 'text-green-500' : 'text-fuel-orange'}">
        ${sale.short_excess < 0 ? '-' : '+'}₹${Math.abs(sale.short_excess).toFixed(2)}
      </td>
      <td class="p-2 text-center">
        <button onclick="viewSalesDetails(${sale.id})" class="text-fuel-orange hover:text-white mr-2">View</button>
        <button onclick="deleteSalesEntry(${sale.id})" class="text-red-500 hover:text-red-400">Delete</button>
      </td>
    </tr>
  `).join('');
}

function filterSales() {
  const filterDate = document.getElementById('filterDate').value;
  const salesData = JSON.parse(localStorage.getItem('salesData') || '[]');
  const tbody = document.getElementById('salesTableBody');
  
  if (!tbody) return;
  
  let filteredData = salesData;
  if (filterDate) {
    filteredData = salesData.filter(sale => sale.date === filterDate);
  }
  
  if (filteredData.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="text-center p-4 text-gray-400">No sales records found</td></tr>';
    return;
  }
  
  const sortedData = filteredData.sort((a, b) => new Date(b.date) - new Date(a.date));
  
  tbody.innerHTML = sortedData.map(sale => `
    <tr class="border-b border-gray-700 hover:bg-fuel-black/30">
      <td class="p-2">${sale.date}</td>
      <td class="p-2">${sale.shift}</td>
      <td class="p-2">${sale.attendant}</td>
      <td class="p-2 text-center">${sale.pump_no}</td>
      <td class="p-2 text-right">${sale.total_liters.toFixed(2)}</td>
      <td class="p-2 text-right">₹${sale.expected_amount.toFixed(2)}</td>
      <td class="p-2 text-right">₹${sale.actual_amount.toFixed(2)}</td>
      <td class="p-2 text-right ${sale.short_excess < 0 ? 'text-red-500' : sale.short_excess > 0 ? 'text-green-500' : 'text-fuel-orange'}">
        ${sale.short_excess < 0 ? '-' : '+'}₹${Math.abs(sale.short_excess).toFixed(2)}
      </td>
      <td class="p-2 text-center">
        <button onclick="viewSalesDetails(${sale.id})" class="text-fuel-orange hover:text-white mr-2">View</button>
        <button onclick="deleteSalesEntry(${sale.id})" class="text-red-500 hover:text-red-400">Delete</button>
      </td>
    </tr>
  `).join('');
}

function viewSalesDetails(saleId) {
  const salesData = JSON.parse(localStorage.getItem('salesData') || '[]');
  const sale = salesData.find(s => s.id === saleId);
  
  if (!sale) return;
  
  const mismatchText = sale.short_excess < 0 ? `Shortage: ₹${Math.abs(sale.short_excess).toFixed(2)}` : 
                       sale.short_excess > 0 ? `Excess: ₹${sale.short_excess.toFixed(2)}` : 
                       'Perfect Match';
  
  alert(`Sales Details:\n\nDate: ${sale.date}\nShift: ${sale.shift}\nAttendant: ${sale.attendant}\nPump: ${sale.pump_no}\n\nMeter Readings:\nOpening: ${sale.opening_reading} L\nClosing: ${sale.closing_reading} L\nTest Sales: ${sale.test_sales} L\nRate: ₹${sale.rate}/L\n\nCalculations:\nTotal Liters: ${sale.total_liters.toFixed(2)}\nExpected Amount: ₹${sale.expected_amount.toFixed(2)}\nActual Amount: ₹${sale.actual_amount.toFixed(2)}\n${mismatchText}\n\nPayment Breakdown:\nCash: ₹${sale.cash_sales.toFixed(2)}\nCard: ₹${sale.card_sales.toFixed(2)}\nUPI: ₹${sale.upi_sales.toFixed(2)}\nCredit: ₹${sale.credit_sales.toFixed(2)}`);
}

function deleteSalesEntry(saleId) {
  try {
    if (!confirm('Are you sure you want to delete this sales entry?')) return;
    
    const salesData = JSON.parse(localStorage.getItem('salesData') || '[]');
    const updatedData = salesData.filter(sale => sale.id !== saleId);
    localStorage.setItem('salesData', JSON.stringify(updatedData));
    
    loadSalesHistory();
    showToast('Sales entry deleted successfully', 'success');
  } catch (error) {
    console.error('Error deleting sales entry:', error);
    showToast('Error deleting sales entry', 'error');
  }
}

function exportSales() {
  try {
    const salesData = JSON.parse(localStorage.getItem('salesData') || '[]');
    
    if (salesData.length === 0) {
      showToast('No sales data to export', 'error');
      return;
    }
    
    // Create CSV content
    const headers = ['Date', 'Shift', 'Attendant', 'Pump No', 'Opening Reading', 'Closing Reading', 'Test Sales', 'Rate', 'Total Liters', 'Expected Amount', 'Actual Amount', 'Short/Excess', 'Cash Sales', 'Card Sales', 'UPI Sales', 'Credit Sales'];
    const csvContent = [
      headers.join(','),
      ...salesData.map(sale => [
        sale.date,
        sale.shift,
        sale.attendant,
        sale.pump_no,
        sale.opening_reading,
        sale.closing_reading,
        sale.test_sales,
        sale.rate,
        sale.total_liters.toFixed(2),
        sale.expected_amount.toFixed(2),
        sale.actual_amount.toFixed(2),
        sale.short_excess.toFixed(2),
        sale.cash_sales.toFixed(2),
        sale.card_sales.toFixed(2),
        sale.upi_sales.toFixed(2),
        sale.credit_sales.toFixed(2)
      ].join(','))
    ].join('\n');
    
    // Create download link
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sales_register_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    
    showToast('Sales data exported successfully', 'success');
  } catch (error) {
    console.error('Error exporting sales data:', error);
    showToast('Error exporting sales data', 'error');
  }
}

function saveAndPrint() {
  try {
    const form = document.getElementById('salesForm');
    if (!form) return;
    
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }
    
    const formData = new FormData(form);
    const newEntry = saveSalesEntry(formData);
    
    if (!newEntry) {
      showToast('Error saving sales entry for printing', 'error');
      return;
    }
    
    // Print functionality
    const mismatchText = newEntry.short_excess < 0 ? `Shortage: ₹${Math.abs(newEntry.short_excess).toFixed(2)}` : 
                         newEntry.short_excess > 0 ? `Excess: ₹${newEntry.short_excess.toFixed(2)}` : 
                         'Perfect Match';
    
    const printContent = `
      <html>
        <head>
          <title>Sales Register Entry</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            .header { text-align: center; margin-bottom: 30px; }
            .details { margin: 20px 0; }
            .row { display: flex; justify-content: space-between; margin: 10px 0; }
            .total { font-weight: bold; font-size: 18px; margin-top: 20px; }
            .mismatch { color: ${newEntry.short_excess < 0 ? 'red' : newEntry.short_excess > 0 ? 'green' : 'orange'}; font-weight: bold; }
          </style>
        </head>
        <body>
          <div class="header">
            <h1>Sales Register Entry</h1>
            <p>Date: ${newEntry.date}</p>
          </div>
          <div class="details">
            <div class="row"><span>Shift:</span><span>${newEntry.shift}</span></div>
            <div class="row"><span>Attendant:</span><span>${newEntry.attendant}</span></div>
            <div class="row"><span>Pump No:</span><span>${newEntry.pump_no}</span></div>
            <hr>
            <div class="row"><span>Opening Reading:</span><span>${newEntry.opening_reading} L</span></div>
            <div class="row"><span>Closing Reading:</span><span>${newEntry.closing_reading} L</span></div>
            <div class="row"><span>Test Sales:</span><span>${newEntry.test_sales} L</span></div>
            <div class="row"><span>Rate:</span><span>₹${newEntry.rate}/L</span></div>
            <hr>
            <div class="row total"><span>Total Sales:</span><span>${newEntry.total_liters.toFixed(2)} L</span></div>
            <div class="row total"><span>Expected Amount:</span><span>₹${newEntry.expected_amount.toFixed(2)}</span></div>
            <div class="row total"><span>Actual Amount:</span><span>₹${newEntry.actual_amount.toFixed(2)}</span></div>
            <div class="row total mismatch"><span>Mismatch:</span><span>${mismatchText}</span></div>
            <hr>
            <div class="row"><span>Cash Sales:</span><span>₹${newEntry.cash_sales.toFixed(2)}</span></div>
            <div class="row"><span>Card Sales:</span><span>₹${newEntry.card_sales.toFixed(2)}</span></div>
            <div class="row"><span>UPI Sales:</span><span>₹${newEntry.upi_sales.toFixed(2)}</span></div>
            <div class="row"><span>Credit Sales:</span><span>₹${newEntry.credit_sales.toFixed(2)}</span></div>
          </div>
        </body>
      </html>
    `;
    
    const printWindow = window.open('', '_blank');
    printWindow.document.write(printContent);
    printWindow.document.close();
    printWindow.print();
    printWindow.close();
    
    // Clear form and reload history
    clearSalesForm();
    loadSalesHistory();
    showToast('Sales entry saved and printed successfully', 'success');
  } catch (error) {
    console.error('Error in save and print:', error);
    showToast('Error in save and print functionality', 'error');
  }
}

function initSalesRegister() {
  const form = document.getElementById('salesForm');
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      
      console.log('Form submission started');
      
      if (!form.checkValidity()) {
        console.log('Form validation failed');
        form.reportValidity();
        return;
      }
      
      try {
        const formData = new FormData(form);
        console.log('FormData created');
        
        // Log all form data for debugging
        for (let [key, value] of formData.entries()) {
          console.log(`${key}: ${value}`);
        }
        
        const result = saveSalesEntry(formData);
        
        if (result) {
          console.log('Sales entry saved successfully');
          clearSalesForm();
          loadSalesHistory();
          showToast('Sales entry saved successfully', 'success');
        } else {
          console.log('Failed to save sales entry');
        }
      } catch (error) {
        console.error('Form submission error:', error);
        showToast('Error submitting form', 'error');
      }
    });
    
    // Set today's date as default
    const dateInput = form.querySelector('input[name="date"]');
    if (dateInput && !dateInput.value) {
      dateInput.value = new Date().toISOString().split('T')[0];
    }
  }
  
  loadSalesHistory();
}

// Toast notification function
function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.id = 'toast';
  toast.className = 'show';
  toast.textContent = message;
  
  if (type === 'error') {
    toast.style.backgroundColor = '#ef4444';
  } else if (type === 'warning') {
    toast.style.backgroundColor = '#f59e0b';
  } else {
    toast.style.backgroundColor = '#10b981';
  }
  
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => {
      document.body.removeChild(toast);
    }, 500);
  }, 3000);
}

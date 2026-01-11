// Admin Dashboard JavaScript
function verifyPayment(paymentId) {
  window.location.href = `/admin/payments/pending#payment-${paymentId}`;
}

function verifyWalletTopup(topupId) {
  window.location.href = `/admin/wallet-topups/pending#topup-${topupId}`;
}

function verifyRegistration(regId) {
  window.location.href = `/admin/registrations/pending#reg-${regId}`;
}

// Export Functions
function exportDashboardData(format) {
  const dashboardData = {
    statistics: {
      total_pumps: 0,
      total_owners: 0,
      active_subscriptions: 0
    },
    pending_payments: [],
    pending_wallet_topups: [],
    pending_registrations: [],
    export_date: new Date().toISOString()
  };

  if (format === 'csv') {
    exportToCSV(dashboardData);
  } else if (format === 'pdf') {
    exportToPDF(dashboardData);
  }
}

function exportToCSV(data) {
  let csv = 'Fuel Flux Admin Dashboard Export\n';
  csv += `Export Date: ${data.export_date}\n\n`;
  
  // Statistics
  csv += 'STATISTICS\n';
  csv += 'Metric,Value\n';
  csv += `Total Pumps,${data.statistics.total_pumps}\n`;
  csv += `Total Owners,${data.statistics.total_owners}\n`;
  csv += `Active Subscriptions,${data.statistics.active_subscriptions}\n\n`;
  
  // Pending Payments
  csv += 'PENDING PAYMENTS\n';
  csv += 'User Email,Plan Type,Duration,Amount\n';
  data.pending_payments.forEach(payment => {
    csv += `"${payment.user_email}","${payment.plan_type}","${payment.duration}","${payment.amount}"\n`;
  });
  csv += '\n';
  
  // Pending Wallet Top-ups
  csv += 'PENDING WALLET TOP-UPS\n';
  csv += 'User Email,Amount\n';
  data.pending_wallet_topups.forEach(topup => {
    csv += `"${topup.user_email}","${topup.amount}"\n`;
  });
  csv += '\n';
  
  // Pending Registrations
  csv += 'PENDING REGISTRATIONS\n';
  csv += 'Owner Name,Pump Name,Contact Number\n';
  data.pending_registrations.forEach(reg => {
    csv += `"${reg.owner_name}","${reg.pump.name}","${reg.contact_number}"\n`;
  });

  // Download CSV
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  link.setAttribute('href', url);
  link.setAttribute('download', `fuel_flux_dashboard_${new Date().toISOString().split('T')[0]}.csv`);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function exportToPDF(data) {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();
  
  // Title
  doc.setFontSize(20);
  doc.text('Fuel Flux Admin Dashboard', 14, 20);
  doc.setFontSize(10);
  doc.text(`Export Date: ${new Date().toLocaleDateString()}`, 14, 30);
  
  let yPosition = 50;
  
  // Statistics
  doc.setFontSize(14);
  doc.text('Statistics', 14, yPosition);
  yPosition += 10;
  doc.setFontSize(10);
  doc.text(`Total Pumps: ${data.statistics.total_pumps}`, 20, yPosition);
  yPosition += 7;
  doc.text(`Total Owners: ${data.statistics.total_owners}`, 20, yPosition);
  yPosition += 7;
  doc.text(`Active Subscriptions: ${data.statistics.active_subscriptions}`, 20, yPosition);
  yPosition += 15;
  
  // Pending Payments
  doc.setFontSize(14);
  doc.text('Pending Payments', 14, yPosition);
  yPosition += 10;
  doc.setFontSize(10);
  data.pending_payments.forEach(payment => {
    doc.text(`${payment.user_email} - ${payment.plan_type} - ₹${payment.amount}`, 20, yPosition);
    yPosition += 7;
    if (yPosition > 270) {
      doc.addPage();
      yPosition = 20;
    }
  });
  
  // Save PDF
  doc.save(`fuel_flux_dashboard_${new Date().toISOString().split('T')[0]}.pdf`);
}

function printDashboard() {
  // Create print-friendly version
  const printContent = `
    <div style="font-family: Arial, sans-serif; padding: 20px;">
      <h1 style="color: #FB923C; margin-bottom: 20px;">Fuel Flux Admin Dashboard</h1>
      <p style="margin-bottom: 30px;"><strong>Export Date:</strong> ${new Date().toLocaleDateString()}</p>
      
      <h2 style="color: #FB923C; margin-bottom: 15px;">Statistics</h2>
      <table style="width: 100%; margin-bottom: 30px; border-collapse: collapse;">
        <tr style="background-color: #1F2937;">
          <th style="padding: 10px; text-align: left; border: 1px solid #374151;">Metric</th>
          <th style="padding: 10px; text-align: left; border: 1px solid #374151;">Value</th>
        </tr>
        <tr>
          <td style="padding: 10px; border: 1px solid #374151;">Total Pumps</td>
          <td style="padding: 10px; border: 1px solid #374151;">0</td>
        </tr>
        <tr>
          <td style="padding: 10px; border: 1px solid #374151;">Total Owners</td>
          <td style="padding: 10px; border: 1px solid #374151;">0</td>
        </tr>
        <tr>
          <td style="padding: 10px; border: 1px solid #374151;">Active Subscriptions</td>
          <td style="padding: 10px; border: 1px solid #374151;">0</td>
        </tr>
      </table>
      
      <h2 style="color: #FB923C; margin-bottom: 15px;">Pending Items</h2>
      <p><strong>Pending Payments:</strong> 0</p>
      <p><strong>Pending Wallet Top-ups:</strong> 0</p>
      <p><strong>Pending Registrations:</strong> 0</p>
    </div>
  `;
  
  const printWindow = window.open('', '_blank');
  printWindow.document.write(`
    <html>
      <head>
        <title>Fuel Flux Dashboard - Print</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
          table { width: 100%; border-collapse: collapse; }
          th, td { padding: 10px; border: 1px solid #374151; text-align: left; }
          th { background-color: #1F2937; color: #FB923C; }
        </style>
      </head>
      <body>${printContent}</body>
    </html>
  `);
  printWindow.document.close();
  printWindow.print();
}

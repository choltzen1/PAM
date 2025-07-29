// JIRA Modal Functions
function openJiraModal() {
  // Pre-fill with promo information
  const promoCode = document.querySelector('input[name="promo_code"]')?.value || 
                   window.promoData?.code || "";
  const orbitId = window.promoData?.orbit_id || "";
  const initiativeName = window.promoData?.initiative_name || "";
  const launchDate = window.promoData?.promo_start_date || "";
  
  // Format the launch date properly
  let formattedLaunchDate = "";
  if (launchDate) {
    try {
      // Parse the date string and avoid timezone issues by using local date
      const dateParts = launchDate.split('-');
      const year = parseInt(dateParts[0]);
      const month = parseInt(dateParts[1]) - 1; // Month is 0-indexed in JavaScript
      const day = parseInt(dateParts[2]);
      const date = new Date(year, month, day);
      
      const displayMonth = date.getMonth() + 1;
      const displayDay = date.getDate();
      const displayYear = date.getFullYear();
      formattedLaunchDate = ` - Launch Date ${displayMonth}/${displayDay}/${displayYear} 12:00 AM`;
    } catch (error) {
      console.warn('Error parsing launch date:', error);
    }
  }
  
  // Build the summary in the required format:
  // EFPE Promo Device - New Promo - Promo {promo_code} - {orbit_id} - {initiative_name} - Launch Date {date} 12:00 AM
  const summary = `EFPE Promo Device - New Promo - Promo ${promoCode}${orbitId ? ' - ' + orbitId : ''}${initiativeName ? ' - ' + initiativeName : ''}${formattedLaunchDate}`;
  
  document.getElementById('jiraSummary').value = summary;
  document.getElementById('jiraDescription').value = `JIRA Automation Test`;
  
  document.getElementById('jiraModal').style.display = 'block';
}

function closeJiraModal() {
  document.getElementById('jiraModal').style.display = 'none';
}

function createJiraTicket() {
  const formData = {
    summary: document.getElementById('jiraSummary').value,
    description: document.getElementById('jiraDescription').value,
    priority: document.getElementById('jiraPriority').value,
    issue_type: document.getElementById('jiraIssueType').value,
    parent: document.getElementById('jiraParent').value,
    email: document.getElementById('jiraEmail').value,
    token: document.getElementById('jiraToken').value,
    promo_code: window.promoData?.code || ""
  };
  
  if (!formData.summary || !formData.description || !formData.email || !formData.token) {
    alert('Please fill in all required fields.');
    return;
  }
  
  // Show loading state
  const createBtn = event.target;
  const originalText = createBtn.innerHTML;
  createBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';
  createBtn.disabled = true;
  
  fetch('/create_jira_ticket', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(formData)
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      alert(`✅ JIRA Ticket Created: ${data.ticket_key}\n\nThe operator ID has been updated with the ticket number.`);
      closeJiraModal();
      // Refresh the page to show the updated operator ID
      window.location.reload();
    } else {
      alert(`❌ Error creating ticket: ${data.error}`);
    }
  })
  .catch(error => {
    alert(`❌ Error: ${error.message}`);
  })
  .finally(() => {
    // Reset button state
    createBtn.innerHTML = originalText;
    createBtn.disabled = false;
  });
}

// Close modal when clicking outside of it
window.onclick = function(event) {
  const modal = document.getElementById('jiraModal');
  if (event.target == modal) {
    closeJiraModal();
  }
}

// Initialize promo data when page loads
document.addEventListener('DOMContentLoaded', function() {
  // This will be populated by the template
  if (typeof initPromoData === 'function') {
    initPromoData();
  }
});

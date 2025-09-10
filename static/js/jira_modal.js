// JIRA Modal Functions
function openJiraModal(ticketType = 'bptcr') {
  // Store the ticket type for later use
  window.currentTicketType = ticketType;
  
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
  
  // Build different summaries based on ticket type
  let summary, description;
  if (ticketType === 'dcd') {
    summary = `DCD Promo Request - Promo ${promoCode}${orbitId ? ' - ' + orbitId : ''}${initiativeName ? ' - ' + initiativeName : ''}${formattedLaunchDate}`;
    description = `DCD approval request for promotion ${promoCode}`;
    
    // Update modal title
    document.querySelector('#jiraModal .modal-header h3').textContent = 'Create DCD JIRA Ticket';
    
    // Set parent to DCD by default
    const parentSelect = document.getElementById('jiraParent');
    const dcdOption = Array.from(parentSelect.options).find(option => option.textContent.includes('DCD'));
    if (dcdOption) {
      parentSelect.value = dcdOption.value;
    }
  } else {
    summary = `EFPE Promo Device - New Promo - Promo ${promoCode}${orbitId ? ' - ' + orbitId : ''}${initiativeName ? ' - ' + initiativeName : ''}${formattedLaunchDate}`;
    description = `JIRA Automation Test`;
    
    // Update modal title
    document.querySelector('#jiraModal .modal-header h3').textContent = 'Create JIRA Ticket';
    
    // Reset parent to default
    document.getElementById('jiraParent').value = '';
  }
  
  document.getElementById('jiraSummary').value = summary;
  document.getElementById('jiraDescription').value = description;
  
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
    promo_code: window.promoData?.code || document.querySelector('input[name="promo_code"]')?.value || "",
    ticket_type: window.currentTicketType || 'bptcr' // Use stored ticket type
  };
  
  if (!formData.summary || !formData.description) {
    alert('Please fill in the summary and description fields.');
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
      // Show success message with ticket details
      const ticketTypeDisplay = formData.ticket_type === 'dcd' ? 'DCD ' : '';
      alert(`✅ ${ticketTypeDisplay}JIRA Ticket Created Successfully!\n\nTicket: ${data.ticket_key}\nURL: ${data.ticket_url}\n\n${data.message || ''}`);
      
      // Update the appropriate ticket display
      if (data.ticket_key && formData.promo_code) {
        const jiraCards = document.querySelectorAll('.jira-management-card');
        let targetCard;
        
        if (formData.ticket_type === 'dcd') {
          // Find DCD card
          targetCard = Array.from(jiraCards).find(card => 
            card.querySelector('h3')?.textContent.includes('DCD')
          );
        } else {
          // Find BPTCR card (the first one or one without DCD)
          targetCard = Array.from(jiraCards).find(card => 
            !card.querySelector('h3')?.textContent.includes('DCD')
          );
        }
        
        if (targetCard) {
          let statusDiv = targetCard.querySelector('.jira-ticket-status');
          const ticketLabel = formData.ticket_type === 'dcd' ? 'DCD JIRA Ticket Created:' : 'JIRA Ticket Created:';
          
          if (statusDiv) {
            statusDiv.innerHTML = `
              <i class="fas fa-check-circle"></i>
              <strong>${ticketLabel}</strong> 
              <a href="${data.ticket_url}" target="_blank">${data.ticket_key}</a>
            `;
            statusDiv.style.display = 'block';
          } else {
            // Add the status if it doesn't exist
            statusDiv = document.createElement('div');
            statusDiv.className = 'jira-ticket-status';
            statusDiv.innerHTML = `
              <i class="fas fa-check-circle"></i>
              <strong>${ticketLabel}</strong> 
              <a href="${data.ticket_url}" target="_blank">${data.ticket_key}</a>
            `;
            targetCard.appendChild(statusDiv);
          }
        }
      }
      
      closeJiraModal();
    } else {
      // Show detailed error message
      let errorMsg = data.error || 'Unknown error occurred';
      if (errorMsg.includes('JIRA configuration is incomplete')) {
        errorMsg += '\n\nPlease ensure your .env file contains:\n- JIRA_URL\n- JIRA_USERNAME\n- JIRA_API_TOKEN\n- JIRA_PROJECT';
      }
      alert(`❌ Error creating JIRA ticket:\n\n${errorMsg}`);
    }
  })
  .catch(error => {
    console.error('JIRA Error:', error);
    alert(`❌ Network Error: ${error.message}\n\nPlease check your connection and try again.`);
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

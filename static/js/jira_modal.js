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

// ================================
// DCD JIRA FORM FUNCTIONS
// ================================

function toggleEditField(button) {
  const fieldValue = button.closest('.dcd-field-value');
  const autoText = fieldValue.querySelector('.auto-text');
  const editInput = fieldValue.querySelector('.edit-input');
  const autoBadge = fieldValue.querySelector('.auto-badge');
  
  if (editInput.classList.contains('hidden')) {
    // Switch to edit mode
    autoText.style.display = 'none';
    autoBadge.style.display = 'none';
    editInput.classList.remove('hidden');
    editInput.focus();
    button.innerHTML = '<i class="fas fa-check"></i>';
  } else {
    // Switch back to display mode
    const newValue = editInput.value;
    if (newValue.trim()) {
      autoText.textContent = newValue;
    }
    autoText.style.display = 'inline';
    autoBadge.style.display = 'inline';
    editInput.classList.add('hidden');
    button.innerHTML = '<i class="fas fa-edit"></i>';
  }
}

function collectDcdFormData() {
  const formData = {};
  
  // Helper function to get field value (either from display text or input)
  function getFieldValue(name) {
    // First, try to find a direct input/textarea/select field
    const input = document.querySelector(`input[name="${name}"], textarea[name="${name}"], select[name="${name}"]`);
    if (input && !input.classList.contains('hidden') && !input.classList.contains('edit-input')) {
      return input.value;
    }
    
    // For auto-filled fields, find the field by name and get the auto-text value
    const hiddenInput = document.querySelector(`input[name="${name}"].edit-input`);
    if (hiddenInput) {
      // Find the parent dcd-field-value, then find the auto-text within it
      const fieldValue = hiddenInput.closest('.dcd-field-value');
      const autoText = fieldValue?.querySelector('.auto-text');
      if (autoText) {
        return autoText.textContent;
      }
      // Fallback to hidden input value
      return hiddenInput.value;
    }
    
    return '';
  }
  
  // Collect all form data
  formData.initiative_name = getFieldValue('dcd_initiative_name');
  formData.point_of_contact = getFieldValue('dcd_point_of_contact');
  formData.gtm_contact = getFieldValue('dcd_gtm_contact');
  formData.lob = getFieldValue('dcd_lob');
  formData.promo_type = getFieldValue('dcd_promo_type');
  formData.business_behavior = getFieldValue('dcd_business_behavior');
  formData.max_payout = getFieldValue('dcd_max_payout');
  formData.soc_group = getFieldValue('dcd_soc_group');
  formData.start_date = getFieldValue('dcd_start_date');
  formData.end_date = getFieldValue('dcd_end_date');
  formData.promo_id = getFieldValue('dcd_promo_id');
  formData.promo_group_id = getFieldValue('dcd_promo_group_id');
  formData.customer_facing_name = getFieldValue('dcd_customer_facing_name');
  formData.channels = getFieldValue('dcd_channels');
  formData.purchase_devices = getFieldValue('dcd_purchase_devices');
  formData.tradein_devices = getFieldValue('dcd_tradein_devices');
  formData.account_types = getFieldValue('dcd_account_types');
  formData.transaction_types = getFieldValue('dcd_transaction_types');
  formData.ban_limit = getFieldValue('dcd_ban_limit');
  
  return formData;
}

function buildDcdDescription(data) {
  return `Description
*Initiative Name:* ${data.initiative_name || 'TBD'}

*Point of contact for review/validating in PRW/PROD:* ${data.point_of_contact || 'TBD'}

*GTM Point of contact for review/validating in PRW/PROD:* ${data.gtm_contact || 'TBD'}

*LOB:* ${data.lob || 'TMO Postpaid'}

*Promo Type:* ${data.promo_type || 'Trade In (Multi-Tier)'}

*Expected Business Behavior:*  

${data.business_behavior || 'TBD'}

*Max Payout:* ${data.max_payout || 'TBD'}

*SOC Group:* ${data.soc_group || 'TBD'}

*Purchase Devices:*

${data.purchase_devices || 'TBD'}

*Trade-in devices:*

${data.tradein_devices || 'TBD'}

*Promotion Configuration Details:*

*Promotion start date, time:* ${data.start_date || 'TBD'}

*Promotion end date, time:* ${data.end_date || 'TBD'}

*Promo ID:* ${data.promo_id || 'TBD'}

*Promo Group ID:* ${data.promo_group_id || 'TBD'}

*Promotion Customer-Facing Name:* ${data.customer_facing_name || 'TBD'}

*Any account type/sub-type (AT/ST) conditions:* ${data.account_types || 'TBD'}

*DCP Application Channels:* ${data.channels || 'TBD'}

*Transaction types:* ${data.transaction_types || 'TBD'}

*Redemption/BAN Limit:* ${data.ban_limit || 'TBD'}`;
}

function previewDcdTemplate() {
  const data = collectDcdFormData();
  const description = buildDcdDescription(data);
  
  // Create modal for preview
  const modal = document.createElement('div');
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  `;
  
  const content = document.createElement('div');
  content.style.cssText = `
    background: white;
    border-radius: 8px;
    padding: 2rem;
    max-width: 80%;
    max-height: 80%;
    overflow-y: auto;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
  `;
  
  content.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
      <h3 style="margin: 0; color: var(--tmobile-magenta);">DCD JIRA Template Preview</h3>
      <button onclick="this.closest('div').remove()" style="background: none; border: none; font-size: 1.5rem; cursor: pointer;">&times;</button>
    </div>
    <pre style="background: #f8f9fa; padding: 1rem; border-radius: 4px; white-space: pre-wrap; font-family: monospace; font-size: 0.9rem;">${description}</pre>
    <div style="margin-top: 1rem; text-align: right;">
      <button onclick="this.closest('div').remove()" class="btn btn-secondary">Close</button>
    </div>
  `;
  
  modal.appendChild(content);
  document.body.appendChild(modal);
  
  // Close on backdrop click
  modal.addEventListener('click', function(e) {
    if (e.target === modal) {
      modal.remove();
    }
  });
}

function createDcdJiraTicket() {
  const data = collectDcdFormData();
  
  // Validate required fields (business_behavior is auto-filled so not required)
  const requiredFields = ['gtm_contact'];
  const missingFields = requiredFields.filter(field => !data[field] || !data[field].trim());
  
  if (missingFields.length > 0) {
    alert('Please fill in all required fields:\n- ' + missingFields.map(field => 
      field.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())
    ).join('\n- '));
    return;
  }
  
  const description = buildDcdDescription(data);
  const promoCode = window.promoData?.code || document.querySelector('input[name="promo_code"]')?.value || "";
  
  // Determine promo category for title (Device vs Service) based on desired_execution
  const desiredExecution = window.promoData?.desired_execution || '';
  const promoCategory = desiredExecution === 'SPE' ? 'Service' : 'Device';
  
  // Format launch date for summary
  let formattedLaunchDate = '';
  const launchDate = window.promoData?.promo_start_date || '';
  if (launchDate) {
    try {
      const dateParts = launchDate.split('-');
      const year = parseInt(dateParts[0]);
      const month = parseInt(dateParts[1]) - 1;
      const day = parseInt(dateParts[2]);
      const date = new Date(year, month, day);
      const displayMonth = String(date.getMonth() + 1).padStart(2, '0');
      const displayDay = String(date.getDate()).padStart(2, '0');
      const displayYear = date.getFullYear();
      formattedLaunchDate = `${displayMonth}/${displayDay}/${displayYear}`;
    } catch (error) {
      console.warn('Error parsing launch date:', error);
      formattedLaunchDate = 'TBD';
    }
  } else {
    formattedLaunchDate = 'TBD';
  }
  
  const formData = {
    summary: `DCD ${promoCategory} Promo - Promo Build - ${promoCode} - Orbit ${window.promoData?.orbit_id || ''} - ${window.promoData?.bill_facing_name || ''}. Launch date: ${formattedLaunchDate}`,
    description: description,
    priority: 'High',
    issue_type: 'Story',
    parent: '', // Will be set to DCD parent from environment
    promo_code: promoCode,
    ticket_type: 'dcd'
  };
  
  // Show loading state
  const createBtn = document.querySelector('.dcd-actions .btn-primary');
  const originalText = createBtn.innerHTML;
  createBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating DCD Ticket...';
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
      alert(`✅ DCD JIRA Ticket Created Successfully!\n\nTicket: ${data.ticket_key}\nURL: ${data.ticket_url}\n\n${data.message || ''}`);
      
      // Update the ticket status display
      let statusDiv = document.querySelector('.dcd-ticket-status');
      if (!statusDiv) {
        statusDiv = document.createElement('div');
        statusDiv.className = 'dcd-ticket-status';
        document.querySelector('.dcd-jira-form').appendChild(statusDiv);
      }
      
      statusDiv.innerHTML = `
        <i class="fas fa-check-circle"></i>
        <strong>DCD JIRA Ticket Created:</strong> 
        <a href="${data.ticket_url}" target="_blank">${data.ticket_key}</a>
      `;
    } else {
      alert(`❌ Error creating DCD JIRA ticket:\n\n${data.error || 'Unknown error occurred'}`);
    }
  })
  .catch(error => {
    console.error('DCD JIRA Error:', error);
    alert(`❌ Network Error: ${error.message}\n\nPlease check your connection and try again.`);
  })
  .finally(() => {
    // Reset button state
    createBtn.innerHTML = originalText;
    createBtn.disabled = false;
  });
}

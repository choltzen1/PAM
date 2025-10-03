// JIRA Modal Functions
function openJiraModal(ticketType = 'bptcr') {
  // Store the ticket type for later use
  window.currentTicketType = ticketType;
  
  // Pre-fill with promo information
  const promoCode = document.querySelector('input[name="promo_code"]')?.value || 
                   window.promoData?.code || "";
  const orbitId = window.promoData?.orbit_id || "";
  // Initiative name fallback: use initiative_name, then bill_facing_name (strip any quotes)
  const rawInitiativeName = window.promoData?.initiative_name || window.promoData?.bill_facing_name || "";
  const initiativeName = rawInitiativeName.replace(/["'“”‘’`]/g,'');
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
    // Enforce required summary pattern:
    // EFPE Promo Device - New Promo - Promo {promo_code} - {orbit_id} - {initiative_name} - Launch Date {display_start_date}
    // Fallbacks: if data missing, leave blank segment but preserve dashes to keep recognizable structure
    // formattedLaunchDate already includes leading ' - Launch Date ...' per earlier logic
    let displayLaunch = '';
    if(formattedLaunchDate){
      displayLaunch = formattedLaunchDate.replace(/^ - Launch Date\s*/,'');
    } else if (window.promoData?.promo_start_date){
      // Fallback parse if earlier block failed to format
      try {
        const parts = window.promoData.promo_start_date.split('-');
        if(parts.length>=3){
          const y=parseInt(parts[0]); const m=parseInt(parts[1]); const d=parseInt(parts[2]);
          if(!isNaN(y) && !isNaN(m) && !isNaN(d)){
            displayLaunch = `${m}/${d}/${y} 12:00 AM`;
          }
        }
      } catch(e) { /* ignore */ }
    }
    const safePromo = promoCode || (window.promoData?.code || '');
    const safeOrbit = orbitId || (window.promoData?.orbit_id || '');
  const safeInitiative = (initiativeName || '').replace(/["'“”‘’`]/g,'');
    summary = `EFPE Promo Device - New Promo - Promo ${safePromo} - ${safeOrbit} - ${safeInitiative} - Launch Date ${displayLaunch}`.trim();
    description = `BPTCR ticket for promotion ${safePromo || '(unspecified code)'} created via PAM.`;
    
    // Update modal title
    document.querySelector('#jiraModal .modal-header h3').textContent = 'Create JIRA Ticket';
    
    // Reset parent to default
    document.getElementById('jiraParent').value = '';
  }
  
  document.getElementById('jiraSummary').value = summary;
  document.getElementById('jiraDescription').value = description;
  
  document.getElementById('jiraModal').style.display = 'block';

  // If core fields were blank, attempt a deferred fill once after a short timeout (for any late-populated window.promoData)
  if(!promoCode || !orbitId || !initiativeName){
    setTimeout(()=>{
      if(!document.getElementById('jiraModal') || document.getElementById('jiraModal').style.display !== 'block') return;
      const pd = window.promoData || {};
      const p2 = pd.code || promoCode;
      const o2 = pd.orbit_id || orbitId;
  const i2 = (pd.initiative_name || pd.bill_facing_name || initiativeName || '').replace(/["'“”‘’`]/g,'');
      if(p2 && o2 && i2){
        // Rebuild summary preserving existing launch date fragment at end
        const current = document.getElementById('jiraSummary').value;
        const launchFragMatch = current.match(/ - Launch Date .+$/);
        const launchFrag = launchFragMatch ? launchFragMatch[0] : ' - Launch Date ';
        document.getElementById('jiraSummary').value = `EFPE Promo Device - New Promo - Promo ${p2} - ${o2} - ${i2}${launchFrag}`;
      }
    }, 300);
  }

  // --- Absolute fallback: pull fresh from PAM API if still missing key fields (ensures DB source of truth) ---
  (function doApiFallback(){
    if(ticketType === 'dcd') return; // only for EFPE/BPTCR

    // If we don't even have promoCode yet, try to extract from URL (/edit_promo/<CODE>)
    let codeCandidate = promoCode;
    if(!codeCandidate){
      const m = window.location.pathname.match(/\/edit_promo\/([^\/]+)/);
      if(m) codeCandidate = m[1];
    }

    // Decide if we need a fetch: any of orbit / initiative / launch date missing OR promo code was missing before
    const haveLaunch = / - Launch Date \d{1,2}\/\d{1,2}\/\d{4}/.test(document.getElementById('jiraSummary').value);
    if(!codeCandidate) return; // cannot fetch without a code
    if(orbitId && initiativeName && haveLaunch) return; // nothing missing

    // Indicate loading state subtly if the summary is essentially empty after promo label
    const currentSummary = document.getElementById('jiraSummary').value;
    if(/Promo\s*-\s*-\s*-\s*- Launch Date\s*$/.test(currentSummary) || currentSummary.endsWith('Launch Date')){
      document.getElementById('jiraSummary').value = 'Loading promotion details...';
    }

    fetch(`/api/get_promo_details/${encodeURIComponent(codeCandidate)}`)
      .then(r=>r.ok ? r.json() : Promise.reject(new Error('HTTP '+r.status)))
      .then(data => {
        if(!data || !data.found) return;
        const o3 = data.orbit_id || orbitId || '';
  const i3 = (data.initiative_name || data.bill_facing_name || data.description || initiativeName || '').replace(/["'“”‘’`]/g,'');
        // Format launch date (prefer existing formatted if present)
        let launchFrag = '';
        if(data.promo_start_date){
          try {
            const parts = data.promo_start_date.split('-');
            if(parts.length>=3){
              const y=parseInt(parts[0]); const m=parseInt(parts[1]); const d=parseInt(parts[2]);
              if(!isNaN(y)&&!isNaN(m)&&!isNaN(d)){
                launchFrag = ` - Launch Date ${m}/${d}/${y} 12:00 AM`;
              }
            }
          } catch(e){ /* ignore */ }
        }
        const finalLaunch = launchFrag || (document.getElementById('jiraSummary').value.match(/ - Launch Date .+$/) || [''])[0] || ' - Launch Date ';
        document.getElementById('jiraSummary').value = `EFPE Promo Device - New Promo - Promo ${codeCandidate} - ${o3} - ${i3}${finalLaunch}`;
      })
      .catch(()=>{/* silent */});
  })();
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
      // Show success message with ticket details using custom popup with hyperlink
      const ticketTypeDisplay = formData.ticket_type === 'dcd' ? 'DCD ' : '';
      showJiraSuccessPopup({
        key: data.ticket_key,
        url: data.ticket_url,
        message: data.message || '',
        typeLabel: ticketTypeDisplay.trim()
      });
      
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

// Lightweight success popup with hyperlink to Jira ticket
function showJiraSuccessPopup(info){
  if(!info || !info.key) return;
  // Remove existing if present
  const existing = document.getElementById('jiraSuccessToast');
  if(existing) existing.remove();
  const toast = document.createElement('div');
  toast.id = 'jiraSuccessToast';
  toast.style.cssText = 'position:fixed; bottom:20px; right:20px; background:#1c1f23; color:#fff; padding:16px 18px; border-radius:8px; box-shadow:0 4px 16px rgba(0,0,0,0.35); font-family:system-ui,Segoe UI,Roboto,sans-serif; max-width:340px; z-index:99999; display:flex; gap:12px; align-items:flex-start;';
  toast.innerHTML = `
    <div style="flex:1;">
      <div style="font-weight:600; margin-bottom:4px;">${info.typeLabel ? info.typeLabel+' ' : ''}JIRA Ticket Created</div>
      <div style="font-size:13px; line-height:1.4;">
        <a href="${info.url}" target="_blank" style="color:#72d4ff; text-decoration:none; font-weight:600;">${info.key}</a><br>
        ${info.message ? `<span>${escapeHtml(info.message)}</span><br>`:''}
        <span style="opacity:0.75;">Opens in new tab.</span>
      </div>
    </div>
    <button aria-label="Close" style="background:none; border:none; color:#bbb; cursor:pointer; font-size:16px; line-height:1; padding:0 4px;">&times;</button>
  `;
  const closeBtn = toast.querySelector('button');
  closeBtn.addEventListener('click', ()=> toast.remove());
  document.body.appendChild(toast);
  setTimeout(()=>{ if(toast.isConnected) toast.remove(); }, 8000);
}

function escapeHtml(str){
  return String(str).replace(/[&<>"']/g, s=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;' }[s]));
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
    // First, try to find a direct input/textarea/select field that's not hidden
    const directInput = document.querySelector(`input[name="${name}"], textarea[name="${name}"], select[name="${name}"]`);
    if (directInput && !directInput.classList.contains('hidden') && !directInput.classList.contains('edit-input')) {
      return directInput.value;
    }
    
    // For auto-filled fields, find the hidden input/textarea/select with edit-input class
    const hiddenInput = document.querySelector(`input[name="${name}"].edit-input, textarea[name="${name}"].edit-input, select[name="${name}"].edit-input`);
    
    if (hiddenInput) {
      // Find the parent dcd-field-value, then find the auto-text within it
      const fieldValue = hiddenInput.closest('.dcd-field-value');
      const autoText = fieldValue?.querySelector('.auto-text');
      
      if (autoText) {
        return autoText.textContent.trim();
      }
      // Fallback to hidden input/textarea/select value
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
  
  // Additional DCD fields
  formData.rdc_activations = getFieldValue('dcd_rdc_activations');
  formData.rdc_aal = getFieldValue('dcd_rdc_aal');
  formData.rdc_upgrades = getFieldValue('dcd_rdc_upgrades');
  formData.payout_amount = getFieldValue('dcd_payout_amount');
  formData.rebate_details = getFieldValue('dcd_rebate_details');
  formData.segment_name = getFieldValue('dcd_segment_name');
  formData.segment_level = getFieldValue('dcd_segment_level');
  formData.sku_list = getFieldValue('dcd_sku_list');
  formData.tradein_list = getFieldValue('dcd_tradein_list');
  formData.broken_trade = getFieldValue('dcd_broken_trade');
  formData.handset_line_condition = getFieldValue('dcd_handset_line_condition');
  formData.port_in = getFieldValue('dcd_port_in');
  formData.stackable = getFieldValue('dcd_stackable');
  formData.yu1 = getFieldValue('dcd_yu1');
  
  return formData;
}

function formatFieldValue(value, defaultValue = 'TBD') {
  // Only show default if value is truly empty/undefined/null
  // Preserve actual values like "N/A", "No", "False", etc.
  if (value === null || value === undefined || value === '') {
    return defaultValue;
  }
  return value;
}

function buildDcdDescription(data) {
  return `
*Initiative Name:* ${formatFieldValue(data.initiative_name)}

*Point of contact for review/validating in PRW/PROD:* ${formatFieldValue(data.point_of_contact)}

*GTM Point of contact for review/validating in PRW/PROD:* ${formatFieldValue(data.gtm_contact)}

*LOB:* ${formatFieldValue(data.lob, 'TMO Postpaid')}

*Promo Type:* ${formatFieldValue(data.promo_type, 'Trade In (Multi-Tier)')}

*Expected Business Behavior:*  

${formatFieldValue(data.business_behavior)}

*Max Payout:* ${formatFieldValue(data.max_payout)}

*Purchase Devices:*

${formatFieldValue(data.purchase_devices)}

*Trade-in devices:*

${formatFieldValue(data.tradein_devices)}

*Promotion Configuration Details:*

*Promotion start date, time:* ${formatFieldValue(data.start_date)}

*Promotion end date, time:* ${formatFieldValue(data.end_date)}

*Promo ID:* ${formatFieldValue(data.promo_id)}

*Promo Group ID:* ${formatFieldValue(data.promo_group_id)}

*Promotion Customer-Facing Name:* ${formatFieldValue(data.customer_facing_name)}

*Any account type/sub-type (AT/ST) conditions:* ${formatFieldValue(data.account_types)}

*DCP Application Channels:* ${formatFieldValue(data.channels)}

*SOC Group/Rate plan requirement:* ${formatFieldValue(data.soc_group)}

*Transaction types:* ${formatFieldValue(data.transaction_types)}

*100% RDC for Activations (Web only):* ${formatFieldValue(data.rdc_activations)}

*100% RDC for AAL (Web only):* ${formatFieldValue(data.rdc_aal)}

*100% RDC Upgrades (Web only):* ${formatFieldValue(data.rdc_upgrades)}

*Payout amount:* ${formatFieldValue(data.payout_amount)}

*Rebate Details / Promo Code:* ${formatFieldValue(data.rebate_details, 'N/A')}

*Redemption/BAN Limit:* ${data.ban_limit ? (formatFieldValue(data.ban_limit) + '/BAN') : 'TBD'}

*Segment Name:* ${formatFieldValue(data.segment_name)}

*Segment Level:* ${formatFieldValue(data.segment_level)}

*SKU List:* ${formatFieldValue(data.sku_list, 'Attached')}

*Trade-In List (if applicable):* ${formatFieldValue(data.tradein_list, 'Attached')}

*Broken Trade (if applicable):* ${formatFieldValue(data.broken_trade)}

*Handset Line Condition:* ${formatFieldValue(data.handset_line_condition)}

*Port-In:* ${formatFieldValue(data.port_in)}

*Stackable:* ${formatFieldValue(data.stackable)}

*YU1:* ${formatFieldValue(data.yu1)}`;
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

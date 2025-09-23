// Device list formatting functions
document.addEventListener('DOMContentLoaded', function() {
  // Format device lists on page load
  formatDeviceLists();
});

/**
 * Format all device lists in the document
 */
function formatDeviceLists() {
  const deviceLists = document.querySelectorAll('.device-list');
  
  deviceLists.forEach(list => {
    // Only process if not already formatted
    if (!list.dataset.formatted) {
      formatDeviceList(list);
      list.dataset.formatted = 'true';
    }
  });
}

/**
 * Format a single device list element
 * @param {HTMLElement} deviceList - The device list element to format
 */
function formatDeviceList(deviceList) {
  // Get the raw text content instead of innerHTML to prevent HTML entity issues
  const text = deviceList.textContent;
  
  if (!text || text.trim() === '') {
    return;
  }
  
  // Create clean HTML to avoid quote issues
  deviceList.innerHTML = '';
  
  // Split by price categories - looking for $X.XX patterns
  const priceSections = text.split(/(\$\d+\.?\d*)/g);
  
  let currentHTML = '';
  let inPriceSection = false;
  let sectionCount = 0;
  
  // Process each section
  priceSections.forEach(section => {
    if (section.trim() === '') {
      return; // Skip empty sections
    }
    
    // Escape HTML to prevent XSS and handle quotes
    const safeSection = section
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
    
    // If this is a price marker ($399.99, etc)
    if (safeSection.match(/^\$\d+\.?\d*$/)) {
      // Close previous section if there was one
      if (sectionCount > 0) {
        currentHTML += '</div>';
      }
      
      // Start a new price section
      currentHTML += `<div class="device-price-section"><strong>${safeSection}</strong>`;
      inPriceSection = true;
      sectionCount++;
    } else {
      // This is device content
      
      // If this is the first section and doesn't have a price, still format it
      if (!inPriceSection && sectionCount === 0) {
        currentHTML += '<div class="device-section">';
        sectionCount++;
      }
      
      // Process manufacturer sections
      const manufacturers = ['Samsung Galaxy', 'Apple', 'OnePlus', 'Google Pixel', 'LG', 'Moto', 'Motorola'];
      
      let processingSection = section;
      
      manufacturers.forEach(manufacturer => {
        const regex = new RegExp(`(${manufacturer}:)`, 'g');
        processingSection = processingSection.replace(regex, 
          '<span class="device-category">$1</span>');
      });
      
      currentHTML += processingSection;
    }
  });
  
  // Close the last section
  if (sectionCount > 0) {
    currentHTML += '</div>';
  }
  
  // Set the formatted HTML
  deviceList.innerHTML = currentHTML;
}
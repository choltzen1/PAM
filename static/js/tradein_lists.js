/* tradein_lists.js — Trade-In List Generator */

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('createTradeListBtn');
  const errorMsg = document.getElementById('tradeinErrorMsg');

  if (!btn) return;

  btn.addEventListener('click', async () => {
    const tier1 = document.getElementById('tier1Input').value;
    const tier2 = document.getElementById('tier2Input').value;
    const tier3 = document.getElementById('tier3Input').value;

    // Clear previous error
    errorMsg.textContent = '';
    errorMsg.hidden = true;

    // Loading state
    btn.classList.add('is-loading');
    btn.disabled = true;
    btn.innerHTML = '<span class="tradein-spinner"></span> Building list…';

    try {
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
      const response = await fetch('/lists/tradein/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ tier1, tier2, tier3 }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || `Server error (${response.status})`);
      }

      // Trigger file download
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'trade_list.xlsx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      errorMsg.textContent = err.message;
      errorMsg.hidden = false;
    } finally {
      btn.classList.remove('is-loading');
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-plus-lg"></i> Create Trade List';
    }
  });
});

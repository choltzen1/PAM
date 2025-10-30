// Research workspace JS (self-contained)
// Wrap in DOMContentLoaded to avoid global leakage and ensure elements exist.

document.addEventListener('DOMContentLoaded', () => {
  function renderTable(rows, mountEl) {
    if (!rows || !rows.length) { mountEl.innerHTML = '<em>No data</em>'; return; }
    const cols = Object.keys(rows[0]);
    let html = '<div class="table-responsive"><table class="table table-sm table-striped table-bordered"><thead><tr>' + cols.map(c => `<th>${c}</th>`).join('') + '</tr></thead><tbody>';
    html += rows.map(r => '<tr>' + cols.map(c => `<td>${c in r ? (r[c] ?? '') : ''}</td>`).join('') + '</tr>').join('');
    html += '</tbody></table></div><div class="text-muted">' + rows.length + ' rows</div>';
    mountEl.innerHTML = html;
  }

  async function fetchJson(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error('Request failed ' + r.status);
    return r.json();
  }

  function attachForm(id, handler) {
    const form = document.getElementById(id);
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      try { await handler(form); } catch(err) { console.error(err); alert(err.message); }
    });
  }

  attachForm('promo-eligibility-form', async () => {
    const code = document.getElementById('promo_code').value.trim();
    const mount = document.getElementById('promo-eligibility-result');
    if (!code) { mount.innerHTML = '<em>Enter a promo code</em>'; return; }
    mount.innerHTML = 'Loading...';
    const data = await fetchJson(`/research/api/promo-eligibility?promo_code=${encodeURIComponent(code)}`);
    renderTable(data.rows, mount);
  });

  attachForm('eip-form', async () => {
    const eip = document.getElementById('eip_id').value.trim();
    const mount = document.getElementById('eip-result');
    if (!eip) { mount.innerHTML = '<em>Enter EIP ID</em>'; return; }
    mount.innerHTML = 'Loading...';
    const data = await fetchJson(`/research/api/main-data?eip_id=${encodeURIComponent(eip)}`);
    renderTable(data.rows, mount);
  });

  attachForm('ban-form', async () => {
    const ban = document.getElementById('ban').value.trim();
    const rateMount = document.getElementById('ban-rate-plans');
    const lineMount = document.getElementById('ban-aal-lines');
    if (!ban) { rateMount.innerHTML = '<em>Enter BAN</em>'; lineMount.innerHTML = ''; return; }
    rateMount.innerHTML = 'Loading rate plans...';
    lineMount.innerHTML = 'Loading active lines...';
    const [plans, lines] = await Promise.all([
      fetchJson(`/research/api/rate-plans?ban=${encodeURIComponent(ban)}`),
      fetchJson(`/research/api/aal-lines?ban=${encodeURIComponent(ban)}`)
    ]);
    rateMount.innerHTML = '<h6 class="mt-2">Rate Plans</h6>';
    renderTable(plans.rows, rateMount);
    lineMount.innerHTML = '<h6 class="mt-2">Active Lines</h6>';
    renderTable(lines.rows, lineMount);
  });

  attachForm('trade-form', async () => {
    const raw = document.getElementById('order_ids').value.trim();
    const mount = document.getElementById('trade-result');
    if (!raw) { mount.innerHTML = '<em>Enter order line IDs</em>'; return; }
    mount.innerHTML = 'Loading...';
    const data = await fetchJson(`/research/api/trade-data-qr?order_ids=${encodeURIComponent(raw)}`);
    renderTable(data.rows, mount);
  });

  attachForm('promo-error-form', async () => {
    const eip = document.getElementById('eip_error_id').value.trim();
    const mount = document.getElementById('promo-error-result');
    if (!eip) { mount.innerHTML = '<em>Enter EIP ID</em>'; return; }
    mount.innerHTML = 'Loading...';
    const data = await fetchJson(`/research/api/promo-error-reasons?eip_id=${encodeURIComponent(eip)}`);
    renderTable(data.rows, mount);
  });

  attachForm('extract-form', async () => {
    const text = document.getElementById('extract_text').value;
    const mount = document.getElementById('extract-result');
    if (!text.trim()) { mount.innerHTML = '<em>Paste text first</em>'; return; }
    mount.innerHTML = 'Extracting...';
    const data = await fetchJson('/research/api/extract-promo-code', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ prompt: text }) });
    mount.innerHTML = data.promo_code ? `<strong>Found:</strong> ${data.promo_code}` : '<em>No promo code found</em>';
  });

  // Toggle query console visibility
  document.getElementById('toggle-console')?.addEventListener('click', () => {
    const btn = document.getElementById('toggle-console');
    const consoleSection = document.getElementById('query-console');
    if (!btn || !consoleSection) return;
    const open = btn.getAttribute('data-open') === 'true';
    if (open) {
      consoleSection.style.display = 'none';
      btn.textContent = 'Show Query Console';
      btn.setAttribute('data-open','false');
    } else {
      consoleSection.style.display = '';
      btn.textContent = 'Hide Query Console';
      btn.setAttribute('data-open','true');
    }
  });

  // Identification form logic (BAN/MSISDN -> EIP list)
  document.querySelectorAll('input[name="lookup_mode"]').forEach(r => {
    r.addEventListener('change', () => {
      const mode = document.querySelector('input[name="lookup_mode"]:checked').value;
      const label = document.getElementById('identify-input-label');
      const input = document.getElementById('identify_input');
      if (mode === 'ban') { label.textContent = 'BAN'; input.placeholder = 'Enter BAN'; }
      else { label.textContent = 'MSISDN'; input.placeholder = 'Enter MSISDN'; }
    });
  });

  attachForm('identify-form', async () => {
    const mode = document.querySelector('input[name="lookup_mode"]:checked').value;
    const val = document.getElementById('identify_input').value.trim();
    const mount = document.getElementById('identify-result');
    if (!val) { mount.innerHTML = '<em>Enter a value</em>'; return; }
    mount.innerHTML = 'Identifying...';
    const url = mode === 'ban' ? `/research/api/eip-identify?ban=${encodeURIComponent(val)}` : `/research/api/eip-identify?msisdn=${encodeURIComponent(val)}`;
    const data = await fetchJson(url);
    if (!data.rows.length) { mount.innerHTML = '<em>No EIP accounts found</em>'; return; }
    let html = '<div class="table-responsive"><table class="table table-sm table-hover"><thead><tr><th>Select</th><th>EQUIP_ID</th><th>BAN</th><th>MSISDN</th><th>SKU</th><th>Status</th><th>Created</th></tr></thead><tbody>';
    data.rows.forEach(r => {
      html += `<tr data-eip="${r.EQUIP_ID || ''}" style="cursor:pointer"><td><button type="button" class="btn btn-outline-primary btn-xs select-eip" data-eip="${r.EQUIP_ID || ''}" data-ban="${r.BAN || ''}">Use</button></td><td>${r.EQUIP_ID||''}</td><td>${r.BAN||''}</td><td>${r.MSISDN||''}</td><td>${r.EQUIP_SKU||''}</td><td>${r.EQUIP_STATUS||''}</td><td>${r.EQUIP_CREATED_AT||''}</td></tr>`;
    });
    html += '</tbody></table></div>';
    html += '<div class="text-muted">Click Use to populate EIP & BAN into other forms and trigger aggregate pull.</div>';
    mount.innerHTML = html;
    mount.querySelectorAll('.select-eip').forEach(btn => {
      btn.addEventListener('click', async () => {
        const eip = btn.getAttribute('data-eip');
        const ban = btn.getAttribute('data-ban');
        if (eip) { document.getElementById('eip_id').value = eip; document.getElementById('eip_error_id').value = eip; }
        if (ban) { document.getElementById('ban').value = ban; }
        // Auto-run all related lookups using aggregate endpoint for efficiency
        try {
          const aggregateUrl = `/research/api/pete/aggregate?eip_id=${encodeURIComponent(eip)}&ban=${encodeURIComponent(ban)}`;
          const agg = await fetchJson(aggregateUrl);
          // Render main data
          const mainMount = document.getElementById('eip-result');
          if (mainMount && agg.main) { renderTable(agg.main, mainMount); }
          // Promo error reasons
            const errMount = document.getElementById('promo-error-result');
            if (errMount && agg.errors) { renderTable(agg.errors, errMount); }
          // Trade data if present
          const tradeMount = document.getElementById('trade-result');
          if (tradeMount && agg.trade) { renderTable(agg.trade, tradeMount); }
          // Rate plans & AAL lines
          const rateMount = document.getElementById('ban-rate-plans');
          const lineMount = document.getElementById('ban-aal-lines');
          if (rateMount && agg.rate_plans) { rateMount.innerHTML = '<h6 class="mt-2">Rate Plans</h6>'; renderTable(agg.rate_plans, rateMount); }
          if (lineMount && agg.aal_lines) { lineMount.innerHTML = '<h6 class="mt-2">Active Lines</h6>'; renderTable(agg.aal_lines, lineMount); }
          // Populate order_ids field for manual tweaking if trade data exists
          if (agg.trade && agg.trade.length && document.getElementById('order_ids')) {
            const ordCol = agg.trade[0].ord_ln_id !== undefined ? 'ord_ln_id' : 'ORD_LN_ID';
            const orderIds = [...new Set(agg.trade.map(r => r[ordCol]).filter(Boolean))];
            if (orderIds.length) document.getElementById('order_ids').value = orderIds.join(',');
          }
        } catch(err) { console.warn('Aggregate fetch failed', err); }
      });
    });
  });

  // --- PETE Chat UI ---
  const chatForm = document.getElementById('pete-chat-form');
  const chatLog = document.getElementById('pete-chat-log');
  const chatInput = document.getElementById('pete-chat-input');
  const chatStatus = document.getElementById('pete-chat-status');

  function appendChat(role, text, meta) {
    if (!chatLog) return;
    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    div.innerHTML = `<span class="role">${role === 'user' ? 'You' : 'PETE'}</span><span class="text">${text.replace(/</g,'&lt;')}</span>` + (meta ? `<div class="meta">${meta}</div>` : '');
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  if (chatForm) {
    chatForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const prompt = chatInput.value.trim();
      if (!prompt) return;
      appendChat('user', prompt);
      chatInput.value = '';
      chatStatus.textContent = 'Thinking...';
      try {
        const data = await fetchJson('/research/api/pete/chat', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ prompt }) });
        appendChat('assistant', data.reply, data.promo_code ? `Promo: ${data.promo_code}` : '');
      } catch(err) {
        appendChat('assistant', 'Error: ' + err.message);
      } finally {
        chatStatus.textContent = '';
      }
    });
  }
});

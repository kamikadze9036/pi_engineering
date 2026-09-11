(() => {
  const debounce = (fn, wait = 160) => { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); }; };
  function autocomplete(inputId, hiddenId, optionsId, endpoint, formatter) {
    const input = document.getElementById(inputId); if (!input) return;
    const hidden = document.getElementById(hiddenId); const options = document.getElementById(optionsId);
    let results = [];
    const close = () => { options.innerHTML = ''; options.classList.remove('open'); };
    const render = () => { options.innerHTML = ''; results.forEach(item => { const button = document.createElement('button'); button.type = 'button'; button.role = 'option'; button.innerHTML = formatter(item); button.addEventListener('mousedown', event => { event.preventDefault(); hidden.value = item.id; input.value = `${item.code} · ${item.name}`; close(); }); options.appendChild(button); }); options.classList.toggle('open', results.length > 0); };
    const load = async () => { const q = input.value.trim(); hidden.value = ''; try { const response = await fetch(`${endpoint}?q=${encodeURIComponent(q)}`, { headers: { Accept: 'application/json' } }); results = response.ok ? await response.json() : []; render(); } catch { results = []; close(); } };
    input.addEventListener('input', debounce(load)); input.addEventListener('focus', load); input.addEventListener('blur', () => setTimeout(close, 140));
  }
  autocomplete('machine-search', 'machine-id', 'machine-options', '/api/catalog/machines', item => `<b>${item.code}</b> · ${item.name}<small>${item.location || ''}</small>`);
  autocomplete('tool-search', 'tool-id', 'tool-options', '/api/catalog/tools', item => `<b>${item.code}</b> · ${item.name}<small>${item.material || ''}</small>`);
})();

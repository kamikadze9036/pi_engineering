(() => {
  const input = document.getElementById('history-query');
  if (!input) return;
  const clear = document.getElementById('history-clear');
  const rows = [...document.querySelectorAll('#history-rows tr[data-history-search]')];
  const count = document.getElementById('history-count');
  const noMatch = document.getElementById('history-no-match');
  const form = document.getElementById('history-search-form');
  const refresh = () => {
    const query = input.value.trim().toLocaleLowerCase('cs');
    let visible = 0;
    rows.forEach(row => { const show = !query || row.dataset.historySearch.includes(query); row.hidden = !show; if (show) visible++; });
    clear.hidden = !input.value;
    count.textContent = `${visible} ${visible === 1 ? 'záznam' : visible >= 2 && visible <= 4 ? 'záznamy' : 'záznamů'}`;
    if (noMatch) noMatch.hidden = visible > 0 || rows.length === 0;
  };
  form.addEventListener('submit', event => event.preventDefault());
  input.addEventListener('input', refresh);
  clear.addEventListener('click', () => { input.value = ''; refresh(); input.focus(); });
  refresh();
})();

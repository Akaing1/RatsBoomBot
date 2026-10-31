(() => {
 const controls = document.querySelector('[data-log-filters]');
 if (!controls) return;
 const search = controls.querySelector('[data-log-search]');
 const status = controls.querySelector('[data-log-status]');
 const rows = [...document.querySelectorAll('[data-log-row]')];
 const update = () => {
  let visible = 0;
  rows.forEach(row => {
   row.hidden = !(row.dataset.search.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase()) && (status.value === 'all' || row.dataset.status === status.value));
   if (!row.hidden) visible++;
  });
  document.querySelector('[data-log-count]').textContent = `${visible} of ${rows.length} sessions`;
  document.querySelector('[data-log-empty]').hidden = visible > 0;
 };
 search.addEventListener('input', update); status.addEventListener('change', update);
 controls.querySelector('[data-log-reset]').addEventListener('click', () => {search.value = ''; status.value = 'all'; update(); search.focus();});
 controls.hidden = false; update();
})();

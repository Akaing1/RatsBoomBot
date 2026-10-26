(() => {
    const panel = document.querySelector('[data-predictions]');
    if (!panel) return;
    const status = panel.querySelector('[data-prediction-status]');
    const current = panel.querySelector('[data-prediction-current]');
    let busy = false;
    function text(tag, value) { const el = document.createElement(tag); el.textContent = value; return el; }
    async function request(values) {
        const response = await fetch(panel.dataset.api, {cache: 'no-store', credentials: 'same-origin',
            ...(values ? {method: 'POST', body: new URLSearchParams({csrf_token: panel.dataset.csrf, ...values})} : {})});
        let payload;
        try { payload = await response.json(); } catch { throw new Error('Predictions are temporarily unavailable.'); }
        if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'Check the prediction inputs.');
        return payload.data || [];
    }
    function render(predictions) {
        current.replaceChildren();
        const prediction = predictions.find(p => p.status === 'ACTIVE' || p.status === 'LOCKED') || predictions[0];
        if (!prediction) { current.append(text('p', 'No predictions yet.')); return; }
        current.append(text('h4', prediction.title), text('p', prediction.status));
        const outcomes = document.createElement('ul');
        prediction.outcomes.forEach(o => outcomes.append(text('li', `${o.title} · ${o.users || 0} participants`)));
        current.append(outcomes);
        if (panel.dataset.canEdit !== 'true' || !['ACTIVE', 'LOCKED'].includes(prediction.status)) return;
        function button(label, action, extra = {}) {
            const el = text('button', label); el.type = 'button'; el.className = 'button secondary';
            el.addEventListener('click', () => {
                if (action === 'resolve' && !window.confirm(`Resolve this prediction with “${label.slice(8)}” as the winner?`)) return;
                if (action === 'cancel' && !window.confirm('Cancel this prediction and refund all participants?')) return;
                run(() => request({action, prediction_id: prediction.id, ...extra}), 'Prediction updated.');
            });
            return el;
        }
        const controls = document.createElement('div'); controls.className = 'mod-prediction-controls';
        if (prediction.status === 'ACTIVE') controls.append(button('Lock', 'lock'));
        controls.append(button('Cancel', 'cancel'));
        if (prediction.status === 'LOCKED') prediction.outcomes.forEach(o => controls.append(button(`Winner: ${o.title}`, 'resolve', {winning_outcome_id: o.id})));
        current.append(controls);
    }
    async function run(operation, message = '') {
        if (busy) return;
        busy = true; panel.setAttribute('aria-busy', 'true'); status.textContent = 'Loading…';
        panel.querySelectorAll('button').forEach(b => b.disabled = true);
        try { render(await operation()); status.textContent = message; }
        catch (error) { status.textContent = error.message; }
        finally { busy = false; panel.removeAttribute('aria-busy'); panel.querySelectorAll('button').forEach(b => b.disabled = false); }
    }
    panel.querySelector('[data-prediction-refresh]').addEventListener('click', () => run(() => request()));
    panel.querySelector('[data-prediction-create]')?.addEventListener('submit', event => {
        event.preventDefault();
        const values = Object.fromEntries(new FormData(event.currentTarget));
        run(() => request({action: 'create', ...values}), 'Prediction started.');
    });
})();

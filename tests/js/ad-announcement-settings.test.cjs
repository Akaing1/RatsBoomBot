const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('ad color follows delivery selection and remains correct after inline saves', () => {
    const handlers = {};
    const type = {value: 'announcement'}, color = {hidden: false};
    const book = {querySelector: key => key.includes('ad_message_type') ? type : color,
        addEventListener: (name, handler) => { handlers[name] = handler; }};
    vm.runInNewContext(fs.readFileSync('web/static/js/ad-announcement-settings.js', 'utf8'),
        {document: {querySelector: () => book}});
    assert.equal(color.hidden, false);
    type.value = 'message'; handlers.change();
    assert.equal(color.hidden, true);
    type.value = 'announcement'; handlers['settings-saved']();
    assert.equal(color.hidden, false);
});

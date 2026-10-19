const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function setup(saved) {
    const storage = new Map(saved === undefined ? [] : [['ratsboombot:visible-name-colors:1', saved]]);
    const background = {parentElement: null, classList: {contains: () => true}};
    const name = {dataset: {chatNameColor: '#7800a0'}, style: {}, parentElement: background};
    const window = {localStorage: {getItem() { throw new Error('Name readability must not depend on storage'); }, setItem() { throw new Error('No preference to save'); }}};
    vm.runInNewContext(fs.readFileSync('web/static/js/chat-name-colors.js', 'utf8'), {
        window, document: {documentElement: {}, querySelector: () => ({dataset: {channelId: '1'}}),
            querySelectorAll: () => [name]},
        getComputedStyle: () => ({backgroundColor: 'rgb(32, 36, 44)', backgroundImage: 'linear-gradient(rgba(234, 179, 8, 0.12), rgba(234, 179, 8, 0.12))'}),
        MutationObserver: class {observe() {}}
    });
    return {api: window.dashboardNameColors, name, storage};
}
const rgb = color => color.startsWith('#') ? [1,3,5].map(i => parseInt(color.slice(i, i+2),16)) : color.match(/[\d.]+/g).map(Number);
test('always brightens dark colors while preserving readable ones', () => {
    const app = setup();
    app.api.apply(app.name); assert.notEqual(app.name.style.color, '#7800a0');
    assert.ok(app.api.contrast(rgb(app.name.style.color), [32,36,44]) >= 4.5);
    assert.equal(app.api.readable('#ffffff', [[32,36,44]]), '#ffffff');
});
test('corrects existing names on startup regardless of the old disabled preference', () => {
    const app = setup('false');
    assert.notEqual(app.name.style.color, '#7800a0');
    assert.ok(app.api.contrast(rgb(app.name.style.color), [32,36,44]) >= 4.5);
    assert.equal(app.api.attach, undefined);
});
test('dashboard and preview no longer offer a readability toggle', () => {
    const dashboard = fs.readFileSync('web/templates/channel/dashboard.html', 'utf8');
    const preview = fs.readFileSync('web/static/js/raid-preview-chat.js', 'utf8');
    assert.ok(!dashboard.includes('data-visible-name-colors'));
    assert.ok(!preview.includes('Visible name colors'));
    const app = setup(); app.name.dataset.chatNameColor = 'invalid';
    app.name.style.color = 'unchanged'; app.api.apply(app.name);
    assert.equal(app.name.style.color, 'unchanged');
});
test('contrast includes highlighted message backgrounds and light backgrounds', () => {
    const app = setup(); const backgrounds = [[32,36,44], [56,53,40]];
    const result = rgb(app.api.readable('#ff0000', backgrounds));
    backgrounds.forEach(background => assert.ok(app.api.contrast(result, background) >= 4.5));
    const darkened = rgb(app.api.readable('#eeeeee', [[240,240,240]]));
    assert.ok(app.api.contrast(darkened, [240,240,240]) >= 4.5);
});

test('readability adjustment calculates each background luminance only once', () => {
    const app = setup(), background = [32, 36, 44]; let calculations = 0;
    background.map = function(callback) { calculations++; return Array.prototype.map.call(this, callback); };
    const result = app.api.readable('#030004', [background]);
    assert.equal(calculations, 1);
    assert.ok(app.api.contrast(rgb(result), background) >= 4.5);
});

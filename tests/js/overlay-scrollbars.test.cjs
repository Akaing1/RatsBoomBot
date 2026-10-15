const {test} = require('node:test');
const assert = require('node:assert/strict');
const {thumbGeometry} = require('../../web/static/js/overlay-scrollbars.js');

test('no overflow has no scroll range', () => {
    assert.equal(thumbGeometry(100, 100, 96, 0).range, 0);
});
test('thumb follows content proportion and reaches both ends', () => {
    const top = thumbGeometry(100, 400, 96, 0);
    assert.equal(top.size, 24);
    assert.equal(top.offset, 0);
    const end = thumbGeometry(100, 400, 96, 300);
    assert.equal(end.offset + end.size, 96);
    assert.equal(thumbGeometry(100, 400, 96, 150).offset, 36);
});
test('overscroll is clamped and short tracks remain usable', () => {
    assert.equal(thumbGeometry(100, 400, 96, -20).offset, 0);
    assert.equal(thumbGeometry(100, 400, 96, 400).offset, 72);
    assert.equal(thumbGeometry(10, 400, 16, 0).size, 16);
});

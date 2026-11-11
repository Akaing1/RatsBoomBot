const test = require('node:test');
const assert = require('node:assert/strict');
const M = require('../../web/static/js/command-canvas-model.js');
const reply = message => ({type:'reply',message});
const branch = () => ({type:'if',condition:'has_argument',value:'',then:[],else:[]});

test('move reorders siblings and moves blocks into and out of branches without losing them',()=>{
    const a=reply('a'),b=reply('b'),c=branch(),blocks=[a,b,c];
    assert.equal(M.move(blocks,a,blocks,2),true);assert.deepEqual(blocks,[b,a,c]);
    assert.equal(M.move(blocks,a,c.then,0),true);assert.deepEqual(blocks,[b,c]);assert.deepEqual(c.then,[a]);
    assert.equal(M.move(blocks,a,blocks,0),true);assert.deepEqual(blocks,[a,b,c]);assert.deepEqual(c.then,[]);
});
test('moves cannot create a cycle, leave the command tree, or use an invalid index',()=>{
    const parent=branch(),child=branch();parent.then.push(child);const blocks=[parent];
    for(const target of [parent.then,child.else,[]])assert.equal(M.move(blocks,parent,target,0),false);
    assert.equal(M.move(blocks,parent,blocks,-1),false);
    assert.equal(M.flatten(blocks).length,2);assert.equal(blocks[0],parent);
});
test('too-deep moves roll back the original source and destination',()=>{
    const a=branch(),blocks=[a];a.then.push(reply('a'));let target=blocks;
    for(let i=0;i<6;i++){const b=branch();target.push(b);target=b.then;}
    const before=JSON.stringify(blocks);assert.equal(M.withinDepth(blocks),true);
    assert.equal(M.move(blocks,a,target,0),false);
    assert.equal(JSON.stringify(blocks),before);
});
test('arranging preserves manual positions unless requested and never changes execution order',()=>{
    const a=reply('a'),b=branch();b.then.push(reply('nested'));const blocks=[a,b];
    a.position={x:800,y:900};M.arrange(blocks);
    assert.deepEqual(a.position,{x:800,y:900});assert.ok(b.then[0].position.x>b.position.x);
    const order=M.flatten(blocks).map(x=>x.block);
    M.arrange(blocks,true);assert.deepEqual(a.position,{x:40,y:125});
    assert.deepEqual(M.flatten(blocks).map(x=>x.block),order);
});
test('branch depth includes empty child lists, matching server validation',()=>{
    const blocks=[];let target=blocks;
    for(let i=0;i<6;i++){const b=branch();target.push(b);target=b.then;}
    target.push(reply('deepest allowed'));assert.equal(M.withinDepth(blocks),true);
    target.push(branch());assert.equal(M.withinDepth(blocks),false);
});
test('copies retain branches, offset layout and remain independent of their source',()=>{
    const original=branch();original.position={x:50,y:100};original.then.push(reply('hello'));original.then[0].position={x:350,y:230};
    const blocks=[original],copy=M.insertCopy(blocks,original,blocks,1,{x:150,y:200});
    assert.ok(copy);assert.equal(copy.then[0].message,'hello');assert.deepEqual(copy.then[0].position,{x:450,y:330});
    copy.then[0].message='changed';assert.equal(original.then[0].message,'hello');assert.equal(blocks.length,2);
});
test('paste rejects block and nesting limits atomically',()=>{
    const blocks=Array.from({length:40},()=>reply('hi'));
    assert.equal(M.insertCopy(blocks,blocks[0],blocks,1),null);assert.equal(blocks.length,40);
    const tree=[];let target=tree;for(let i=0;i<6;i++){const b=branch();target.push(b);target=b.then;}
    const before=JSON.stringify(tree);assert.equal(M.insertCopy(tree,branch(),target,0),null);assert.equal(JSON.stringify(tree),before);
});

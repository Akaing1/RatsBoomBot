/* Pure tree operations shared by the editor and its tests. Layout never drives execution. */
(function(root) {
    'use strict';
    const children = b => b.type === 'if' ? [['then', b.then], ['else', b.else]] : b.type === 'repeat' ? [['blocks', b.blocks]] : [];
    function flatten(blocks, depth=0, out=[]) {
        blocks.forEach((block,index)=> {out.push({block,list:blocks,index,depth});for(const [,branch] of children(block))flatten(branch,depth+1,out);});return out;
    }
    const withinDepth = blocks => !flatten(blocks).some(x=>x.depth>6||(x.depth===6&&children(x.block).length));
    function move(blocks, block, target, index) {
        const source=flatten(blocks).find(x=>x.block===block);
        if(!source||!Array.isArray(target)||!Number.isInteger(index)||index<0||index>target.length)return false;
        if(target!==blocks&&!flatten(blocks).some(x=>children(x.block).some(([,list])=>list===target)))return false;
        const nested=children(block).some(([,branch])=>branch===target||flatten(branch).some(x=>children(x.block).some(([,list])=>list===target)));
        if(nested)return false;
        source.list.splice(source.index,1);
        if(source.list===target&&source.index<index)index--;
        target.splice(index,0,block);
        if(!withinDepth(blocks)) {target.splice(index,1);source.list.splice(source.index,0,block);return false;}
        return true;
    }
    function insertCopy(blocks, original, target, index, point) {
        if(!Array.isArray(target)||index<0||index>target.length)return null;
        if(target!==blocks&&!flatten(blocks).some(x=>children(x.block).some(([,list])=>list===target)))return null;
        if(flatten(blocks).length+flatten([original]).length>40)return null;
        const copy=JSON.parse(JSON.stringify(original)), origin=copy.position||{x:0,y:0};
        const dx=(point?.x??origin.x+40)-origin.x,dy=(point?.y??origin.y+40)-origin.y;
        for(const {block} of flatten([copy]))if(block.position)block.position={x:Math.max(0,Math.min(20000,block.position.x+dx)),y:Math.max(0,Math.min(20000,block.position.y+dy))};
        if(!copy.position&&point)copy.position={...point};
        target.splice(index,0,copy);
        if(!withinDepth(blocks)){target.splice(index,1);return null;}
        arrange(blocks);return copy;
    }
    function arrange(blocks, force=false) {
        function walk(list,x,y) {
            for(const b of list) {
                if(force||!b.position)b.position={x,y};
                y+=132;
                for(const [,branch] of children(b)) {y=walk(branch,x+300,y);y+=40;}
            }
            return y;
        }
        walk(blocks,40,125);
    }
    function availableRandomBefore(blocks, target) {
        let found=new Set();
        function walk(list, incoming) {
            let available=new Set(incoming);
            for(const block of list){
                if(block===target)found=new Set(available);
                if(block.type==='random_number'&&/^[a-z][a-z0-9_]{0,31}$/.test(block.name))available.add(block.name);
                else if(block.type==='if'){
                    const yes=walk(block.then,available),no=walk(block.else,available);
                    available=new Set([...yes].filter(name=>no.has(name)));
                }else if(block.type==='repeat')available=walk(block.blocks,available);
            }
            return available;
        }
        walk(blocks,new Set());return [...found];
    }
    const api={availableRandomBefore,children,flatten,withinDepth,move,insertCopy,arrange};
    if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.CommandCanvasModel=api;
})(globalThis);

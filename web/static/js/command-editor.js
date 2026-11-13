(() => {
    'use strict';
    const root=document.querySelector('[data-command-editor]');if(!root)return;
    const M=window.CommandCanvasModel, list=root.querySelector('[data-command-list]'), status=root.querySelector('[data-command-status]');
    const endpoint=(document.body.dataset.channelRoot||'/channel')+'/api/for-you/commands', csrf=root.closest('[data-workspace-page]').dataset.csrf;
    const names={reply:'Send message',if:'If / else',random:'Random message',counter:'Counter',random_number:'Random Number'};
    const conditions={has_argument:'An argument was provided',argument_equals:'Arguments equal',is_moderator:'Viewer is a moderator or broadcaster',is_broadcaster:'Viewer is the broadcaster'};
    const values={'user.name':'Caller → name','user.mention':'Caller → @mention','user.channel':'Caller → Twitch channel URL','arg.name':'Argument → username','arg.mention':'Argument → @mention','arg.channel':'Argument → Twitch channel URL','channel.name':'This channel → name','channel.url':'This channel → URL',args:'All arguments',arg1:'First argument',user:'Caller name (legacy)',channel:'Channel name (legacy)'};
    let items=[],selected=null,draft=null,active=null,insertion=null,dirty=false,busy=false,loaded=false,loading=false,expanded=false,zoom=1;
    let testArgs='',testRole='everyone',testResult=null,testBusy=false, generation=0;
    let knownCounters={}, countersLoading=false, counterFeedback='', counterSaving=false, counterOpen=false, counterOpener=null;
    let scroll={left:0,top:0}, clipboard=null, menu=null, menuOrigin=null;
    function el(tag,text,cls) {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
    const run=fn=>Promise.resolve().then(fn).catch(e=>notify(e.message,true));
    function button(text,fn,cls='button secondary') {const b=el('button',text,cls);b.type='button';b.addEventListener('click',()=>run(fn));return b;}
    function notify(text,error=false) {for(const n of [status,...root.querySelectorAll('[data-command-feedback]')]){n.textContent=text;n.classList.toggle('cc-error',error);}}
    function mark() {dirty=true;testResult=null;generation++;const n=root.querySelector('[data-command-dirty]');if(n)n.textContent='Unsaved changes';root.querySelector('[data-test-result]')?.replaceChildren();}
    const leave=()=>!dirty||confirm('Discard your unsaved command changes?');
    async function request(data, url=endpoint) {
        const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),15000);
        try {const response=await fetch(url,{method:data?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,...(data?{body:new URLSearchParams({csrf_token:csrf,...data})}:{})});
            const result=await response.json();if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Please check the command fields.');return result;
        } catch(e){if(e.name==='AbortError')throw new Error('Request timed out. Reload before retrying a save.');throw e;}finally{clearTimeout(timer);}
    }
    function field(parent,label,value,update,options,changesDraft=true) {
        const wrap=el('label',label), input=el(options?'select':'input');
        if(options)for(const [key,text]of Object.entries(options)){const o=el('option',text);o.value=key;input.append(o);}
        input.value=value;input.addEventListener(options?'change':'input',()=>{update(input.value);if(changesDraft)mark();});wrap.append(input);parent.append(wrap);return input;
    }
    function message(parent,value,update,label='Message') {
        const wrap=el('label',label), input=el('textarea');input.rows=4;input.maxLength=450;input.value=value;
        input.addEventListener('input',()=>{update(input.value);mark();updateSummary();});wrap.append(input);parent.append(wrap);
        const pick=el('select');pick.setAttribute('aria-label','Insert a value');
        for(const [key,text]of Object.entries({'':'Insert a value…',...values,...Object.fromEntries(M.availableRandomBefore(draft.blocks,active).map(name=>['random.'+name,'Random result → '+name])),...Object.fromEntries([...new Set([...Object.keys(knownCounters),...M.flatten(draft.blocks).filter(x=>x.block.type==='counter').map(x=>x.block.name).filter(n=>/^[a-z][a-z0-9_]{0,31}$/.test(n))])].map(n=>['counter.'+n,'Counter → '+n]))})){ const o=el('option',text);o.value=key;pick.append(o);}
        pick.addEventListener('change',()=>{if(!pick.value)return;input.setRangeText(`{${pick.value}}`,input.selectionStart,input.selectionEnd,'end');update(input.value);mark();updateSummary();pick.value='';input.focus();});parent.append(pick);
    }
    function summary(b){if(b.type==='random_number')return `${b.name}: ${b.min} to ${b.max}`;return b.type==='counter'?`${b.name}: ${b.operation} ${b.value}`:b.type==='reply'?b.message:b.type==='random'?`${b.choices.length} possible replies`:b.type==='repeat'?`${b.count} repetitions`:conditions[b.condition];}
    function updateSummary(){root.querySelectorAll('.cc-node').forEach(n=>{if(n._block===active)n.querySelector('.cc-node-summary').textContent=summary(active);});}
    function create(type) {if(type==='random_number')return {type,name:'roll',min:1,max:100};if(type==='counter')return {type,name:'deaths',operation:'add',value:1};return type==='reply'?{type,message:'Hello, {user.name}!'}:type==='if'?{type,condition:'has_argument',value:'',then:[],else:[]}:type==='random'?{type,choices:['Yes!','No!']}:{type,count:2,blocks:[]};}
    function add(type,target=insertion||draft.blocks,point=null) {
        if(busy||!draft||M.flatten(draft.blocks).length>=40)return notify('A command can have at most 40 blocks.',true);
        const b=create(type);target.push(b);
        if(!M.withinDepth(draft.blocks)){target.pop();return notify('Limit branches to six levels.',true);}
        if(point)b.position=point;M.arrange(draft.blocks);active=b;if(!point)scroll={left:Math.max(0,b.position.x*zoom-40),top:Math.max(0,b.position.y*zoom-100)};mark();render();
    }
    function close(){if(busy||!leave())return;draft=null;selected=null;active=null;dirty=false;expanded=false;generation++;render();}
    function open(item){if(busy||!leave())return;selected=item;draft=structuredClone(item.command);M.arrange(draft.blocks);active=draft.blocks[0]||null;insertion=draft.blocks;testArgs='';testRole='everyone';testResult=null;generation++;dirty=false;expanded=false;zoom=1;scroll={left:0,top:0};notify('');render();}
    async function mutate(action,command,revision,originalName=command.name) {
        if(busy)return;busy=true;render();
        try {const result=await request({action,definition:JSON.stringify(command),revision,original_name:originalName});
            const index=items.findIndex(x=>x.command.name===originalName);
            if(action==='delete'){if(index>=0)items.splice(index,1);}else{const item={command:structuredClone(command),revision:result.revision};if(index<0)items.push(item);else items[index]=item;}
            dirty=false;draft=null;selected=null;expanded=false;active=null;generation++;notify(action==='delete'?'Command deleted.':'Command saved.');
        }finally{busy=false;render();}
    }
    function renderInspector(parent) {
        parent.append(el('h4',active?(names[active.type]||'Legacy Repeat'):'Block properties'));
        if(!active){parent.append(el('p','Select a block to edit its properties.','cc-hint'));return;}
        const b=active;
        if(b.type==='reply')message(parent,b.message,v=>b.message=v);
        if(b.type==='random_number'){
            field(parent,'Result name',b.name,v=>{b.name=v;updateSummary();}).maxLength=32;
            for(const [key,label]of [['min','Minimum'],['max','Maximum']]){const input=field(parent,label,b[key],v=>{b[key]=Number(v);updateSummary();});input.type='number';input.step=1;input.min=-1000000000;input.max=1000000000;}
            parent.append(el('p','Both bounds are included. Use {random.name} in a later message. Each run generates a fresh result; reusing the same name replaces it.','cc-hint'));
        }
        if(b.type==='counter'){
            const name=field(parent,'Counter name',b.name,v=>{b.name=v;updateSummary();});name.maxLength=32;name.setAttribute('list','cc-counter-names');
            const choices=el('datalist');choices.id='cc-counter-names';for(const key of Object.keys(knownCounters)){const option=el('option');option.value=key;choices.append(option);}parent.append(choices);
            field(parent,'Operation',b.operation,v=>{b.operation=v;updateSummary();},{add:'Increase by',subtract:'Decrease by',set:'Set to'});
            const amount=field(parent,'Value',b.value,v=>{b.value=Number(v);updateSummary();});amount.type='number';amount.step=1;amount.min=-1000000000;amount.max=1000000000;
            parent.append(el('p','Channel counters start at 0, persist across streams, and are shared by your commands. Use {counter.name} in messages. Set to 0 to reset.','cc-hint'));
        }

        if(b.type==='random') {
            b.choices.forEach((v,i)=>message(parent,v,text=>b.choices[i]=text,`Choice ${i+1}`));
            if(b.choices.length<5)parent.append(button('+ Choice',()=>{b.choices.push('Another reply');mark();render();}));
            if(b.choices.length>1)parent.append(button('Remove last choice',()=>{b.choices.pop();mark();render();}));
        }
        if(b.type==='if') {
            field(parent,'Condition',b.condition,v=>{b.condition=v;render();},conditions);
            if(b.condition==='argument_equals')field(parent,'Compare with',b.value,v=>b.value=v).maxLength=100;
        }
        if(b.type==='repeat'){const n=field(parent,'Repeats',b.count,v=>{b.count=Number(v);updateSummary();});n.type='number';n.min=1;n.max=5;}
        const entries=M.flatten(draft.blocks), current=entries.find(x=>x.block===b), actions=el('div',undefined,'cc-actions');
        for(const [label,offset]of [['Move earlier',-1],['Move later',1]]){const move=button(label,()=>{M.move(draft.blocks,b,current.list,current.index+(offset<0?-1:2));mark();render();});move.disabled=current.index+offset<0||current.index+offset>=current.list.length;actions.append(move);}
        actions.append(button('Remove block',()=>{if(M.children(b).some(([,v])=>v.length)&&!confirm('Remove this block and all its branch blocks?'))return;current.list.splice(current.index,1);active=null;insertion=draft.blocks;mark();render();},'button danger'));parent.append(actions);
        parent.append(el('p','Drag to arrange. Drop on a branch to move into it, or on another block to run before it. Arrows show execution order.','cc-hint'));
    }
    function dismissMenu(restore=false) {
        menu?.remove();menu=null;if(restore&&menuOrigin?.isConnected)menuOrigin.focus();menuOrigin=null;
    }
    function contextMenu(event, block, point) {
        if(busy||!draft)return;event.preventDefault();event.stopPropagation();dismissMenu();
        menuOrigin=event.currentTarget;menu=el('div',undefined,'cc-context-menu');menu.setAttribute('role','menu');menu.setAttribute('aria-label',block?'Block actions':'Canvas actions');
        const entry=(label,action,disabled=false)=>{const b=button(label,()=>{dismissMenu();if(!busy&&draft)action();},'cc-context-action');b.setAttribute('role','menuitem');b.disabled=disabled;menu.append(b);};
        const changed=()=>{mark();render();};
        const paste=(source,target,index,position)=>{const copy=M.insertCopy(draft.blocks,source,target,index,position);if(!copy)return notify('Copy would exceed 40 blocks or six nested levels.',true);active=copy;changed();};
        if(block){
            const current=M.flatten(draft.blocks).find(x=>x.block===block);
            entry('Edit block',()=>{active=block;render();root.querySelector('.cc-inspector input,.cc-inspector textarea,.cc-inspector select')?.focus();});
            entry('Copy',()=>{clipboard=structuredClone(block);notify('Block copied, including its branches.');});
            entry('Duplicate',()=>paste(block,current.list,current.index+1));
            entry('Paste after',()=>paste(clipboard,current.list,current.index+1),!clipboard);
            for(const [label,offset]of [['Move earlier',-1],['Move later',1]])entry(label,()=>{M.move(draft.blocks,block,current.list,current.index+(offset<0?-1:2));changed();},current.index+offset<0||current.index+offset>=current.list.length);
            entry('Move to main flow',()=>{if(M.move(draft.blocks,block,draft.blocks,draft.blocks.length)){insertion=draft.blocks;changed();}},current.list===draft.blocks);
            entry('Delete',()=>{if(M.children(block).some(([,v])=>v.length)&&!confirm('Delete this block and all its branch blocks?'))return;current.list.splice(current.index,1);active=null;insertion=draft.blocks;changed();});
        }else entry('Paste block',()=>paste(clipboard,draft.blocks,draft.blocks.length,point),!clipboard);
        root.querySelector('.cc-editor').append(menu);
        menu.style.left=Math.max(8,Math.min(event.clientX,window.innerWidth-menu.offsetWidth-8))+'px';
        menu.style.top=Math.max(8,Math.min(event.clientY,window.innerHeight-menu.offsetHeight-8))+'px';
        menu.querySelector('button:not(:disabled)')?.focus();
    }
    function renderCanvas(parent) {
        const bar=el('div',undefined,'cc-canvas-toolbar');bar.append(el('strong','Command flow'));
        for(const [text,action]of [['−',()=>zoom=Math.max(.35,zoom-.15)],['+',()=>zoom=Math.min(1.5,zoom+.15)],['Reset view',()=>{zoom=1;scroll={left:0,top:0};}]])bar.append(button(text,()=>{action();render();}));
        bar.append(el('span',`${Math.round(zoom*100)}%`),button('Auto arrange',()=>{M.arrange(draft.blocks,true);scroll={left:0,top:0};mark();render();}));parent.append(bar);
        const view=el('div',undefined,'cc-canvas'), spacer=el('div',undefined,'cc-spacer'), world=el('div',undefined,'cc-world');
        view.setAttribute('aria-label','Command canvas');view.tabIndex=0;spacer.append(world);view.append(spacer);parent.append(view);
        const entries=M.flatten(draft.blocks), ports=[], nodes=new Map();
        const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.classList.add('cc-wires');world.append(svg);
        const trigger=el('div','When this command is used','cc-trigger');world.append(trigger);
        function port(owner,branch,label,x,y){const p=button(label,()=>{insertion=branch;notify(`Adding blocks to ${label}.`);render();});p.className='cc-port'+(insertion===branch?' is-target':'');p.setAttribute('aria-pressed',String(insertion===branch));p.style.left=x+'px';p.style.top=y+'px';p._target=branch;p.dataset.dropPort='';world.append(p);ports.push({p,owner,branch,label,x,y});}
        port(null,draft.blocks,'Main flow +',40,75);
        entries.forEach(({block,index,list:sequence},i)=>{
            const n=el('div',undefined,`cc-node cc-${block.type}${active===block?' is-selected':''}`);n.tabIndex=0;n.setAttribute('role','button');n.setAttribute('aria-label',`${names[block.type]||'Legacy Repeat'} ${i+1}`);n.dataset.node='';n._block=block;n._sequence=sequence;n._index=index;
            n.append(el('strong',`${i+1}. ${names[block.type]||'Legacy Repeat'}`),el('span',summary(block),'cc-node-summary'));world.append(n);nodes.set(block,n);
            n.addEventListener('contextmenu',e=>contextMenu(e,block));
            n.addEventListener('keydown',e=>{if(e.key==='ContextMenu'||(e.shiftKey&&e.key==='F10')){const box=n.getBoundingClientRect();contextMenu({preventDefault:()=>e.preventDefault(),stopPropagation:()=>e.stopPropagation(),currentTarget:n,clientX:box.x+20,clientY:box.y+20},block);return;}if(!busy&&(e.key==='Enter'||e.key===' ')){e.preventDefault();active=block;render();}});
            n.addEventListener('pointerdown',e=>{
                if(e.button!==0||busy)return;e.preventDefault();e.stopPropagation();const start={clientX:e.clientX,clientY:e.clientY,...block.position};let moved=false;
                n.setPointerCapture(e.pointerId);
                const moving=event=>{const dx=(event.clientX-start.clientX)/zoom,dy=(event.clientY-start.clientY)/zoom;if(Math.abs(dx)+Math.abs(dy)>5)moved=true;if(!moved)return;n.classList.add('is-dragging');n.style.pointerEvents='none';block.position={x:Math.max(0,Math.min(20000,start.x+dx)),y:Math.max(0,Math.min(20000,start.y+dy))};draw();};
                const end=event=>{n.removeEventListener('pointermove',moving);n.removeEventListener('pointerup',end);n.removeEventListener('pointercancel',cancel);if(n.hasPointerCapture(e.pointerId))n.releasePointerCapture(e.pointerId);
                    const hit=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-drop-port],[data-node]');
                    if(moved&&hit&&hit!==n){const target=hit._target||hit._sequence,at=hit._target?target.length:hit._index;if(!M.move(draft.blocks,block,target,at))notify('A block cannot move into its own branch or exceed six nested levels.',true);}
                    active=block;if(moved)mark();render();};
                const cancel=()=>{block.position={x:start.x,y:start.y};n.removeEventListener('pointermove',moving);n.removeEventListener('pointerup',end);n.removeEventListener('pointercancel',cancel);render();};
                n.addEventListener('pointermove',moving);n.addEventListener('pointerup',end);n.addEventListener('pointercancel',cancel);
            });
            M.children(block).forEach(([key,branch],j)=>port(block,branch,key==='then'?'True +':key==='else'?'False +':'Repeat body +',block.position.x+j*125,block.position.y+88));
        });
        function draw() {
            let width=900,height=550;
            for(const [b,n]of nodes){n.style.left=b.position.x+'px';n.style.top=b.position.y+'px';width=Math.max(width,b.position.x+300);height=Math.max(height,b.position.y+170);}
            for(const p of ports)if(p.owner){const j=M.children(p.owner).findIndex(([,a])=>a===p.branch);p.x=p.owner.position.x+j*125;p.y=p.owner.position.y+88;p.p.style.left=p.x+'px';p.p.style.top=p.y+'px';}
            world.style.width=width+'px';world.style.height=height+'px';world.style.transform=`scale(${zoom})`;spacer.style.width=width*zoom+'px';spacer.style.height=height*zoom+'px';svg.setAttribute('width',width);svg.setAttribute('height',height);svg.replaceChildren();
            function line(a,b){const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',`M ${a.x} ${a.y} C ${a.x} ${a.y+35}, ${b.x} ${b.y-35}, ${b.x} ${b.y}`);svg.append(path);const arrow=document.createElementNS(svg.namespaceURI,'path');arrow.setAttribute('d',`M ${b.x-5} ${b.y-7} L ${b.x} ${b.y} L ${b.x+5} ${b.y-7}`);svg.append(arrow);}
            for(const p of ports){if(!p.branch.length)continue;let from={x:p.x+55,y:p.y+24};for(const b of p.branch){line(from,{x:b.position.x+125,y:b.position.y});from={x:b.position.x+125,y:b.position.y+80};}}
        }
        view.addEventListener('contextmenu',e=>{if(e.target.closest('.cc-node,.cc-port'))return;const box=world.getBoundingClientRect();contextMenu(e,null,{x:Math.max(0,Math.min(20000,(e.clientX-box.left)/zoom)),y:Math.max(0,Math.min(20000,(e.clientY-box.top)/zoom))});});
        draw();const restore={...scroll};requestAnimationFrame(()=>{if(!view.isConnected)return;view.scrollLeft=restore.left;view.scrollTop=restore.top;});view.addEventListener('scroll',()=>{if(view.isConnected)scroll={left:view.scrollLeft,top:view.scrollTop};});
        view.addEventListener('pointerdown',e=>{if(e.button!==0||e.target.closest('.cc-node,.cc-port'))return;const start={x:e.clientX,y:e.clientY,left:view.scrollLeft,top:view.scrollTop};view.setPointerCapture(e.pointerId);const move=p=>{view.scrollLeft=start.left-(p.clientX-start.x);view.scrollTop=start.top-(p.clientY-start.y);};const end=()=>{view.removeEventListener('pointermove',move);view.removeEventListener('pointerup',end);view.removeEventListener('pointercancel',end);};view.addEventListener('pointermove',move);view.addEventListener('pointerup',end);view.addEventListener('pointercancel',end);});
        view.addEventListener('dragover',e=>{if(!busy)e.preventDefault();});view.addEventListener('drop',e=>{e.preventDefault();const type=e.dataTransfer.getData('text/plain');if(!names[type]||busy)return;const bounds=world.getBoundingClientRect(),hit=e.target.closest('[data-drop-port]');add(type,hit?hit._target:insertion||draft.blocks,{x:Math.max(0,Math.min(20000,(e.clientX-bounds.left)/zoom)),y:Math.max(0,Math.min(20000,(e.clientY-bounds.top)/zoom))});});
    }
    function renderTest(parent){parent.append(el('h4','Test command'),el('p','Preview only — no messages are sent.','cc-hint'));
        field(parent,'Test arguments',testArgs,v=>testArgs=v,null,false).maxLength=500;
        field(parent,'Test viewer role',testRole,v=>testRole=v,{everyone:'Everyone',moderator:'Moderator',broadcaster:'Broadcaster'},false);
        const result=el('div');result.dataset.testResult='';result.setAttribute('role','status');
        if(testResult)result.append(el('pre',Object.entries(testResult.random||{}).map(([name,value])=>`${name}: ${value}`).join('\n'),'cc-result'),el('pre',Object.entries(testResult.counters||{}).map(([name,value])=>`${name}: ${value}`).join('\n'),'cc-result'),el('pre',testResult.trace.join('\n'),'cc-result'),el('pre',testResult.messages.join('\n')||'No messages.','cc-result'));
        const test=button(testBusy?'Testing…':'Run test',async()=>{if(testBusy)return;testBusy=true;test.disabled=true;const stamp=generation;try{const response=await request({action:'test',definition:JSON.stringify(draft),args:testArgs,role:testRole});if(stamp===generation){testResult=response;}}finally{testBusy=false;if(draft)render();}});test.disabled=testBusy;parent.append(test,result);
    }
    async function refreshCounters(){
        if(countersLoading)return;countersLoading=true;counterFeedback='';renderCounters();
        try{knownCounters=(await request(null,endpoint+'/counters')).counters||{};counterFeedback='Saved values refreshed.';}
        catch(error){counterFeedback=error.message;}
        finally{countersLoading=false;renderCounters();}
    }
    const counterOverlay=root.querySelector('[data-counter-overlay]');
    function closeCounters(){
        if(counterSaving)return;
        counterOverlay.hidden=true;counterOpen=false;
        document.body.classList.remove('cc-counters-open');
        counterOpener?.focus();
    }
    async function openCounters(){
        if(!loaded)return;
        counterOpener=document.activeElement;counterOverlay.hidden=false;counterOpen=true;
        root.querySelector('[data-counter-close]').focus();
        await refreshCounters();
    }
    root.querySelector('[data-command-manage-counters]').addEventListener('click',()=>run(openCounters));
    root.querySelector('[data-counter-close]').addEventListener('click',closeCounters);
    counterOverlay.addEventListener('click',event=>{if(event.target===counterOverlay)closeCounters();});
    counterOverlay.addEventListener('keydown',event=>{
        if(event.key==='Escape'){event.preventDefault();event.stopPropagation();closeCounters();return;}
        if(event.key!=='Tab')return;
        const controls=[...counterOverlay.querySelectorAll('button:not(:disabled),input:not(:disabled)')];
        const first=controls[0],last=controls[controls.length-1];
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    });
    async function saveCounter(name,value){
        if(counterSaving)return;
        if(!Number.isSafeInteger(value)||Math.abs(value)>1000000000000){counterFeedback='Enter a whole number between -1 trillion and 1 trillion.';renderCounters();return;}
        counterSaving=true;
        try{
            const result=await request({name,value:String(value)},endpoint+'/counters');
            knownCounters[name]=result.value;counterFeedback='Saved '+name+'.';
        }catch(error){counterFeedback=error.message;}
        finally{counterSaving=false;renderCounters();}
    }
    function renderCounters(){
        const panel=root.querySelector('[data-command-counters]');if(!panel||!counterOpen)return;panel.replaceChildren();
        const header=el('div',undefined,'cc-header');header.append(el('h4','Channel counters'));
        const refresh=button(countersLoading?'Refreshing…':'Refresh counters',refreshCounters);refresh.disabled=countersLoading||!loaded||counterSaving;header.append(refresh);panel.append(header);
        panel.append(el('p','Shared across your commands and saved across streams. Refresh to see changes from chat.','cc-hint'));
        const usage=new Map();
        for(const item of items)for(const name of M.counterReferences(item.command.blocks)){
            if(!usage.has(name))usage.set(name,[]);usage.get(name).push('!'+item.command.name+(item.command.enabled?'':' (disabled)'));
        }
        const names=[...new Set([...Object.keys(knownCounters),...usage.keys()])].sort();
        if(!loaded)panel.append(el('p','Loading counters…','cc-hint'));
        else if(!names.length)panel.append(el('p','No counters yet. Add a Counter block to a command to get started.','cc-hint'));
        else{const grid=el('div',undefined,'cc-counter-grid');
            for(const name of names){
                const card=el('article',undefined,'cc-counter-card');
                const current=Object.hasOwn(knownCounters,name)?knownCounters[name]:0;
                card.append(el('code',name),el('strong',String(current),'cc-counter-value'),el('p',usage.has(name)?'Used by '+usage.get(name).join(', '):'Not used by saved commands','cc-hint'));
                const actions=el('div',undefined,'cc-counter-actions'),input=el('input');
                input.type='number';input.step='1';input.min='-1000000000000';input.max='1000000000000';input.value=String(current);input.setAttribute('aria-label','Value for '+name);
                const save=button('Save',()=>saveCounter(name,Number(input.value)));
                const reset=button('Reset',()=>{if(confirm('Reset counter '+name+' to 0?'))return saveCounter(name,0);});
                input.disabled=counterSaving;save.disabled=counterSaving;reset.disabled=counterSaving;
                actions.append(input,save,reset);card.append(actions);grid.append(card);
            }panel.append(grid);}
        const feedback=el('p',counterFeedback,'cc-hint');feedback.setAttribute('role','status');panel.append(feedback);
    }
    function render(){
        renderCounters();
        dismissMenu();
        document.body.classList.toggle('cc-fullscreen-open',expanded&&!!draft);list.replaceChildren();root.querySelector('[data-command-new]').disabled=busy||loading;root.querySelector('[data-command-manage-counters]').disabled=!loaded||busy||loading;
        const rows=items.slice();if(draft&&selected.revision===0)rows.push(selected);
        if(!rows.length)list.append(el('p','No custom commands yet. Add a command to start building.','cc-empty'));
        for(const item of rows){const isOpen=draft&&selected===item, article=el('article',undefined,'cc-command'),row=el('div',undefined,'cc-row');
            row.append(el('strong','!'+(isOpen?draft.name||'new-command':item.command.name)),button(isOpen?'Close':'Edit',()=>isOpen?close():open(item)));
            const enabled=isOpen?draft.enabled:item.command.enabled, toggle=button(enabled?'Enabled':'Disabled',()=>{if(isOpen){draft.enabled=!draft.enabled;mark();render();}else if(leave())return mutate('save',{...item.command,enabled:!enabled},item.revision);},`state-toggle cc-toggle ${enabled?'live':'is-off'}`);toggle.setAttribute('role','switch');toggle.setAttribute('aria-label',`Enable ${item.command.name||'new command'}`);toggle.setAttribute('aria-checked',String(enabled));row.append(toggle);row.querySelectorAll('button').forEach(b=>b.disabled=busy);article.append(row);list.append(article);if(!isOpen)continue;
            const editor=el('div',undefined,'cc-editor'+(expanded?' cc-expanded':'')),controls=el('fieldset');controls.disabled=busy;editor.append(controls);article.append(editor);
            const top=el('div',undefined,'cc-editor-header');top.append(el('strong',expanded?'Command sandbox':'Command editor'),button(expanded?'Exit full screen':'Full screen',()=>{expanded=!expanded;render();}));if(expanded){const stateToggle=button(draft.enabled?'Enabled':'Disabled',()=>{draft.enabled=!draft.enabled;mark();render();},`state-toggle cc-toggle ${draft.enabled?'live':'is-off'}`);stateToggle.setAttribute('role','switch');stateToggle.setAttribute('aria-label','Enable command');stateToggle.setAttribute('aria-checked',String(draft.enabled));top.insertBefore(stateToggle,top.lastChild);}controls.append(top);
            const feedback=el('p',status.textContent,status.classList.contains('cc-error')?'cc-error':'');feedback.dataset.commandFeedback='';feedback.setAttribute('role','status');controls.append(feedback);
            const settings=el('div',undefined,'cc-settings');field(settings,'Command name (without !)',draft.name,v=>draft.name=v).maxLength=32;field(settings,'Who can use it?',draft.permission,v=>draft.permission=v,{everyone:'Everyone',moderator:'Moderators and broadcaster',broadcaster:'Broadcaster only'});const cd=field(settings,'Channel cooldown (seconds)',draft.cooldown,v=>draft.cooldown=Number(v));cd.type='number';cd.min=0;cd.max=3600;controls.append(settings);
            const workspace=el('div',undefined,'cc-studio'),toolbox=el('aside',undefined,'cc-toolbox');toolbox.append(el('h4','Blocks'));
            for(const [type,name]of Object.entries(names)){const b=button('+ '+name,()=>add(type));b.draggable=true;b.addEventListener('dragstart',e=>e.dataTransfer.setData('text/plain',type));toolbox.append(b);}toolbox.append(el('p','Drag a block onto the canvas, or choose a branch and click to add.','cc-hint'));
            const canvas=el('div',undefined,'cc-stage'),right=el('aside',undefined,'cc-sidebar'),inspector=el('div',undefined,'cc-inspector'),test=el('div',undefined,'cc-test');renderCanvas(canvas);renderInspector(inspector);renderTest(test);right.append(inspector,test);workspace.append(toolbox,canvas,right);controls.append(workspace);
            const actions=el('div',undefined,'cc-actions'),state=el('span',dirty?'Unsaved changes':'');state.dataset.commandDirty='';actions.append(button('Save',()=>mutate('save',structuredClone(draft),item.revision,item.command.name||draft.name),'button primary'),button('Cancel',close),state);
            if(item.revision)actions.append(button('Delete',()=>{if(confirm('Delete this command?'))return mutate('delete',item.command,item.revision);},'button danger'));controls.append(actions);
        }
    }
    root.querySelector('[data-command-new]').addEventListener('click',()=>{if(!busy&&!loading)open({command:{name:'',enabled:false,permission:'everyone',cooldown:0,blocks:[create('reply')]},revision:0});});
    document.querySelector('[data-workspace-tab="commands"]').addEventListener('click',()=>run(async()=>{if(loaded){await refreshCounters();return;}if(loading)return;loading=true;render();try{const response=await request();items=response.items;knownCounters=response.counters||{};loaded=true;}finally{loading=false;render();}}));
    window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
    document.addEventListener('pointerdown',e=>{if(menu&&!menu.contains(e.target))dismissMenu();});
    window.addEventListener('resize',()=>dismissMenu());
    document.addEventListener('scroll',()=>dismissMenu(),true);
    document.addEventListener('keydown',e=>{if(menu){if(e.key==='Escape'){e.preventDefault();e.stopPropagation();dismissMenu(true);return;}if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();const buttons=[...menu.querySelectorAll('button:not(:disabled)')],i=buttons.indexOf(document.activeElement);buttons[e.key==='Home'?0:e.key==='End'?buttons.length-1:(i+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length]?.focus();return;}if(e.key==='Tab')dismissMenu();}if(e.key==='Escape'&&expanded&&!busy){expanded=false;render();}});
})();

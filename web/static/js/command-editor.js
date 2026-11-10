(() => {
    'use strict';
    const root = document.querySelector('[data-command-editor]');
    if (!root) return;
    const list = root.querySelector('[data-command-list]'), status = root.querySelector('[data-command-status]');
    const endpoint = (document.body.dataset.channelRoot || '/channel') + '/api/for-you/commands';
    const csrf = root.closest('[data-workspace-page]').dataset.csrf;
    let items = [], selected = null, draft = null, dirty = false, busy = false, loaded = false, expanded = false;
    let testArgs = '', testRole = 'everyone';
    const names = {reply:'Send message', if:'If / else', random:'Random message', repeat:'Repeat'};
    const defaults = type => type === 'reply' ? {type, message:'Hello, {user}!'} : type === 'if' ? {type, condition:'has_argument', value:'', then:[], else:[]} : type === 'random' ? {type, choices:['Yes!', 'No!']} : {type, count:2, blocks:[]};
    function el(tag, text, cls) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (cls) node.className = cls; return node; }
    function notify(text, error=false) { status.textContent = text; status.classList.toggle('cc-error', error); root.querySelectorAll('[data-command-feedback]').forEach(node=>{node.textContent=text;node.classList.toggle('cc-error',error);}); }
    const run = fn => Promise.resolve().then(fn).catch(e => notify(e.message, true));
    function button(text, action, cls='button secondary') { const b = el('button', text, cls); b.type='button'; b.addEventListener('click', () => run(action)); return b; }
    function mark() { dirty=true; root.querySelector('[data-command-dirty]').textContent='Unsaved changes'; }
    function leave() { return !dirty || confirm('Discard your unsaved command changes?'); }
    async function request(data) {
        const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 15000);
        try {
            const response = await fetch(endpoint, {method:data?'POST':'GET', credentials:'same-origin', cache:'no-store', signal:controller.signal,
                ...(data ? {body:new URLSearchParams({csrf_token:csrf, ...data})} : {})});
            const result = await response.json();
            if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Please check the command fields.');
            return result;
        } catch (e) { if (e.name === 'AbortError') throw new Error('Request timed out. Reload before retrying a save.'); throw e; }
        finally { clearTimeout(timer); }
    }
    function field(parent, label, value, update, options) {
        const wrap=el('label', label), input=el(options ? 'select':'input');
        if(options) for(const [key,text] of Object.entries(options)) { const option=el('option',text); option.value=key; input.append(option); }
        input.value=value; input.addEventListener(options?'change':'input', () => {update(input.value); mark();}); wrap.append(input); parent.append(wrap); return input;
    }
    function message(parent, value, update, label='Message') {
        const wrap=el('label',label), input=el('textarea'); input.rows=2; input.maxLength=450; input.value=value;
        input.addEventListener('input',()=>{update(input.value);mark();}); wrap.append(input);parent.append(wrap);
        const picker=el('select');picker.setAttribute('aria-label','Insert a value');
        for(const name of ['', 'user','channel','args','arg1']) { const option=el('option',name?`{${name}}`:'Insert a value…'); option.value=name;picker.append(option); }
        picker.addEventListener('change',()=>{if(!picker.value)return; const text=`{${picker.value}}`;input.setRangeText(text,input.selectionStart,input.selectionEnd,'end');update(input.value);mark();picker.value='';input.focus();});parent.append(picker);
    }
    function sequence(blocks, parent, depth=0) {
        const seq=el('div',undefined,'cc-sequence');parent.append(seq);
        blocks.forEach((block,index)=>{
            const card=el('div',undefined,`cc-block cc-${block.type}`), tools=el('div',undefined,'cc-tools');
            tools.append(el('strong',names[block.type]));
            for(const [label,offset] of [['↑',-1],['↓',1]]) {const move=button(label,()=>{[blocks[index],blocks[index+offset]]=[blocks[index+offset],blocks[index]];mark();render();});move.disabled=index+offset<0||index+offset>=blocks.length;move.setAttribute('aria-label',`Move ${names[block.type]} ${offset<0?'up':'down'}`);tools.append(move);}
            tools.append(button('Remove',()=>{blocks.splice(index,1);mark();render();}));card.append(tools);seq.append(card);
            if(block.type==='reply')message(card,block.message,v=>block.message=v);
            if(block.type==='random') {
                block.choices.forEach((choice,i)=>message(card,choice,v=>block.choices[i]=v,`Choice ${i+1}`));
                if(block.choices.length<5)card.append(button('+ Choice',()=>{block.choices.push('Another response');mark();render();}));
                if(block.choices.length>1)card.append(button('Remove last choice',()=>{block.choices.pop();mark();render();}));
            }
            if(block.type==='if') {
                field(card,'Condition',block.condition,v=>{block.condition=v;render();},{has_argument:'An argument was provided',argument_equals:'Arguments equal',is_moderator:'Viewer is a moderator or broadcaster',is_broadcaster:'Viewer is the broadcaster'});
                if(block.condition==='argument_equals')field(card,'Compare with',block.value,v=>block.value=v).maxLength=100;
                for(const [key,label] of [['then','True'],['else','False']]) {card.append(el('p',label,'cc-branch-title'));sequence(block[key],card,depth+1);}
            }
            if(block.type==='repeat') { const input=field(card,'Number of repeats',block.count,v=>block.count=Number(v));input.type='number';input.min=1;input.max=5;sequence(block.blocks,card,depth+1); }
        });
        if(depth<=6) {
            const add=el('div',undefined,'cc-add'), select=el('select');select.setAttribute('aria-label','Block to add');
            for(const [type,name] of Object.entries(names)){if(depth===6&&['if','repeat'].includes(type))continue;const option=el('option',name);option.value=type;select.append(option);}
            add.append(select,button('+ Add block',()=>{blocks.push(defaults(select.value));mark();render();}));seq.append(add);
        }
    }
    async function mutate(action, command, revision) {
        if(busy)return;
        busy=true; render();
        try {
            const result=await request({action,definition:JSON.stringify(command),revision});
            if(action==='delete')items=items.filter(item=>item.command.name!==command.name);
            else {const item={command:structuredClone(command),revision:result.revision};const index=items.findIndex(x=>x.command.name===command.name);if(index<0)items.push(item);else items[index]=item;}
            dirty=false;draft=null;selected=null;expanded=false;notify(action==='delete'?'Command deleted.':'Command saved.');
        } finally {busy=false;render();}
    }
    function open(item) { if(busy||!leave())return;selected=item;draft=structuredClone(item.command);testArgs='';testRole='everyone';notify('');dirty=false;expanded=false;render(); }
    function render() {
        list.replaceChildren(); root.querySelector('[data-command-new]').disabled=busy;
        const rows=items.slice();if(draft&&selected.revision===0)rows.push(selected);
        if(!rows.length)list.append(el('p','No custom commands yet. Add a command to start building.','cc-hint'));
        for(const item of rows) {
            const active=draft&&selected===item, article=el('article',undefined,'cc-command'), row=el('div',undefined,'cc-row');
            row.append(el('strong','!'+(active?draft.name:item.command.name)),button(active?'Close':'Edit',()=>{if(active){if(!leave())return;draft=null;selected=null;dirty=false;expanded=false;render();}else open(item);}));
            const toggleLabel=el('label','Enabled'), toggle=el('input');toggle.type='checkbox';toggle.checked=item.command.enabled;toggle.disabled=busy||!!draft;
            toggle.addEventListener('change',()=>run(()=>mutate('save',{...item.command,enabled:toggle.checked},item.revision)));toggleLabel.append(toggle);row.append(toggleLabel);article.append(row);list.append(article);
            row.querySelectorAll('button').forEach(b=>b.disabled=busy);
            if(!active)continue;
            const editor=el('div',undefined,'cc-editor'+(expanded?' cc-expanded':'')), controls=el('fieldset');controls.disabled=busy;editor.append(controls);article.append(editor);
            const top=el('div',undefined,'cc-tools');top.append(el('strong','Command editor'),button(expanded?'Exit full screen':'Full screen',()=>{expanded=!expanded;render();}));controls.append(top);
            const feedback=el('p',status.textContent,status.classList.contains('cc-error')?'cc-error':'');feedback.dataset.commandFeedback='';feedback.setAttribute('role','status');controls.append(feedback);
            const settings=el('div',undefined,'cc-settings');controls.append(settings);
            const name=field(settings,'Command name (without !)',draft.name,v=>draft.name=v);name.maxLength=32;name.disabled=item.revision>0;
            field(settings,'Who can use it?',draft.permission,v=>draft.permission=v,{everyone:'Everyone',moderator:'Moderators and broadcaster',broadcaster:'Broadcaster only'});
            const cooldown=field(settings,'Channel cooldown (seconds)',draft.cooldown,v=>draft.cooldown=Number(v));cooldown.type='number';cooldown.min=10;cooldown.max=3600;
            const canvas=el('div',undefined,'cc-canvas');canvas.append(el('div','When this command is used','cc-trigger'));sequence(draft.blocks,canvas);controls.append(canvas);
            controls.append(el('p','Up to 40 blocks, 64 executed steps and 3 messages per use. Repeat blocks share these limits.','cc-hint'));
            const actions=el('div',undefined,'cc-actions'), state=el('span',dirty?'Unsaved changes':'');state.dataset.commandDirty='';
            actions.append(button('Save',()=>mutate('save',structuredClone(draft),item.revision),'button primary'),button('Cancel',()=>{if(!leave())return;draft=null;selected=null;dirty=false;expanded=false;render();}),state);
            if(item.revision>0)actions.append(button('Delete',()=>{if(confirm('Delete this command?'))return mutate('delete',item.command,item.revision);},'button danger'));
            controls.append(actions);
            const test=el('div',undefined,'cc-test'), fields=el('div',undefined,'cc-test-inputs');test.append(el('h4','Test command'),el('p','Preview only. Nothing is sent to Twitch.','cc-hint'),fields);
            // Test fields do not modify the saved command.
            const args=el('input');args.maxLength=500;args.value=testArgs;args.setAttribute('aria-label','Test arguments');args.placeholder='Arguments after the command';args.addEventListener('input',()=>testArgs=args.value);fields.append(args);
            const role=el('select');role.setAttribute('aria-label','Test viewer role');for(const name of ['everyone','moderator','broadcaster']){const o=el('option',name);o.value=name;role.append(o);}role.value=testRole;role.addEventListener('change',()=>testRole=role.value);fields.append(role);
            const result=el('div');result.setAttribute('role','status');
            const testButton=button('Run test',async()=>{testButton.disabled=true;try{const response=await request({action:'test',definition:JSON.stringify(draft),args:testArgs,role:testRole});result.replaceChildren(el('pre',response.trace.join('\n'),'cc-result'),el('pre',response.messages.join('\n')||'No messages.','cc-result'));}finally{testButton.disabled=false;}});fields.append(testButton);test.append(result);controls.append(test);
        }
    }
    root.querySelector('[data-command-new]').addEventListener('click',()=>{if(busy)return;const command={name:'',enabled:false,permission:'everyone',cooldown:30,blocks:[defaults('reply')]};open({command,revision:0});});
    document.querySelector('[data-workspace-tab="commands"]').addEventListener('click',()=>run(async()=>{if(loaded)return;const result=await request();items=result.items;loaded=true;render();}));
    window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&expanded&&!busy){expanded=false;render();}});
})();

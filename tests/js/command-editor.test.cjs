const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({chromium} = require('playwright')); } catch {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();

test('command editor builds branches, preserves drafts, tests without saving and recovers failed saves', {skip:!chromium || !fs.existsSync(executablePath || '')}, async()=>{
    const browser = await chromium.launch({executablePath, headless:true, args:['--no-sandbox']});
    try {
        const page = await browser.newPage({viewport:{width:1280,height:1000}});
        const errors=[];page.on('pageerror',e=>errors.push(e.message));
        const calls=[];let failSave=true;
        await page.route('http://editor.test/**',async route=>{
            if(!route.request().url().endsWith('/commands'))return route.fulfill({body:'<html></html>',contentType:'text/html'});
            const data=new URLSearchParams(route.request().postData()||'');calls.push(data.get('action')||'list');
            if(route.request().method()==='GET')return route.fulfill({json:{items:[]}});
            if(data.get('action')==='test')return route.fulfill({json:{messages:['Welcome Guest!'],trace:['has_argument: True','Send message']}});
            if(failSave){failSave=false;return route.fulfill({status:409,json:{detail:'Reload before saving.'}});}
            return route.fulfill({json:{revision:1}});
        });
        await page.goto('http://editor.test/channel/for-you');
        await page.setContent(`<body><main style="max-width:1100px;margin:40px auto;padding:20px"><h2>For You</h2><div data-workspace-page data-csrf="secret"><button data-workspace-tab="commands">Custom Commands</button>${fs.readFileSync('web/templates/channel/command_editor.html','utf8')}</div></main></body>`);
        for(const path of ['web/static/css/style.css','web/static/css/command-editor.css'])await page.addStyleTag({path});
        await page.addScriptTag({path:'web/static/js/command-editor.js'});
        await page.getByRole('button',{name:'Custom Commands',exact:true}).click();
        await page.getByRole('button',{name:'+ Add command',exact:true}).click();
        await page.getByLabel('Command name (without !)').fill('welcome');
        await page.getByLabel('Message',{exact:true}).fill('Hello {user}');
        await page.getByLabel('Block to add').selectOption('if');
        await page.getByRole('button',{name:'+ Add block',exact:true}).click();
        const branches=page.locator('.cc-if .cc-sequence');
        await branches.nth(0).getByLabel('Block to add').selectOption('reply');
        await branches.nth(0).getByRole('button',{name:'+ Add block',exact:true}).click();
        await branches.nth(0).getByLabel('Message',{exact:true}).fill('Welcome {arg1}!');
        await page.getByLabel('Test arguments').fill('Guest');
        await page.getByRole('button',{name:'Run test',exact:true}).click();
        await page.getByText('Welcome Guest!',{exact:true}).waitFor();
        assert.deepEqual(calls,['list','test']);
        await page.getByRole('button',{name:'Full screen',exact:true}).click();
        assert.equal(await page.locator('.cc-expanded').count(),1);
        await page.keyboard.press('Escape');assert.equal(await page.locator('.cc-expanded').count(),0);
        await page.getByRole('button',{name:'Save',exact:true}).click();
        await page.getByText('Reload before saving.',{exact:true}).first().waitFor();
        assert.equal(await page.getByLabel('Command name (without !)').inputValue(),'welcome');
        page.once('dialog',dialog=>dialog.dismiss());
        await page.getByRole('button',{name:'Cancel',exact:true}).click();
        assert.equal(await page.locator('.cc-editor').count(),1);
        if(process.env.COMMAND_EDITOR_SCREENSHOT)await page.screenshot({path:process.env.COMMAND_EDITOR_SCREENSHOT,fullPage:true});
        await page.getByRole('button',{name:'Save',exact:true}).click();
        await page.getByText('Command saved.',{exact:true}).waitFor();
        assert.equal(await page.locator('.cc-editor').count(),0);
        assert.equal(await page.getByRole('checkbox',{name:'Enabled',exact:true}).isChecked(),false);
        await page.getByRole('button',{name:'Edit',exact:true}).click();
        assert.equal(await page.getByLabel('Command name (without !)').isDisabled(),true);
        assert.deepEqual(errors,[]);
    } finally {await browser.close();}
});

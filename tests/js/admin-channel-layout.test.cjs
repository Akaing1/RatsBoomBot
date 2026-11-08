const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {execFileSync} = require('node:child_process');
const http = require('node:http');
let chromium;
try { ({chromium} = require('playwright')); } catch (_) {}
const executablePath = process.env.CHAT_TEST_BROWSER_PATH || chromium?.executablePath();
const options = {skip: !chromium || !fs.existsSync(executablePath || '')};
function fixtures() {
    return JSON.parse(execFileSync(process.env.PYTHON || 'python', ['-c', `
import json
from types import SimpleNamespace
from starlette.requests import Request
from bot.profiles import ChannelProfile, activate_profile
from bot.services.channels.feature_toggle import FeatureToggleService
from web.channel.settings_book import build_settings_sections
from web.shared.common import templates, build_admin_context
activate_profile('123', ChannelProfile(channel_name='test'))
f=FeatureToggleService(None)
s=build_settings_sections({},f.get_channel_features('123'),f.get_profile_features('123'),f.get_global_groups('123'),f.get_global_commands('123'))
r=Request({'type':'http','method':'GET','path':'/admin/channels/123/settings','query_string':b'','headers':[],'session':{}})
c=build_admin_context(r,active_page='channels',channel_section='settings',channel_root='/admin/channels/123',settings_sections=s,broadcaster=SimpleNamespace(id='123',name='Test',login='test',is_live=False),customization_action='/admin/channels/123/customization',channel_settings=SimpleNamespace(),protected_users=[],profile_features={},chat_identity={'connected':False,'premium_enabled':False},url_for=lambda name,path:'/static'+path,twitch_channel_metadata={'title':'Test stream','game':'Games'})
print(json.dumps({key:templates.TemplateResponse(request=r,name='admin/channel_'+key+'.html',context=c).body.decode() for key in ('settings','monitor')}))
`], {encoding:'utf8', env:{...process.env, SESSION_SECRET:'admin-layout-test'}}));
}
async function browserPage(browser, html, url) {
    const page = await browser.newPage({viewport:{width:1500,height:950},reducedMotion:'reduce'});
    await page.route('http://admin.test/**', route => route.fulfill({contentType:'text/html',body:'<html></html>'}));
    await page.goto('http://admin.test'+url);
    await page.setContent(html.replace(/<script[\s\S]*?<\/script>/g,'').replace(/<link[^>]*>/g,''));
    await page.addStyleTag({path:'web/static/css/style.css'});
    return page;
}

test('admin settings switches stay on admin routes and navigation initializes', options, async () => {
    const html=fixtures().settings;
    const browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
    let submitted;
    const server=http.createServer(async (request,response)=>{
        if(request.method==='POST'){
            assert.equal(request.url,'/admin/channels/123/toggles');
            const chunks=[];for await(const chunk of request)chunks.push(chunk);submitted=Buffer.concat(chunks).toString();
            response.writeHead(303,{location:'/admin/channels/123/settings?toggle_result=success&toggle_message=Saved'});response.end();
        }else{response.writeHead(200,{'Content-Type':'text/html'});response.end(html.replace(/<script[\s\S]*?<\/script>/g,'').replace(/<link[^>]*>/g,''));}
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    try {
        const page=await browser.newPage({viewport:{width:1500,height:950},reducedMotion:'reduce'});
        await page.goto(`http://127.0.0.1:${server.address().port}/admin/channels/123/settings`);
        await page.addStyleTag({path:'web/static/css/style.css'});
        const errors=[]; page.on('pageerror',error=>errors.push(error.message));
        await page.addStyleTag({path:'web/static/css/channel-settings.css'});
        await page.addStyleTag({path:'web/static/css/admin-channel-settings.css'});
        await page.addScriptTag({path:'web/static/js/channel-settings.js'});
        await page.addScriptTag({path:'web/static/js/settings-save.js'});
        await page.addScriptTag({path:'web/static/js/settings-finder.js'});
        await page.locator('#settings-control-feature-channel').click();
        await page.waitForFunction(()=>document.querySelector('.settings-floating-status')?.textContent==='Saved',null,{timeout:3000}).catch(async error=>{throw new Error(JSON.stringify({errors,submitted,status:await page.locator('.settings-floating-status').textContent()}));});
        assert.match(submitted,/name="toggle_type"\r?\n\r?\nfeature/);
        assert.match(submitted,/name="action"\r?\n\r?\ndisable/);
        assert.match(submitted,/name="csrf_token"/);
        assert.equal(new URL(page.url()).pathname,'/admin/channels/123/settings');
        await page.locator('[data-settings-tab="chat"]').click();
        assert.equal(await page.locator('[data-settings-page="chat"]').isVisible(),true);
        assert.equal(new URL(page.url()).searchParams.get('section'),'chat');
        assert.deepEqual(errors,[]);
    } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
});

test('monitor feeds scroll without growing the page on desktop and mobile', options, async () => {
    const browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
    try {
        const page=await browserPage(browser,fixtures().monitor,'/admin/channels/123/monitor');
        await page.addStyleTag({path:'web/static/css/admin-channel-monitor.css'});
        await page.evaluate(()=>{window.EventSource=class {addEventListener(){} close(){}};});
        await page.addScriptTag({path:'web/static/js/live-chat-feed.js'});
        for(const width of [1500,900,390]) {
            await page.setViewportSize({width,height:950});
            const result=await page.evaluate(()=>{
                const feeds=[...document.querySelectorAll('[data-live-chat-feed]')];
                feeds.forEach(feed=>feed.replaceChildren());
                const before=document.documentElement.scrollHeight;
                feeds.forEach(feed=>{for(let i=0;i<200;i++){const row=document.createElement('p');row.textContent='Message '+i+' '+('long chat message '.repeat(10));feed.append(row);}});
                return {before,after:document.documentElement.scrollHeight,feeds:feeds.map(feed=>({height:feed.clientHeight,scroll:feed.scrollHeight,overflow:getComputedStyle(feed).overflowY}))};
            });
            assert.equal(result.after,result.before,`page height changed at ${width}px`);
            for(const feed of result.feeds){assert.ok(feed.height>0);assert.ok(feed.scroll>feed.height);assert.equal(feed.overflow,'auto');}
            if(width===1500 && process.env.ADMIN_LAYOUT_SCREENSHOT)await page.screenshot({path:process.env.ADMIN_LAYOUT_SCREENSHOT,fullPage:true});
        }

    } finally {await browser.close();}
});

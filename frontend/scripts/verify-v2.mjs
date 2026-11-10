// Actual authenticated merchant HTTP API -> React review -> real isolated ledger -> fulfillment.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { mkdtemp,mkdir } from 'node:fs/promises';
import { randomBytes } from 'node:crypto';
import { tmpdir } from 'node:os';
import { resolve,join } from 'node:path';
import assert from 'node:assert/strict';
const folder=await mkdtemp(join(tmpdir(),'wallet-v2-'));const railKey=randomBytes(32).toString('hex'),foodKey=randomBytes(32).toString('hex');
const env={...process.env,DATABASE_URL:`sqlite:///${join(folder,'v2-browser-wallet.db').replaceAll('\\','/')}`,REQUIRE_WALLET_LOGIN:'true',WALLET_SESSION_SECRET:'isolated-v2-browser-test-secret-32-characters',DEMO_WALLET_PIN:'123456',NVIDIA_ENABLED:'false',PAYPAL_ENABLED:'false',TEST_DATABASE_URL:'',V2_RAIL_KEY:railKey,V2_FOOD_KEY:foodKey};
const startBackend=()=>spawn('python',['-m','scripts.serve_v2_verification'],{cwd:resolve('../backend'),env,windowsHide:true,stdio:'ignore'});
let backend=startBackend();
const web=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5195','--strictPort'],{windowsHide:true,stdio:'ignore'});
const output=resolve('../artifacts/v2-review');await mkdir(output,{recursive:true});let browser;const merchantServers=[];
async function merchant(id,key,path,method='GET',body){const response=await fetch(`http://127.0.0.1:8195/api/merchant/v1${path}`,{method,headers:{'Content-Type':'application/json','X-Merchant-Id':id,'X-Merchant-Key':key,'Idempotency-Key':`browser-${id}-order-001`},...(body?{body:JSON.stringify(body)}:{})});assert.equal(response.status,200);return response.json();}
try{
  for(let n=0;n<200;n++){try{const r=await fetch('http://127.0.0.1:8195/health');if(r.ok){await fetch('http://127.0.0.1:5195');break;}}catch{}if(backend.exitCode!==null)throw Error('Isolated V2 API exited');await new Promise(r=>setTimeout(r,100));}
  const created=[];
  for(const [id,key,description,amount] of [['demo-railway',railKey,'Simulated train ticket',125000],['demo-food',foodKey,'Simulated food order',40000]]){
    const body={order_reference:'browser-order-001',amount,currency:'INR',description,expires_at:new Date(Date.now()+12*60000).toISOString()};
    const first=await merchant(id,key,'/checkout-requests','POST',body);const retry=await merchant(id,key,'/checkout-requests','POST',body);assert.equal(first.payment_request_id,retry.payment_request_id);created.push(first);
  }
  const exited=new Promise(resolve=>backend.once('exit',resolve));backend.kill();await exited;env.V2_REOPEN_VERIFY='true';backend=startBackend();
  for(let n=0;n<200;n++){try{if((await fetch('http://127.0.0.1:8195/health')).ok)break;}catch{}if(backend.exitCode!==null)throw Error('Restarted API exited');await new Promise(r=>setTimeout(r,100));}
  for(const [index,id,key] of [[0,'demo-railway',railKey],[1,'demo-food',foodKey]])assert.equal((await merchant(id,key,'/orders/browser-order-001')).payment_request_id,created[index].payment_request_id);
  browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{window.EventSource=class{close(){}};});
  await page.route('https://**/*',r=>r.abort());
  await page.route('**/api/**',route=>{const u=new URL(route.request().url());return route.continue({url:`http://127.0.0.1:8195${u.pathname}${u.search}`});});
  await page.goto('http://127.0.0.1:5195');await page.locator('input[type="password"]').fill('123456');await page.getByRole('button',{name:'Unlock wallet',exact:true}).click();
  await page.getByRole('region',{name:'Payment reminders'}).getByText('Demo Railway',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Type instead',exact:true}).click();
  await page.getByLabel('Ask about your wallet or payments').fill('Pay my railway and food requests');await page.getByRole('button',{name:'Send request'}).click();
  const review=page.getByRole('region',{name:'Exact payment review'});await review.getByText('Demo Railway',{exact:true}).waitFor();await review.getByText('Demo Kitchen',{exact:true}).waitFor();
  await review.screenshot({path:join(output,'merchant-review-1440.png')});await page.setViewportSize({width:390,height:1000});assert.ok(await review.evaluate(e=>e.scrollWidth<=e.clientWidth));await review.screenshot({path:join(output,'merchant-review-390.png')});
  await review.getByLabel('Six-digit wallet PIN').fill('123456');await review.getByRole('button',{name:'Approve exact payments',exact:true}).evaluate(b=>{b.click();b.click();});
  await review.getByRole('heading',{name:'All selected payments completed',exact:true}).waitFor();assert.equal(await review.getByText('Payment receipt',{exact:true}).count(),2);
  await review.screenshot({path:join(output,'merchant-receipts-390.png')});
  for(const [id,key] of [['demo-railway',railKey],['demo-food',foodKey]]){const paid=await merchant(id,key,'/orders/browser-order-001');assert.equal(paid.order_status,'PAYMENT_CONFIRMED');assert.equal(paid.fulfilled_at,null);const fulfilled=await merchant(id,key,'/orders/browser-order-001/fulfillment','POST');assert.equal(fulfilled.order_status,'FULFILLED');}
  const balance=await page.evaluate(async()=>{const r=await fetch('/api/wallet');return r.json();});assert.equal(balance.posted_balance,835000);assert.equal(balance.reserved_amount,0);assert.deepEqual(errors,[]);
  for(const [kind,key,port] of [['railway',railKey,8196],['food',foodKey,8197]]){
    const server=spawn('python',[resolve('../examples/merchant-client/demo_server.py'),kind,'--port',String(port),'--wallet-url','http://127.0.0.1:8195'],{env:{...process.env,MERCHANT_KEY:key},windowsHide:true,stdio:'ignore'});merchantServers.push(server);
    for(let n=0;n<100;n++){try{if((await fetch(`http://127.0.0.1:${port}`)).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
    const checkout=await browser.newPage({viewport:{width:390,height:900}});await checkout.goto(`http://127.0.0.1:${port}`);
    await checkout.getByRole('button',{name:'Save request to Wallet-Voice',exact:true}).click();await checkout.locator('#status').filter({hasText:'Saved in Wallet-Voice'}).waitFor();
    const original=JSON.parse(await checkout.locator('#details').textContent());assert.equal(original.mode,'SIMULATED');assert.ok(await checkout.getByRole('button',{name:'Confirm simulated fulfillment'}).isDisabled());
    await checkout.getByRole('button',{name:'Save request to Wallet-Voice',exact:true}).click();await checkout.waitForTimeout(200);assert.equal(JSON.parse(await checkout.locator('#details').textContent()).payment_request_id,original.payment_request_id);
    assert.ok(await checkout.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await checkout.screenshot({path:join(output,`${kind}-checkout-390.png`),fullPage:true});await checkout.close();
  }
  console.log('PASSED: two authenticated merchant HTTP checkouts, immutable retry, actual API process restart, saved attention, typed conversational batch, desktop/mobile review, duplicate click, exact PIN, two real journal receipts, authoritative polling, separate fulfillment, both actual local merchant pages at 390px. No live providers or physical microphone.');
}finally{await browser?.close();for(const server of merchantServers)server.kill();web.kill();backend.kill();}

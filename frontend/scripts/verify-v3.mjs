// Real local API/SQLite. Synthetic STT and one test-only uncertain adapter result.
import {chromium} from 'playwright';
import {spawn} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import {mkdtemp,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve,join} from 'node:path';
import assert from 'node:assert/strict';
const folder=await mkdtemp(join(tmpdir(),'wallet-v3-'));const rail=randomBytes(32).toString('hex'),food=randomBytes(32).toString('hex');
const env={...process.env,DATABASE_URL:`sqlite:///${join(folder,'v3-browser-wallet.db').replaceAll('\\','/')}`,REQUIRE_WALLET_LOGIN:'true',WALLET_SESSION_SECRET:'isolated-v3-browser-session-secret-32-characters',DEMO_WALLET_PIN:'123456',NVIDIA_ENABLED:'false',PAYPAL_ENABLED:'false',TEST_DATABASE_URL:'',V3_RAIL_KEY:rail,V3_FOOD_KEY:food};
const backend=spawn('python',['-m','scripts.serve_v3_verification'],{cwd:resolve('../backend'),env,windowsHide:true,stdio:'ignore'});
const web=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5198','--strictPort'],{windowsHide:true,stdio:'ignore'});
const output=resolve('../artifacts/v3-review');await mkdir(output,{recursive:true});let browser;
async function merchant(id,key,path,method='GET',body,idem='v3-'+id){const response=await fetch('http://127.0.0.1:8198/api/merchant/v1'+path,{method,headers:{'Content-Type':'application/json','X-Merchant-Id':id,'X-Merchant-Key':key,'Idempotency-Key':idem},...(body?{body:JSON.stringify(body)}:{})});assert.equal(response.status,200);return response.json();}
try{
  for(let n=0;n<200;n++){try{if((await fetch('http://127.0.0.1:8198/health')).ok){await fetch('http://127.0.0.1:5198');break;}}catch{}if(backend.exitCode!==null)throw Error('V3 isolated API exited');await new Promise(r=>setTimeout(r,100));}
  for(const [id,key,description,amount] of [['demo-railway',rail,'train ticket',125000],['demo-food',food,'food order',40000]])await merchant(id,key,'/checkout-requests','POST',{order_reference:'v3-order',amount,currency:'INR',description,expires_at:new Date(Date.now()+12*60000).toISOString()});
  browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:390,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    window.EventSource=class{close(){}};window.__stopped=0;
    Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async()=>({getTracks:()=>[{stop(){window.__stopped++}}]})});
    window.MediaRecorder=class{static isTypeSupported(){return true}state='inactive';mimeType='audio/webm';start(){this.state='recording'}stop(){this.state='inactive';this.ondataavailable?.({data:new Blob(['fixture speech'],{type:'audio/webm'})});queueMicrotask(()=>this.onstop?.())}};
    window.AudioContext=class{resume(){return Promise.resolve()}close(){return Promise.resolve()}createAnalyser(){return{fftSize:2048,getFloatTimeDomainData:a=>a.fill(0)}}createMediaStreamSource(){return{connect(){}}}};
  });
  await page.route('https://**/*',r=>r.abort());
  await page.route('**/api/**',route=>{const u=new URL(route.request().url());if(u.pathname==='/api/voice/transcribe')return route.fulfill({json:{transcript:'Pay the railway and food orders.',provider:'synthetic-STT-fixture'}});return route.continue({url:'http://127.0.0.1:8198'+u.pathname+u.search});});
  async function call(path,body,method='POST'){return page.evaluate(async({path,body,method})=>{const r=await fetch(path,{method,headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});if(!r.ok)throw Error(`API ${r.status}`);return r.json();},{path,body,method});}
  await page.goto('http://127.0.0.1:5198');await page.locator('input[type=password]').fill('123456');await page.getByRole('button',{name:'Unlock wallet',exact:true}).click();await page.getByRole('button',{name:'Talk to your wallet',exact:true}).waitFor();
  await call('/api/notifications/preferences',{enabled:false},'PATCH');await page.reload();
  const attention=page.getByRole('region',{name:'Payment reminders'});await attention.getByText('Demo Railway',{exact:true}).waitFor();await attention.getByText('Alerts are off. Your saved payments are still here.').waitFor();
  await page.getByText('2 urgent requests',{exact:true}).waitFor();
  await attention.locator('article').filter({hasText:'Demo Railway'}).getByRole('button',{name:'Dismiss',exact:true}).click();
  await page.getByText('1 urgent request',{exact:true}).waitFor();
  await page.locator('.insight-card').getByText('Demo Kitchen',{exact:true}).waitFor();
  await page.getByRole('navigation').getByRole('button',{name:'Payments',exact:true}).click();
  await page.locator('.payment-list').getByText('Demo Railway',{exact:true}).first().waitFor();
  await page.getByRole('navigation').getByRole('button',{name:'Home',exact:true}).click();
  await attention.getByText('Hidden from attention (1)',{exact:true}).click();
  await attention.getByRole('button',{name:'Restore',exact:true}).click();
  await page.getByText('2 urgent requests',{exact:true}).waitFor();
  await page.screenshot({path:join(output,'forgotten-checkout-390.png')});
  await page.getByRole('button',{name:'Talk to your wallet',exact:true}).click();await page.getByRole('button',{name:'Stop recording',exact:true}).click();
  const session=page.getByRole('region',{name:'Wallet conversation'});const review=session.getByRole('region',{name:'Exact payment review'});await review.getByText('Demo Kitchen',{exact:true}).waitFor();
  async function say(text){await session.getByLabel('Ask about your wallet or payments').fill(text);await session.getByRole('button',{name:'Send request'}).click();}
  // Backend tests separately prove invalidation of already PIN-approved old snapshots.
  await say('Actually, just the railway');await review.getByText('Demo Kitchen',{exact:true}).waitFor({state:'hidden'});
  await say('Add the food order');await review.getByText('Demo Kitchen',{exact:true}).waitFor();
  await review.screenshot({path:join(output,'exact-review-390.png')});await session.screenshot({path:join(output,'home-conversation-390.png')});await page.setViewportSize({width:1440,height:1000});await review.screenshot({path:join(output,'exact-review-1440.png')});
  await review.getByLabel('Six-digit wallet PIN').fill('123456');await review.getByRole('button',{name:'Approve exact payments',exact:true}).evaluate(b=>{b.click();b.click()});await review.getByRole('heading',{name:'All selected payments completed'}).waitFor();assert.equal(await review.getByText('Payment receipt',{exact:true}).count(),2);
  for(const [id,key] of [['demo-railway',rail],['demo-food',food]]){const status=await merchant(id,key,'/orders/v3-order');assert.equal(status.order_status,'PAYMENT_CONFIRMED');assert.equal(status.fulfilled_at,null);}
  await page.keyboard.press('Escape');assert.ok(await page.evaluate(()=>window.__stopped>0));
  async function transfer(action,amount,key){const c=await call('/api/security/challenges',{action,amount});const t=await call(`/api/security/challenges/${c.id}/verify`,{pin:'123456'});return call(action==='TOPUP'?'/api/bank/topups':'/api/bank/withdrawals',{amount,idempotency_key:key,approval_token:t.approval_token});}
  await transfer('WITHDRAWAL',600000,'v3-shortfall-withdrawal');
  await merchant('demo-railway',rail,'/checkout-requests','POST',{order_reference:'v3-uncertain',amount:300000,currency:'INR',description:'pending-once train ticket',expires_at:new Date(Date.now()+12*60000).toISOString()},'v3-uncertain-key');
  await page.getByRole('button',{name:'Type instead',exact:true}).click();await say('Pay the railway and food orders'); // Paid historical orders are not eligible matches.
  // Select the actual remaining request directly; review still uses server policy.
  const order=await merchant('demo-railway',rail,'/orders/v3-uncertain');const short=await call('/api/payment-batches',{payment_ids:[order.payment_request_id]});assert.equal(short.funding_shortfall,65000);assert.equal(short.can_authorize,false);
  await transfer('TOPUP',100000,'v3-pin-authorized-funding');
  const fresh=await call('/api/payment-batches',{payment_ids:[order.payment_request_id]});assert.equal(fresh.can_authorize,true);
  // Open that fresh review in the actual assistant via a normal single-request instruction.
  await say('Cancel this review');await say('Pay my train ticket');
  const guardian=session.getByRole('region',{name:'Payment Guardian'});await guardian.getByRole('button',{name:'Confirm action',exact:true}).click();
  await review.getByLabel('Six-digit wallet PIN').fill('123456');await review.getByRole('button',{name:'Approve exact payments',exact:true}).click();await review.getByRole('heading',{name:'Payments processing',exact:true}).waitFor();assert.equal(await review.getByText('Payment receipt',{exact:true}).count(),0);
  await call('/api/test/reconcile',{});await review.getByRole('heading',{name:'All selected payments completed'}).waitFor();await page.setViewportSize({width:390,height:1000});await review.screenshot({path:join(output,'reconciled-receipt-390.png')});
  const balance=await call('/api/wallet',undefined,'GET');assert.equal(balance.posted_balance,35000);assert.equal(balance.reserved_amount,0);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
  console.log('PASSED: V3 A/B/C: remembered checkout with alerts off; explicit synthetic voice auto-submit; corrections and re-add; inline desktop/mobile review; exact PIN and two journals; separate fulfillment; real shortfall, PIN funding, fresh review; unknown outcome stays processing until actual worker reconciliation. No live providers or physical microphone.');
}finally{await browser?.close();web.kill();backend.kill();}

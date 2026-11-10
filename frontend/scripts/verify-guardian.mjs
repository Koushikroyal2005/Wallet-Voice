// Synthetic server and PayPal SDK evidence only. No live payment is made.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import assert from 'node:assert/strict';
import { guardianFixture } from './guardian-fixture.mjs';
const server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5192','--strictPort'],{stdio:'ignore',windowsHide:true});
let browser;
try {
  for(let n=0;n<100;n++){try{await fetch('http://127.0.0.1:5192');break;}catch{await new Promise(r=>setTimeout(r,100));}}
  browser=await chromium.launch({headless:true});
  for(const scenario of ['wallet','paypal-pending','paypal-completed','failed','unknown','insufficient','expired','hold']) {
    const page=await browser.newPage({viewport:{width:scenario==='wallet'?1440:390,height:900}});
    let payCalls=0;const errors=[];page.on('pageerror',e=>errors.push(e.message));
    const p={id:'rail',merchant:'Indian Railways',category:'travel',description:'Ticket',amount:125050,currency:'INR',verified:scenario!=='unknown',status:'PENDING',expires_at:new Date(Date.now()+(scenario==='expired'?-60000:3600000)).toISOString()};
    let result=guardianFixture(p);
    if(scenario==='insufficient')result.wallet_policy={...result.wallet_policy,decision:'HELD_INSUFFICIENT_BALANCE',reason_codes:['MINIMUM_BALANCE']};
    if(scenario==='expired')result.wallet_policy={...result.wallet_policy,decision:'EXPIRED',reason_codes:['EXPIRED']};
    if(scenario.startsWith('paypal')){p.status=scenario==='paypal-pending'?'PROCESSING':'SUCCEEDED';result.payment.status=p.status;result.paypal={status:scenario==='paypal-pending'?'PENDING':'COMPLETED',order_id:'FIXTURE-ORDER',capture_id:'FIXTURE-CAPTURE',provider_currency:'USD',provider_amount:'14.89'};result.attempt={status:p.status};result.receipt={payment_id:p.id,merchant:p.merchant,amount:p.amount,currency:'INR',funding_source:'PAYPAL_SANDBOX',status:p.status,timestamp:new Date().toISOString(),timestamp_label:'Capture recorded',order_id:'FIXTURE-ORDER',capture_id:'FIXTURE-CAPTURE'};}
    await page.addInitScript(()=>{window.EventSource=class{close(){}};});
    await page.route('https://**/*',r=>r.abort());
    await page.route('**/api/**',async route=>{
      const path=new URL(route.request().url()).pathname;let data=[];
      if(path==='/api/auth/session')data={authenticated:true};
      else if(path==='/api/wallet')data={posted_balance:1000000,reserved_amount:0,available_balance:1000000};
      else if(path==='/api/payments')data=[p];
      else if(path.endsWith('/review'))data=result;
      else if(path==='/api/assistant/turn')data={response:'Review the railway request.',provider:'context-resolver',action_preview:{kind:'payment',payment_id:p.id,payment_source:'AI_WALLET',requires_confirmation:true}};
      else if(path.endsWith('/pay')){
        payCalls++;await new Promise(r=>setTimeout(r,200));
        p.status=scenario==='failed'?'FAILED':'SUCCEEDED';result.payment.status=p.status;result.attempt={status:p.status,failure_reason:scenario==='failed'?'DEMO_PROVIDER_FAILURE':null};
        result.receipt={payment_id:p.id,merchant:p.merchant,amount:p.amount,currency:'INR',funding_source:'AI_WALLET',status:p.status,timestamp:new Date().toISOString(),timestamp_label:'Journal posted',journal_id:scenario==='failed'?null:'FIXTURE-JOURNAL'};data=result.attempt;
      }else if(path.endsWith('/hold')){p.explicit_hold=true;p.status='HELD';result.payment={...result.payment,...p};result.wallet_policy={decision:'EXPLICIT_HOLD',reason_codes:['USER_HELD']};data=p;}
      else if(path==='/api/paypal/config')data={configured:true,environment:'sandbox'};
      else if(path.endsWith('/order'))data=result.paypal;
      await route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
    });
    await page.goto('http://127.0.0.1:5192');
    await page.getByRole('button',{name:'Type instead',exact:true}).click();
    await page.getByLabel('Ask about your wallet or payments').fill('pay the railway ticket');
    await page.getByRole('button',{name:'Send request'}).click();
    const panel=page.getByRole('region',{name:'Payment Guardian'});await panel.getByText('Indian Railways',{exact:true}).first().waitFor();
    if(['wallet','failed'].includes(scenario)){
      await panel.getByRole('button',{name:'Confirm action',exact:true}).evaluate(b=>{b.click();b.click();});
      await panel.getByRole('heading',{name:scenario==='wallet'?'Payment completed':'Payment did not complete',exact:true}).waitFor();
      assert.equal(payCalls,1,'Duplicate confirmation must submit once');
      await panel.getByText(scenario==='wallet'?'FIXTURE-JOURNAL':'DEMO_PROVIDER_FAILURE',{exact:true}).waitFor();
    }else if(scenario==='unknown'){
      assert.ok(await panel.getByRole('button',{name:'Confirm action',exact:true}).isDisabled());
      await panel.getByLabel('I recognize this business and have checked the amount.').check();
      assert.ok(await panel.getByRole('button',{name:'Confirm action',exact:true}).isEnabled());
    }else if(scenario==='hold'){
      await panel.getByRole('button',{name:'Hold payment',exact:true}).click();await panel.getByRole('heading',{name:'Payment on hold',exact:true}).waitFor();
    }else if(scenario.startsWith('paypal')){
      await panel.getByRole('heading',{name:scenario==='paypal-pending'?'Waiting for confirmation':'Payment completed',exact:true}).waitFor();
      await panel.getByText(/Internal wallet limits do not govern/).waitFor();
      assert.equal(await panel.getByRole('button',{name:'Confirm action',exact:true}).count(),0);
    }else assert.ok(await panel.getByRole('button',{name:'Confirm action',exact:true}).isDisabled());
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal page overflow');
    assert.ok(await panel.evaluate(el=>el.scrollWidth<=el.clientWidth),'No panel overflow');
    await panel.getByLabel('Payment decision timeline').waitFor();
    assert.deepEqual(errors,[]);await page.close();
  }
  console.log('PASSED: 8 Guardian browser fixture scenarios; desktop/mobile, duplicate-click guard, unknown merchant, policy holds, expiry, hold, failed and completed wallet records, pending/completed PayPal states.');
}finally{await browser?.close();server.kill();}

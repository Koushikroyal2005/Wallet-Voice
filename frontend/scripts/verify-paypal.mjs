// Mock SDK/API lifecycle verification; never contacts PayPal or a real database.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import assert from 'node:assert/strict';
import { guardianFixture } from './guardian-fixture.mjs';

const server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5190','--strictPort'],{stdio:'ignore',windowsHide:true});
let browser;
try {
  for(let n=0;n<100;n++){try{await fetch('http://127.0.0.1:5190');break;}catch{await new Promise(r=>setTimeout(r,100));}}
  browser=await chromium.launch({headless:true});
  for(const outcome of ['COMPLETED','DENIED','PENDING','LOST_RESPONSE','CANCEL','RELOAD_PENDING','RELOAD_CAPTURE']) {
    const page=await browser.newPage();
    let captureCalls=0,refreshCalls=0,createCalls=0,recordedOrder=null;
    const order={order_id:'FIXTURE-ORDER',provider_amount:'14.88',provider_currency:'USD',status:'CREATED'};
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.addInitScript((outcome)=>{
      window.EventSource=class{close(){}};
      window.paypal={createInstance:async options=>{
        if(options.clientId!=='fixture-client-id' || options.clientToken)throw new Error('Expected v6 client ID authentication');
        return {findEligibleMethods:async()=>({isEligible:()=>true}),createPayPalOneTimePaymentSession:callbacks=>({
          start:async(_options,orderPromise)=>{
            const {orderId}=await orderPromise;
            if(outcome==='CANCEL'){setTimeout(()=>callbacks.onCancel(),200);return;}
            // Two approval callbacks must not dispatch duplicate capture requests.
            setTimeout(()=>{void callbacks.onApprove({orderId});void callbacks.onApprove({orderId});},200);
          },
        })};
      }};
    },outcome);
    await page.route('https://**/*',route=>route.abort());
    await page.route('**/api/**',async route=>{
      const path=new URL(route.request().url()).pathname;
      let result={};let status=200;
      if(path==='/api/auth/session')result={authenticated:true,required:true};
      else if(path==='/api/wallet')result={posted_balance:1000000,reserved_amount:0,available_balance:1000000};
      else if(path==='/api/notifications')result={items:[{payment_id:'ticket',merchant:'Indian Railways',amount:125000,stage:'URGENT'}],preferences:{enabled:false}};
      else if(path==='/api/payments')result=[{id:'ticket',merchant:'Indian Railways',description:'Ticket',category:'travel',amount:125000,status:'PENDING',verified:true,explicit_hold:false,trace:{urgency:'URGENT'}}];
      else if(path==='/api/payments/ticket/review')result=guardianFixture({id:'ticket',merchant:'Indian Railways',description:'Ticket',category:'travel',amount:125000,status:recordedOrder?.status==='COMPLETED'?'SUCCEEDED':recordedOrder?'PROCESSING':'PENDING',verified:true}, {paypal:recordedOrder});
      else if(path==='/api/paypal/config')result={configured:true,environment:'sandbox',client_id:'fixture-client-id',checkout_currency:'USD',demo_inr_per_usd:'84'};
      else if(path==='/api/paypal/payment-requests/ticket/order')result=outcome==='RELOAD_PENDING'?{...order,status:'PENDING'}:outcome==='RELOAD_CAPTURE'?order:null;
      else if(path==='/api/paypal/orders'){createCalls++;result=order;}
      else if(path.endsWith('/capture')){
        captureCalls++;await new Promise(r=>setTimeout(r,250));
        if(outcome==='LOST_RESPONSE'){status=503;result={detail:'Fixture timeout'};}
        else {result={...order,status:outcome,capture_id:'FIXTURE-CAPTURE'};recordedOrder=result;}
      } else if(path.endsWith('/refresh')){refreshCalls++;result={...order,status:['PENDING','RELOAD_PENDING'].includes(outcome)?'DENIED':'COMPLETED',capture_id:'FIXTURE-CAPTURE'};recordedOrder=result;}
      else result=[];
      await route.fulfill({status,contentType:'application/json',body:JSON.stringify(result)});
    });
    await page.goto('http://127.0.0.1:5190');
    await page.getByRole('region',{name:'Payment reminders'}).getByRole('button',{name:'Review now',exact:true}).first().click();
    await page.getByLabel('Payment source',{exact:true}).selectOption('PAYPAL_SANDBOX');
    if(outcome.startsWith('RELOAD')) {
      if(outcome==='RELOAD_PENDING')await page.getByText('Failed or denied',{exact:true}).waitFor();
      else await page.getByRole('heading',{name:'Payment completed',exact:true}).waitFor();
      assert.equal(createCalls,0);assert.equal(captureCalls,0);assert.ok(refreshCalls>=1);assert.deepEqual(errors,[]);
      await page.close();continue;
    }
    await page.getByText('Ready for approval',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Continue with PayPal'}).click();
    await page.getByText('Waiting for buyer approval',{exact:true}).waitFor();
    if(outcome==='CANCEL'){
      await page.getByText('Ready for approval',{exact:true}).waitFor();assert.equal(captureCalls,0);assert.equal(createCalls,1);assert.deepEqual(errors,[]);await page.close();continue;
    }
    if(outcome==='PENDING' || outcome==='LOST_RESPONSE')await page.getByText('Processing',{exact:true}).waitFor();
    if(outcome==='DENIED' || outcome==='PENDING')await page.getByText('Failed or denied',{exact:true}).waitFor();
    else await page.getByRole('heading',{name:'Payment completed',exact:true}).waitFor();
    assert.equal(captureCalls,1,`${outcome}: duplicate approval must not duplicate capture`);
    assert.equal(createCalls,1);
    if(outcome==='PENDING' || outcome==='LOST_RESPONSE')assert.ok(refreshCalls>=1);
    assert.deepEqual(errors,[]);
    await page.close();
  }
  console.log('PASSED: 7 fixture journeys: completed, denied, pending-to-denied, lost response, buyer cancellation, reload pending, reload capture; SDK v6 initialization and duplicate approval');
} finally {if(browser)await browser.close();server.kill();}

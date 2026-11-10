// Actual FastAPI + isolated SQLite settlement. Only microphone transcription is synthetic.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { mkdtemp,mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve,join } from 'node:path';
import assert from 'node:assert/strict';
const folder=await mkdtemp(join(tmpdir(),'wallet-v1-'));
const env={...process.env,DATABASE_URL:`sqlite:///${join(folder,'v1-browser-wallet.db').replaceAll('\\','/')}`,REQUIRE_WALLET_LOGIN:'true',WALLET_SESSION_SECRET:'isolated-browser-test-secret-32-characters',DEMO_WALLET_PIN:'123456',NVIDIA_ENABLED:'false',PAYPAL_ENABLED:'false',TEST_DATABASE_URL:''};
const backend=spawn('python',['-m','scripts.serve_v1_verification'],{cwd:resolve('../backend'),env,windowsHide:true,stdio:['ignore','pipe','pipe']});
let backendOutput='';backend.stderr.on('data',data=>backendOutput+=data.toString());
const web=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5194','--strictPort'],{windowsHide:true,stdio:'ignore'});
const output=resolve('../artifacts/v1-review');await mkdir(output,{recursive:true});
let browser;
try {
  for(let n=0;n<150;n++){
    try{const r=await fetch('http://127.0.0.1:8194/health');if(r.ok){await fetch('http://127.0.0.1:5194');break;}}catch{}
    if(backend.exitCode!==null)throw new Error(`Verification API exited: ${backendOutput}`);
    await new Promise(r=>setTimeout(r,100));
  }
  browser=await chromium.launch({headless:true});
  for(const width of [1440,390]) {
    const page=await browser.newPage({viewport:{width,height:1000}});const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(()=>{
      window.EventSource=class{close(){}};
      window.__tracksStopped=0;
      Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async()=>({getTracks:()=>[{stop(){window.__tracksStopped++;}}]})});
      window.MediaRecorder=class{static isTypeSupported(){return true;}state='inactive';mimeType='audio/webm';start(){this.state='recording';}stop(){this.state='inactive';this.ondataavailable?.({data:new Blob(['synthetic speech'],{type:'audio/webm'})});queueMicrotask(()=>this.onstop?.());}};
      window.AudioContext=class{resume(){return Promise.resolve();}close(){return Promise.resolve();}createAnalyser(){return{fftSize:2048,getFloatTimeDomainData:a=>a.fill(0)}}createMediaStreamSource(){return{connect(){}}}};
    });
    await page.route('https://**/*',r=>r.abort());
    await page.route('**/api/**',route=>{
      const u=new URL(route.request().url());
      if(u.pathname==='/api/voice/transcribe')return route.fulfill({json:{transcript:'Pay the train and movie tickets, not the food order.',provider:'synthetic-browser-fixture'}});
      return route.continue({url:`http://127.0.0.1:8194${u.pathname}${u.search}`});
    });
    await page.goto('http://127.0.0.1:5194');
    await page.locator('input[type="password"]').fill('123456');
    await page.getByRole('button',{name:'Unlock wallet',exact:true}).click();
    await page.getByRole('button',{name:'Talk to your wallet',exact:true}).waitFor();
    if(width===1440){
      await page.getByRole('region',{name:'Payment reminders'}).getByRole('button',{name:'Review now',exact:true}).first().click();
      await page.getByRole('region',{name:'Payment Guardian'}).waitFor();await page.keyboard.press('Escape');
      await page.getByRole('button',{name:'Talk to your wallet',exact:true}).click();
      await page.getByRole('button',{name:'Stop recording',exact:true}).click();
      const review=page.getByRole('region',{name:'Exact payment review'});
      await review.getByText('Indian Railways',{exact:true}).waitFor();
      await review.getByText('CinemaPass',{exact:true}).waitFor();
      assert.equal(await review.getByText('Demo Kitchen',{exact:true}).count(),0);
      await review.screenshot({path:join(output,'exact-review-1440.png')});
      await page.getByLabel('Ask about your wallet or payments').fill('Remove the movie ticket.');
      await page.getByRole('button',{name:'Send request'}).click();
      await review.getByText('CinemaPass',{exact:true}).waitFor({state:'hidden'});
      // Rebuild exact two-item selection, then approve once.
      await page.getByLabel('Ask about your wallet or payments').fill('Pay train and movie tickets, not food.');
      await page.getByRole('button',{name:'Send request'}).click();
      await review.getByText('CinemaPass',{exact:true}).waitFor();
      await review.getByLabel('Six-digit wallet PIN').fill('123456');
      await review.getByRole('button',{name:'Approve exact payments',exact:true}).evaluate(b=>{b.click();b.click();});
      await review.getByRole('heading',{name:'All selected payments completed',exact:true}).waitFor();
      assert.equal(await review.getByText('Payment receipt',{exact:true}).count(),2);
      await review.screenshot({path:join(output,'receipts-1440.png')});
      assert.ok(await page.evaluate(()=>window.__tracksStopped>0));
      await page.keyboard.press('Escape');
      const wallet=await page.evaluate(async()=>{const r=await fetch('/api/wallet');return r.json();});
      assert.equal(wallet.posted_balance,815000);assert.equal(wallet.reserved_amount,0);
      const payments=await page.evaluate(async()=>{const r=await fetch('/api/payments');return r.json();});
      assert.equal(payments.find(p=>p.merchant==='Demo Kitchen').status,'PENDING');
    } else {
      await page.getByRole('region',{name:'Payment reminders'}).getByRole('button',{name:'Review now',exact:true}).first().click();
      await page.getByRole('region',{name:'Payment Guardian'}).getByRole('button',{name:'Confirm action',exact:true}).click();
      const mobileReview=page.getByRole('region',{name:'Exact payment review'});
      await mobileReview.getByLabel('Six-digit wallet PIN').waitFor();
      assert.ok(await mobileReview.evaluate(el=>el.scrollWidth<=el.clientWidth));
      await mobileReview.screenshot({path:join(output,'exact-review-390.png')});
      await mobileReview.getByRole('button',{name:'Cancel review',exact:true}).click();
    }
    await page.screenshot({path:join(output,`home-${width}.png`),fullPage:true});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.deepEqual(errors,[]);await page.close();
  }
  console.log('PASSED: actual FastAPI/SQLite login, reminder review, default voice auto-submit, exclusion, correction, exact PIN batch, duplicate-click guard, two journal receipts, untouched food request, balance reconciliation, desktop/mobile. Synthetic STT only; no live NVIDIA or PayPal.');
} finally {await browser?.close();web.kill();backend.kill();}

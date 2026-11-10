// Synthetic microphone/SDK fixtures: no physical microphone or live AI calls.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import assert from 'node:assert/strict';
import { guardianFixture } from './guardian-fixture.mjs';

const server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5191','--strictPort'],{stdio:'ignore',windowsHide:true});
let browser;
try {
  for(let n=0;n<100;n++){try{await fetch('http://127.0.0.1:5191');break;}catch{await new Promise(r=>setTimeout(r,100));}}
  browser=await chromium.launch({headless:true});
  for(const scenario of ['review','close-upload','switch-upload','close-listening','auto-send-opt-in','retry','interrupt-playback','short-pause','long-pause']) {
    const page=await browser.newPage();const requests=[];const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.addInitScript((scenario)=>{
      localStorage.setItem('wallet-review-transcript',scenario==='review'?'on':'off');
      localStorage.setItem('wallet-patient-listening',String(scenario==='long-pause'));
      window.__voice={stops:0,spoken:0};
      window.EventSource=class{close(){}};
      window.speechSynthesis.speak=()=>{window.__voice.spoken++;};
      Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async()=>({getTracks:()=>[{stop:()=>{window.__voice.stops++;}}]})});
      window.MediaRecorder=class {
        static isTypeSupported(){return true;}
        state='inactive';mimeType='audio/webm';onstop=null;ondataavailable=null;
        start(){this.state='recording';}
        stop(){this.state='inactive';this.ondataavailable?.({data:new Blob(['fixture'],{type:'audio/webm'})});queueMicrotask(()=>this.onstop?.());}
      };
      window.AudioContext=class {
        resume(){return Promise.resolve();}close(){return Promise.resolve();}
        createAnalyser(){const began=performance.now();return {fftSize:2048,getFloatTimeDomainData:array=>{
          const elapsed=performance.now()-began;
          const speaking=scenario==='short-pause' && (elapsed<900 || elapsed>=1800 && elapsed<2700) || scenario==='long-pause' && elapsed<900;
          array.fill(speaking?0.08:0);
        }};}
        createMediaStreamSource(){return {connect(){}};}
      };
    },scenario);
    await page.route('https://**/*',route=>route.abort());
    await page.route('**/api/**',async route=>{
      const path=new URL(route.request().url()).pathname;
      const body=route.request().postData();
      const json=body && route.request().headers()['content-type']?.includes('application/json')?JSON.parse(body):{};
      requests.push({path,body:json});let result={};let status=200;
      if(path==='/api/auth/session')result={required:true,authenticated:true};
      else if(path==='/api/wallet')result={posted_balance:1000000,reserved_amount:0,available_balance:1000000};
      else if(path==='/api/payments')result=[];
      else if(path==='/api/payments/rail/review')result=guardianFixture({id:'rail',merchant:'Indian Railways',amount:125050,verified:false,status:'PENDING'});
      else if(path==='/api/assistant/status')result={browser_tts_fallback:true};
      else if(path.includes('/conversations/'))result={messages:[]};
      else if(path==='/api/voice/transcribe'){
        if(scenario.includes('upload'))await new Promise(r=>setTimeout(r,400));
        result={transcript:'pay the train ticket',provider:'nvidia-riva-whisper-large-v3'};
      } else if(path==='/api/assistant/turn') {
        await new Promise(r=>setTimeout(r,100));
        if(scenario==='retry' && requests.filter(r=>r.path===path).length===1){status=503;result={detail:'Fixture service unavailable'};}
        else result={conversation_id:json.conversation_id,response:'Please review the selected train ticket.',provider:scenario==='auto-send-opt-in'?'demo-parser':'nvidia-nemotron',action_preview:{kind:'payment',merchant:'Indian Railways',payment_id:'rail',amount:125050,verified:false,payment_source:'AI_WALLET',requires_confirmation:true}};
      } else if(path==='/api/voice/synthesize'){await new Promise(r=>setTimeout(r,400));status=503;}
      else result=[];
      await route.fulfill({status,contentType:'application/json',body:JSON.stringify(result)}).catch(()=>undefined);
    });
    await page.goto('http://127.0.0.1:5191');
    if(['retry','interrupt-playback','auto-send-opt-in'].includes(scenario))await page.getByRole('button',{name:'Type instead',exact:true}).click();
    else await page.getByRole('button',{name:'Talk to your wallet',exact:true}).click();
    if(scenario==='auto-send-opt-in'){
      await page.getByText('Assistant details and voice preferences',{exact:true}).click();
      await page.getByLabel('Review transcript before sending').uncheck();
      await page.getByRole('button',{name:'Voice',exact:true}).click();
    }
    if(!['retry','interrupt-playback'].includes(scenario)){
      await page.getByRole('button',{name:'Stop recording',exact:true}).waitFor();
      if(scenario==='close-listening')await page.keyboard.press('Escape');
      else if(scenario.endsWith('-pause')) {
        await page.waitForTimeout(scenario==='short-pause'?1500:2300);
        assert.ok(await page.getByRole('button',{name:'Stop recording',exact:true}).isVisible(),'A within-turn pause must not end capture');
        await page.getByRole('button',{name:'Confirm action',exact:true}).waitFor();
      }
      else {
        await page.getByRole('button',{name:'Stop recording',exact:true}).click();
        if(scenario==='close-upload')await page.keyboard.press('Escape');
        else if(scenario==='switch-upload')await page.getByRole('button',{name:'Chat',exact:true}).click();
        else if(scenario==='review'){
          await page.getByText('Transcript ready',{exact:true}).first().waitFor();
          assert.equal(requests.filter(r=>r.path==='/api/assistant/turn').length,0);
          assert.equal(await page.getByLabel('Ask about your wallet or payments').inputValue(),'pay the train ticket');
          await page.getByLabel('Ask about your wallet or payments').fill('pay my train ticket');
          await page.getByRole('button',{name:'Send request'}).evaluate(button=>{button.click();button.click();});
        }
      }
    } else {
      await page.getByLabel('Ask about your wallet or payments').fill('pay my train ticket');
      await page.getByRole('button',{name:'Send request'}).click();
      if(scenario==='retry'){
        await page.getByRole('button',{name:'Retry this request'}).click();
        const turns=requests.filter(r=>r.path==='/api/assistant/turn');
        assert.equal(turns[0].body.request_id,turns[1].body.request_id);
        assert.equal(turns[0].body.conversation_id,turns[1].body.conversation_id);
      }
    }
    if(['review','retry','interrupt-playback','auto-send-opt-in','short-pause','long-pause'].includes(scenario)){
      await page.getByRole('button',{name:'Confirm action',exact:true}).waitFor();
      await page.getByRole('region',{name:'Payment Guardian'}).getByText(/1,250\.50/).first().waitFor();
      assert.ok(await page.getByRole('button',{name:'Confirm action',exact:true}).isDisabled(),'Unknown business requires acknowledgement');
      await page.getByLabel('I recognize this business and have checked the amount.').check();
      assert.ok(await page.getByRole('button',{name:'Confirm action',exact:true}).isEnabled());
      assert.equal(requests.filter(r=>r.path==='/api/assistant/turn').length,scenario==='retry'?2:1);
      assert.equal(requests.filter(r=>r.path==='/api/voice/synthesize').length,0,'No automatic playback by default');
      if(!await page.getByLabel('Assistant provider').isVisible()) await page.getByText('Assistant details and voice preferences',{exact:true}).click();
      if(scenario==='auto-send-opt-in')await page.getByText(/Reasoning: deterministic demo parser/).waitFor();
      else await page.getByText(/Reasoning: NVIDIA Nemotron/).waitFor();
      if(scenario==='interrupt-playback'){
        await page.getByRole('button',{name:'Read aloud',exact:true}).click();
        await page.getByRole('button',{name:'Voice',exact:true}).click();
      }
      await page.keyboard.press('Escape');
    }
    await page.waitForTimeout(600);
    assert.equal(await page.evaluate(()=>window.__voice.spoken),0,'Interrupted synthesis must not start browser speech');
    if(!['retry'].includes(scenario))assert.ok(await page.evaluate(()=>window.__voice.stops)>0,'Microphone tracks must stop');
    assert.equal(requests.filter(r=>r.path.endsWith('/pay') || r.path.endsWith('/capture')).length,0,'Assistant tests never approve payment');
    assert.deepEqual(errors,[]);
    await page.close();
  }
  console.log('PASSED: 9 voice fixture journeys: transcript review, close/switch during transcription, close while listening, opt-in auto-send, retry deduplication, interrupted playback, short pause continuity and longer patient-listening silence detection; synthetic audio only, no payments executed');
} finally {if(browser)await browser.close();server.kill();}

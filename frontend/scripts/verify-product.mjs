// Browser checks use explicit API fixtures, never a development database or provider.
import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { guardianFixture } from './guardian-fixture.mjs';

const output = resolve('..', 'artifacts', 'product-review');
await mkdir(output, { recursive: true });
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5189', '--strictPort'], { stdio: 'ignore', windowsHide: true });
const base = process.env.UI_TEST_URL || 'http://127.0.0.1:5189';
for (let n=0;n<80;n++) { try { await fetch(base); break; } catch { await new Promise(resolve => setTimeout(resolve,100)); } }
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await page.addInitScript(() => {
  window.EventSource = class { close() {} };
  window.speechSynthesis.speak = () => {};
  navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('Fixture: permission denied', 'NotAllowedError'); };
});
let posted = 1_000_000;
let authenticated = false;
const requests = [];
const people = [];
const drafts = [];
const activities = [{ id: 'seed', kind: 'TOPUP', amount: posted, reference: 'Opening balance', created_at: new Date().toISOString() }];
const payments = [
  { id: 'rail', merchant: 'Indian Railways', category: 'travel', description: 'Hyderabad to Bengaluru · Railway ticket', amount: 125000, status: 'PENDING', verified: true, expires_at: new Date(Date.now() + 240000).toISOString(), trace: { urgency: 'URGENT' } },
  { id: 'movie', merchant: 'CinemaPass', category: 'entertainment', description: 'Friday night, sorted.', amount: 60000, status: 'PENDING', verified: true, expires_at: new Date(Date.now() + 7200000).toISOString(), trace: { urgency: 'DUE_SOON' } },
  { id: 'shop', merchant: 'ElectroHub', category: 'shopping', description: 'Something for your desk.', amount: 450000, status: 'PENDING', verified: false, trace: { urgency: 'FLEXIBLE' } },
];
await page.route('**/api/**', async route => {
  const request = route.request();
  const path = new URL(request.url()).pathname;
  const body = request.postData() ? JSON.parse(request.postData()) : {};
  requests.push({ path, method: request.method(), body });
  let result = {};
  if (path === '/api/auth/session') result = { required: true, authenticated };
  else if (path === '/api/auth/login') { authenticated = true;result = { authenticated }; }
  else if (path === '/api/wallet') result = { posted_balance: posted, reserved_amount: 0, available_balance: posted };
  else if (path === '/api/payments') result = payments;
  else if (path.endsWith('/review')) result = guardianFixture(payments.find(p => path.includes(`/${p.id}/`)));
  else if (path === '/api/wallet/transactions') result = activities;
  else if (path === '/api/wallet/reservations') result = [];
  else if (path === '/api/mandates') result = [];
  else if (path === '/api/merchants') result = [{id:'fixture-rail',name:'Indian Railways'}];
  else if (path === '/api/autopay/settings') result = { enabled: false, time_sensitive_only: true, per_transaction_limit: 500000, daily_limit: 1000000, minimum_balance: 10000 };
  else if (path === '/api/recipients') { if (request.method() === 'POST') { result = { ...body, id: 'asha' }; people.push(result); } else result = people; }
  else if (path === '/api/payment-intents') { if (request.method() === 'POST') { result = { ...body, id: 'draft', status: 'DRAFT', version: 1 }; drafts.push(result); } else result = drafts; }
  else if (path === '/api/security/challenges') result = { id: 'challenge' };
  else if (path.endsWith('/verify')) result = { approval_token: 'fixture-approved-token-only' };
  else if (path === '/api/bank/topups') { posted += body.amount; activities.unshift({ id: 'added', kind: 'TOPUP', amount: body.amount, reference: 'New top-up', created_at: new Date().toISOString() }); result = { status: 'SUCCEEDED' }; }
  else if (path === '/api/assistant/turn') result = { conversation_id: 'conversation', response: 'Indian Railways is urgent because its deadline is less than 15 minutes away.', data: [payments[0]], action_preview: { kind: 'payment', payment_id: 'rail', merchant: 'Indian Railways', amount: 125000, payment_source: 'AI_WALLET', verified: true, requires_confirmation: true } };
  else if (path.includes('/conversations/')) result = { messages: [] };
  else if (path === '/api/voice/synthesize') return route.fulfill({ status: 503, contentType: 'application/json', body: '{}' });
  else if (path === '/api/demo/checkout') result = { status: 'AWAITING_USER_APPROVAL', payment_request: { id: 'sample' } };
  else if (path === '/api/demo/checkout/sample') result = { status: 'HELD' };
  else if (path === '/api/payments/batch/evaluate') result = { eligible_count: 2, required_total: 185000, items: payments.slice(0, 2).map(p => ({ ...p, decision: 'ELIGIBLE', reason_codes: [] })) };
  else if (path === '/api/payments/batch/confirm') result = { results: [{ id: 'a', status: 'SUCCEEDED', provider_reference: 'demo' }, { id: 'b', status: 'FAILED', failure_reason: 'Simulated failure' }] };
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(result) });
});
try {
  await page.goto(base, { waitUntil: 'networkidle' });
  await page.getByRole('heading',{name:'Welcome to your wallet.'}).waitFor();
  await page.screenshot({path:resolve(output,'unlock-desktop.png'),fullPage:true});
  await page.getByLabel('Wallet PIN',{exact:true}).fill('123456');
  await page.getByRole('button',{name:'Unlock wallet'}).click();
  await page.getByRole('heading', { name: 'Talk to your wallet.' }).waitFor();
  async function screen(name) {
    if(!name.startsWith('guardian-'))await page.evaluate(()=>window.scrollTo(0,0));
    await page.screenshot({ path: resolve(output, `${name}.png`), fullPage: false, animations:'disabled' });
    if(!name.startsWith('guardian-'))await page.screenshot({ path: resolve(output, `${name}-full.png`), fullPage: true, animations:'disabled' });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name}: horizontal overflow`);
  }
  for (const [width,height] of [[1440,1000],[1024,900],[768,1024],[390,844]]) {
    await page.setViewportSize({width,height});
    for (const name of ['Home','Payments','Wallet','Auto-pay & security']) {
      await page.getByRole('navigation').getByRole('button',{name,exact:true}).click();
      await page.waitForTimeout(100);
      await screen(`${name.toLowerCase()}-${width}`);
    }
    await page.getByRole('navigation').getByRole('button',{name:'Home',exact:true}).click();
    await page.getByRole('button',{name:'Review payment',exact:true}).click();
    await page.getByRole('region',{name:'Payment Guardian'}).getByText('Indian Railways',{exact:true}).waitFor();
    await page.getByRole('dialog').evaluate(el=>Promise.all(el.getAnimations().map(a=>a.finished)));
    await screen(`guardian-${width}`);
    assert.ok(await page.getByRole('dialog').evaluate(el=>el.scrollWidth<=el.clientWidth),'Guardian drawer overflow');
    await page.getByRole('dialog').getByRole('button',{name:'Confirm action',exact:true}).scrollIntoViewIfNeeded();
    await screen(`guardian-actions-${width}`);
    await page.keyboard.press('Escape');
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('navigation').getByRole('button',{name:'Wallet',exact:true}).click();
  await page.getByRole('button',{name:'Add demo money',exact:true}).click();
  await page.getByLabel('Amount in rupees').fill('200');
  await page.getByRole('button',{name:/Review ₹200/}).click();
  await page.getByLabel('Your six-digit wallet PIN').fill('123456');
  await page.getByRole('button',{name:'Approve',exact:true}).click();
  await page.getByText('New top-up',{exact:true}).waitFor();
  assert.equal(posted,1_020_000);
  await page.getByRole('navigation').getByRole('button',{name:'Payments',exact:true}).click();
  await page.getByRole('button',{name:'New draft'}).click();
  await page.getByRole('button',{name:'Add a recipient'}).click();
  await page.getByLabel('Name',{exact:true}).fill('Asha');
  await page.getByLabel('Phone number with country code').fill('+919876543210');
  await page.getByRole('button',{name:'Save recipient'}).click();
  await page.getByRole('button',{name:'Save recipient'}).waitFor({state:'detached'});
  await page.getByLabel('Amount in rupees').fill('500');
  await page.getByLabel('What’s it for?').fill('Dinner');
  await page.getByRole('button',{name:'Save draft',exact:true}).click();
  await page.getByText('Asha',{exact:true}).waitFor();
  assert.equal(drafts[0].recipient_id,'asha');
  assert.equal(drafts[0].amount,50000);
  await page.getByRole('navigation').getByRole('button',{name:'Auto-pay & security',exact:true}).click();
  await page.getByRole('button',{name:'Security',exact:true}).click();
  await page.getByRole('button',{name:'Change PIN',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Choose a business',exact:true}).count(),0);
  await page.getByRole('button',{name:'Auto-pay',exact:true}).click();
  await page.getByRole('button',{name:'Choose a business'}).click();
  await page.getByRole('combobox').selectOption('fixture-rail');
  await page.getByRole('button',{name:'Review checkout approval'}).click();
  await page.getByRole('dialog').getByText('Indian Railways',{exact:true}).waitFor();
  await page.getByRole('dialog').getByText('Maximum in one day',{exact:true}).waitFor();
  await screen('permission-approval');
  await page.keyboard.press('Escape');
  await page.keyboard.press('Escape');
  await page.getByRole('navigation').getByRole('button',{name:'Home',exact:true}).click();
  await page.getByRole('button', {name: 'Type instead',exact:true}).click();
  await page.getByLabel('Ask about your wallet or payments').fill('Pay the railway ticket');
  await page.getByRole('button',{name:'Send request'}).click();
  await page.getByRole('button',{name:'Confirm action'}).waitFor();
  await page.getByLabel('Ask about your wallet or payments').fill('Use PayPal instead');
  assert.equal(await page.getByRole('button',{name:'Confirm action'}).count(),0,'Editing must discard old approval preview');
  assert.equal(requests.filter(r=>r.path.endsWith('/pay')).length,0,'Assistant preview must not pay');
  await screen('assistant-chat');
  const turnCount = requests.filter(r => r.path === '/api/assistant/turn').length;
  await page.getByRole('button',{name:'Voice',exact:true}).click();
  await page.getByText('Microphone permission was not granted. Type your request instead.').waitFor();
  await page.getByRole('button',{name:'Chat',exact:true}).click();
  assert.equal(await page.getByLabel('Ask about your wallet or payments').inputValue(),'Use PayPal instead','Mode changes preserve the unfinished correction');
  assert.equal(await page.getByRole('button',{name:'Confirm action'}).count(),0,'Mode changes must not restore a stale preview');
  assert.equal(requests.filter(r => r.path === '/api/assistant/turn').length,turnCount,'Mode changes do not resubmit a turn');
  await page.keyboard.press('Escape');
  const orb = page.getByRole('button', {name: 'Open wallet assistant',exact:true});
  await orb.click();
  await page.getByRole('heading',{name:'Your wallet assistant',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  assert.ok(await orb.evaluate(el=>el===document.activeElement),'Closing assistant restores launcher focus');
  await page.getByRole('button',{name:'Talk',exact:true}).click();
  await page.getByRole('heading',{name:'Let’s talk',exact:true}).waitFor();
  await page.getByText('Microphone permission was not granted. Type your request instead.').waitFor();
  await screen('assistant-voice');
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Type',exact:true}).focus();
  await page.keyboard.press('Enter');
  await page.getByRole('heading',{name:'Your wallet assistant',exact:true}).waitFor();
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({status:'passed',screenshots:output,viewports:4,screens:5,journeys:['funding/activity refresh','recipient draft','permission review','stale assistant preview cleared','single tap assistant','explicit Talk/Type','keyboard launcher']},null,2));
} finally { await browser.close(); server.kill(); }

import assert from 'node:assert/strict';

export async function orbCollisions(page) {
  return page.evaluate(() => {
    const orb = document.querySelector('.assistant-launcher')?.getBoundingClientRect();
    if (!orb || !orb.width) return ['Launcher missing'];
    if(orb.left<0||orb.top<0||orb.right>innerWidth||orb.bottom>innerHeight)return ['Launcher outside viewport'];
    if(!document.elementFromPoint(orb.left+orb.width/2,orb.top+orb.height/2)?.closest('.assistant-launcher'))return ['Launcher obscured'];
    const modal = [...document.querySelectorAll('dialog[open]')].find(el=>el.matches(':modal'));
    const selector = 'button,input,select,textarea,a,summary,strong,b,time,p,small,dt,dd,.payment-amount,.batch-totals,.count,.badge,dialog[open]';
    if(modal) {
      const r=modal.getBoundingClientRect();
      if(r.left<orb.right&&r.right>orb.left&&r.top<orb.bottom&&r.bottom>orb.top)return ['Modal approval surface'];
    }
    return [...(modal || document.body).querySelectorAll(selector)].filter(el=>!el.closest('.guardian-assistant-layer')).flatMap(el=>{
      const r=el.getBoundingClientRect();
      if(!r.width||!r.height||r.bottom<=0||r.top>=innerHeight||getComputedStyle(el).visibility==='hidden')return [];
      const x=Math.max(r.left,orb.left),y=Math.max(r.top,orb.top);
      if(x>=Math.min(r.right,orb.right)||y>=Math.min(r.bottom,orb.bottom))return [];
      const hit=document.elementFromPoint((x+Math.min(r.right,orb.right))/2,(y+Math.min(r.bottom,orb.bottom))/2);
      return hit && (el.contains(hit)||hit.closest('.assistant-launcher')) ? [el.textContent?.trim().slice(0,70)||el.getAttribute('aria-label')||el.tagName] : [];
    });
  });
}
export async function assertOrbClear(page, name) {
  await page.waitForTimeout(100);
  assert.deepEqual(await orbCollisions(page),[], `${name}: orb overlaps protected content`);
}

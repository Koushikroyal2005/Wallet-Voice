// Local visual inspection aids only; no screenshots or gallery HTML are committed.
import { chromium } from 'playwright';
import { readdir,readFile,mkdir } from 'node:fs/promises';
import { resolve,join } from 'node:path';
const target=resolve('../artifacts/final-completion/visual');await mkdir(target,{recursive:true});
const browser=await chromium.launch({headless:true});
try {
  const page=await browser.newPage({viewport:{width:1140,height:900}});
  for (const folder of ['consumer-product','premium-assistant','prompt-completion']) {
    const root=resolve('../artifacts',folder);
    const files=(await readdir(root)).filter(name=>name.endsWith('.png')).sort();
    for(let offset=0;offset<files.length;offset+=9) {
      const cards=await Promise.all(files.slice(offset,offset+9).map(async name=>`<figure><figcaption>${name.replaceAll('&','&amp;').replaceAll('<','&lt;')}</figcaption><img src="data:image/png;base64,${(await readFile(join(root,name))).toString('base64')}"></figure>`));
      await page.setContent(`<style>body{margin:0;padding:12px;background:#e5e8f1;font:12px system-ui}main{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}figure{margin:0;background:white}figcaption{padding:8px;overflow-wrap:anywhere}img{width:100%;height:780px;object-fit:contain;object-position:top;display:block}</style><main>${cards.join('')}</main>`);
      await page.evaluate(()=>Promise.all([...document.images].map(image=>image.decode())));
      await page.screenshot({path:join(target,`${folder}-${Math.floor(offset/9)+1}.png`),fullPage:true});
    }
  }
  console.log(target);
} finally {await browser.close();}

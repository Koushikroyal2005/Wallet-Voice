import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

const output = resolve('..', 'artifacts', 'ui-review');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
const issues = [];
page.on('console', message => { if (message.type() === 'error') issues.push(`console: ${message.text()}`); });
page.on('pageerror', error => issues.push(`page: ${error.message}`));
await page.goto('http://127.0.0.1:8080', { waitUntil: 'domcontentloaded' });
await page.getByRole('heading', { name: 'Your wallet' }).waitFor();

async function capture(name, width, height, navLabel) {
  await page.setViewportSize({ width, height });
  if (navLabel) await page.getByRole('button', { name: navLabel, exact: true }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(250);
  const overflow = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
  if (overflow.width > overflow.client) issues.push(`${name}: horizontal overflow ${overflow.width - overflow.client}px`);
  await page.screenshot({ path: resolve(output, `${name}.png`), fullPage: true });
}

const group = process.argv[2] || 'desktop';
if (group === 'desktop') {
  await capture('overview-1440x1000', 1440, 1000, 'Overview');
  await capture('payments-1440x1000', 1440, 1000, 'Payment Inbox');
  await capture('autopay-1440x1000', 1440, 1000, 'AutoPay controls');
  await capture('overview-1280x900', 1280, 900, 'Overview');
} else {
  await capture('payments-768x1024', 768, 1024, 'Payment Inbox');
  await capture('overview-390x844', 390, 844, 'Overview');
  await capture('payments-390x844', 390, 844, 'Payment Inbox');
  await capture('autopay-390x844', 390, 844, 'AutoPay controls');
}
console.log(JSON.stringify({ output, issues }, null, 2));
await browser.close();

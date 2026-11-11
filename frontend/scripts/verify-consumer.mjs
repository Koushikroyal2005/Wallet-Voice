// Disposable actual FastAPI/SQLite journey. Provider calls disabled. No normal Docker.
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";
import assert from "node:assert/strict";
import { navigate } from "./navigation.mjs";
const folder = await mkdtemp(join(tmpdir(), "wallet-consumer-"));
const env = {
  ...process.env,
  DATABASE_URL: `sqlite:///${join(folder, "v3-browser-consumer.db").replaceAll("\\", "/")}`,
  REQUIRE_WALLET_LOGIN: "true",
  WALLET_SESSION_SECRET: "isolated-consumer-browser-secret-32-characters",
  DEMO_WALLET_PIN: "123456",
  NVIDIA_ENABLED: "false",
  PAYPAL_ENABLED: "false",
  TEST_DATABASE_URL: "",
  V3_RAIL_KEY: "consumer-fixture-rail-only",
  V3_FOOD_KEY: "consumer-fixture-food-only",
  VERIFICATION_PORT: "8197",
};
const backend = spawn("python", ["-m", "scripts.serve_v3_verification"], {
  cwd: resolve("../backend"),
  env,
  windowsHide: true,
  stdio: "ignore",
});
const web = spawn(
  process.execPath,
  [
    "node_modules/vite/bin/vite.js",
    "--host",
    "127.0.0.1",
    "--port",
    "5197",
    "--strictPort",
  ],
  { windowsHide: true, stdio: "ignore" },
);
const output = resolve("../artifacts/consumer-product");
await mkdir(output, { recursive: true });
let browser;
try {
  for (let n = 0; n < 250; n++) {
    try {
      if ((await fetch("http://127.0.0.1:8197/health")).ok) {
        await fetch("http://127.0.0.1:5197");
        break;
      }
    } catch {}
    if (backend.exitCode !== null) throw Error("Isolated API exited");
    await new Promise((r) => setTimeout(r, 100));
  }
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    acceptDownloads: true,
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => {
    window.EventSource = class {
      close() {}
    };
  });
  await page.route("**/api/**", (route) => {
    const u = new URL(route.request().url());
    return route.continue({
      url: "http://127.0.0.1:8197" + u.pathname + u.search,
    });
  });
  async function call(path, body, method = "POST") {
    return page.evaluate(
      async ({ path, body, method }) => {
        const r = await fetch(path, {
          method,
          headers: { "Content-Type": "application/json" },
          ...(body ? { body: JSON.stringify(body) } : {}),
        });
        if (!r.ok) throw Error(`API ${r.status}: ${await r.text()}`);
        return r.json();
      },
      { path, body, method },
    );
  }
  async function shot(name) {
    if (name.startsWith("activity-") || name === "dark-activity")
      await page.getByRole("heading", { name: "Your Activity", exact: true }).locator("..").locator(".record-row").first().waitFor();
    if (/^inbox-(360|390|430)$/.test(name)) assert.equal(await page.evaluate(()=>{
      const orb=document.querySelector('.assistant-launcher')?.getBoundingClientRect();
      return !!orb&&[...document.querySelectorAll('button.row-action')].some(button=>{const r=button.getBoundingClientRect();return r.width>0&&r.left<orb.right&&r.right>orb.left&&r.top<orb.bottom&&r.bottom>orb.top;});
    }),false,'Assistant launcher must not cover mobile review controls');
    await page.screenshot({
      path: join(output, name + ".png"),
      animations: "disabled",
    });
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      name + " overflow",
    );
    const d = page.getByRole("dialog");
    if (await d.count())
      assert.ok(
        await d.last().evaluate((el) => el.scrollWidth <= el.clientWidth),
        name + " dialog overflow",
      );
  }
  await page.goto("http://127.0.0.1:5197",{waitUntil:'domcontentloaded',timeout:60000});
  await page.getByLabel("Wallet PIN", { exact: true }).fill("123456");
  await page
    .getByRole("button", { name: "Unlock wallet", exact: true })
    .click();
  await page.getByText("Your wallet.", { exact: true }).waitFor();
  await call("/api/merchant/payment-requests", { type: "railway" });
  await call("/api/merchant/payment-requests", { type: "movie" });
  await page.reload();
  for (const [width, height] of [
    [360, 800],
    [390, 844],
    [430, 932],
    [768, 1024],
    [1024, 900],
    [1440, 900],
  ]) {
    await page.setViewportSize({ width, height });
    for (const name of ["Home", "Pay", "Inbox", "Activity"]) {
      await navigate(page, name);
      await page.waitForTimeout(100);
      await shot(`${name.toLowerCase()}-${width}`);
    }
    assert.equal(
      await page
        .getByRole("navigation", { name: "Main navigation" })
        .getByRole("button")
        .count(),
      4,
    );
    await page.getByRole("button", { name: /^Notifications/ }).click();
    assert.equal(await page.getByRole("dialog").evaluate(el=>el.matches(":modal")), width <= 768, "Desktop notifications are nonmodal; mobile is a sheet");
    if (width > 768) {
      await page.getByRole("button", { name: /^Notifications/ }).click();
      await page.getByRole("dialog").waitFor({state:"detached"});
      await page.getByRole("button", { name: /^Notifications/ }).click();
    }
    for (const section of ['All','Needs Review','AI Updates']) {
      await page.getByRole('dialog').getByRole('button',{name:section,exact:true}).click();
      await shot(`notifications-${section.toLowerCase().replaceAll(' ','-')}-${width}`);
    }
    await shot(`notifications-${width}`);
    await page.keyboard.press("Escape");
    await navigate(page, "Accounts & Cards");
    await page.getByText("Banks & cards", { exact: true }).waitFor();
    await shot(`accounts-${width}`);
    await page
      .getByRole("button", { name: "Open account and Settings", exact: true })
      .click();
    await shot(`settings-${width}`);
    for (const section of ['Security','AutoPay & Permissions','Notifications','AI & Voice','Appearance','Privacy & Data']) {
      await page.getByRole('navigation',{name:'Settings sections'}).getByRole('button',{name:section,exact:true}).click();
      await shot(`settings-${section.toLowerCase().replaceAll(' ','-')}-${width}`);
      if (section==='Security') {
        await page.getByRole('button',{name:'Change PIN',exact:true}).click();
        await shot(`pin-current-${width}`);
        await page.getByLabel('Current PIN',{exact:true}).fill('123456');
        await page.getByRole('dialog').getByRole('button',{name:'Continue',exact:true}).click();
        await shot(`pin-new-${width}`);
        await page.getByLabel('New PIN',{exact:true}).fill('789012');
        await page.getByRole('dialog').getByRole('button',{name:'Continue',exact:true}).click();
        await shot(`pin-confirm-${width}`);
        await page.keyboard.press('Escape');
      }
      await page.getByRole('button',{name:'Back to Settings',exact:true}).click();
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await navigate(page, "Home");
  await page.getByRole("button", { name: "Request", exact: true }).click();
  await page.getByLabel("Who should pay?").fill("Rahul");
  await page.getByLabel("Amount (INR)", { exact: true }).fill("120");
  await page.getByLabel("Note (optional)").fill("Dinner");
  await page.getByRole("button", { name: "Save request", exact: true }).click();
  await page.getByText("Request saved · Not paid", { exact: true }).waitFor();
  await shot("money-request-saved");
  await page.getByRole("button", { name: "Done", exact: true }).click();
  const before = (await call("/api/wallet", null, "GET")).available_balance;
  assert.equal(before, 1000000);
  await page.getByRole("button", { name: /^Notifications/ }).click();
  await page
    .getByRole("button", { name: "Mark all read", exact: true })
    .click();
  await page.keyboard.press("Escape");
  await page.reload();
  assert.equal(
    (await call("/api/product/notifications", null, "GET")).unread,
    0,
  );
  await page.getByRole("button", { name: "Type instead", exact: true }).click();
  await page
    .getByLabel("Ask about your wallet or payments")
    .fill("Pay my train ticket and movie tickets");
  await page.getByRole("button", { name: "Send request", exact: true }).click();
  await page
    .getByRole("region", { name: "Exact payment review" })
    .getByText("CinemaPass", { exact: true })
    .waitFor();
  await shot("voice-prepared-batch-typed-deterministic");
  await page
    .getByRole("button", { name: "Cancel review", exact: true })
    .click();
  await page.keyboard.press("Escape");
  await navigate(page, "Inbox");
  await page.getByLabel("Select Indian Railways", { exact: true }).check();
  await page.getByLabel("Select CinemaPass", { exact: true }).check();
  await page
    .getByRole("button", { name: "Review 2 selected", exact: true })
    .click();
  const panel = page
    .getByRole("dialog")
    .getByRole("region", { name: "Exact payment review" });
  await panel.getByText("CinemaPass", { exact: true }).waitFor();
  await shot("exact-batch-review");
  await panel.getByLabel("Six-digit wallet PIN").fill("000000");
  await panel
    .getByRole("button", { name: "Approve exact payments", exact: true })
    .click();
  await panel.getByRole("alert").waitFor();
  // Existing security.updated_at session binding intentionally revokes the session after a failed PIN.
  assert.equal(
    await page.evaluate(async () => (await fetch("/api/wallet")).status),
    401,
  );
  await page.reload();
  await page.getByLabel("Wallet PIN", { exact: true }).fill("123456");
  await page
    .getByRole("button", { name: "Unlock wallet", exact: true })
    .click();
  await page.getByText("Your wallet.", { exact: true }).waitFor();
  assert.equal(
    (await call("/api/wallet", null, "GET")).available_balance,
    before,
  );
  await navigate(page, "Inbox");
  await page.getByLabel("Select Indian Railways", { exact: true }).check();
  await page.getByLabel("Select CinemaPass", { exact: true }).check();
  await page
    .getByRole("button", { name: "Review 2 selected", exact: true })
    .click();
  await panel.getByText("CinemaPass", { exact: true }).waitFor();
  await panel.getByLabel("Six-digit wallet PIN").fill("123456");
  await panel
    .getByRole("button", { name: "Approve exact payments", exact: true })
    .click();
  await panel
    .getByRole("heading", {
      name: "All selected payments completed",
      exact: true,
    })
    .waitFor();
  await shot("actual-batch-success");
  assert.equal(
    (await call("/api/wallet", null, "GET")).available_balance,
    815000,
  );
  const batches = await call("/api/product/batches", null, "GET");
  const settled = batches.find((b) => b.status === "SUCCEEDED");
  assert.equal(settled.items.length, 2);
  assert.ok(settled.items.every((i) => i.receipt?.journal_id));
  for (const path of [
    `/api/product/documents/batches/${settled.id}.pdf`,
    `/api/product/documents/payments/${settled.items[0].id}.pdf`,
  ]) {
    const bytes = await page.evaluate(async (path) => {
      const r = await fetch(path);
      return {
        status: r.status,
        type: r.headers.get("content-type"),
        head: (await r.text()).slice(0, 8),
      };
    }, path);
    assert.equal(bytes.status, 200);
    assert.equal(bytes.type, "application/pdf");
    assert.equal(bytes.head, "%PDF-1.4");
  }
  await page.keyboard.press("Escape");
  await navigate(page, "Activity");
  await page
    .getByRole("button", { name: "View batch", exact: true })
    .first()
    .waitFor();
  await shot("activity-documents");
  // Presentation-only partial and pending responses, explicitly not settlement evidence.
  for (const status of ["PARTIAL", "PROCESSING", "FAILED"]) {
    await page.route(`**/api/payment-batches/${settled.id}`, (route) =>
      route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          ...settled,
          status,
          items: settled.items.map((i, n) =>
            n || status==='FAILED'
              ? {
                  ...i,
                  status: status !== "PROCESSING" ? "FAILED" : "PROCESSING",
                  receipt: null,
                  failure_reason:
                    status !== "PROCESSING"
                      ? "Isolated browser fixture denial"
                      : null,
                }
              : i,
          ),
        }),
      }),
    );
    await page
      .getByRole("button", { name: "View batch", exact: true })
      .filter({ visible: true })
      .first()
      .click();
    await page
      .getByRole("heading", {
        name:
          status === "PARTIAL"
            ? "Some payments need attention"
            : status === 'FAILED' ? 'Payments failed' : "Payments processing",
        exact: true,
      })
      .waitFor();
    await shot(`fixture-${status.toLowerCase()}`);
    await page.keyboard.press("Escape");
    await page.unroute(`**/api/payment-batches/${settled.id}`);
  }
  await page
    .getByRole("button", { name: "Open account and Settings", exact: true })
    .click();
  await page.getByRole('button',{name:'AI & Voice',exact:true}).click();
  await page.getByRole('checkbox',{name:/Review transcript before sending/}).uncheck();
  assert.equal(await page.evaluate(()=>localStorage.getItem('wallet-review-transcript')),'off');
  await page.getByRole('checkbox',{name:/Review transcript before sending/}).check();
  await shot('voice-settings');
  await navigate(page,'Bills & Subscriptions');
  await page.getByRole('button',{name:'Track a bill or renewal',exact:true}).click();
  await page.getByLabel('Biller or subscription').fill('My manually tracked renewal');
  await page.getByLabel('Expected amount (INR)').fill('199');
  await page.getByLabel('Next due date').fill(new Date(Date.now()+30*86400000).toISOString().slice(0,16));
  await shot('bill-form');
  await page.getByRole('button',{name:'Save expected expense',exact:true}).click();
  await page.getByText('My manually tracked renewal',{exact:true}).waitFor();
  assert.equal((await call('/api/wallet',null,'GET')).available_balance,815000);
  await shot('bills-saved');
  await navigate(page,'Auto-pay & security');
  await page.getByRole('button',{name:'Security',exact:true}).click();
  await page.getByRole('button',{name:'Change PIN',exact:true}).click();
  await page.getByLabel('Current PIN',{exact:true}).fill('123456');
  await page.getByRole('dialog').getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByLabel('New PIN',{exact:true}).fill('654321');
  await page.getByRole('dialog').getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByLabel('Confirm new PIN',{exact:true}).fill('654320');
  assert.ok(await page.getByRole('button',{name:'Update PIN',exact:true}).isDisabled());
  await shot('change-pin-mismatch');
  await page.getByLabel('Confirm new PIN',{exact:true}).fill('654321');
  await page.getByRole('button',{name:'Update PIN',exact:true}).click();
  await page.getByRole('dialog').getByRole('button',{name:'Done',exact:true}).click();
  await page.getByRole('dialog').waitFor({state:'detached'});
  await page.reload();await page.getByLabel('Wallet PIN',{exact:true}).fill('654321');
  await page.getByRole('button',{name:'Unlock wallet',exact:true}).click();
  await page.getByText('Your wallet.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Open account and Settings',exact:true}).click();
  await page.getByRole("button", { name: "Appearance", exact: true }).click();
  await page.getByRole("button", { name: "Dark", exact: true }).click();
  await shot("dark-settings");
  await page.reload();
  assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
  for (const screen of ["Home", "Pay", "Inbox", "Activity", "Accounts & Cards"]) {
    await navigate(page, screen);
    await shot(`dark-${screen.toLowerCase().replaceAll(" ","-")}`);
  }
  await page.route('**/api/product/notifications',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({items:[],unread:0,mode:'explicit-empty-fixture'})}));
  await page.reload();
  await page.getByRole('button',{name:/^Notifications/}).click();
  await page.getByText('No notices in this section.',{exact:true}).waitFor();
  await shot('notification-empty-fixture');
  await page.keyboard.press('Escape');
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify(
      {
        status: "passed",
        viewports: 6,
        screenshots: output,
        journeys: [
          "four-tab navigation",
          "accounts capability labels",
          "notification read persists",
          "request creates no debit",
          "typed deterministic voice batch preparation",
          "manual exact batch",
          "wrong PIN blocks",
          "actual PIN settlement and balance",
          "actual PDF records",
          "fixture partial/pending display",
          "persisted dark theme",
          "manual bill creates no debit",
          "shared voice preferences",
          "PIN mismatch disabled, change and re-login",
        ],
      },
      null,
      2,
    ),
  );
} catch (e) {
  console.error(e);
  throw e;
} finally {
  if (browser) await browser.close();
  backend.kill();
  web.kill();
}

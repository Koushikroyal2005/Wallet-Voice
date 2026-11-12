// Actual disposable FastAPI/SQLite data; QR frames synthetic, providers disabled.
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";
import assert from "node:assert/strict";
import { navigate } from "./navigation.mjs";
const folder = await mkdtemp(join(tmpdir(), "wallet-completion-"));
const env = {
  ...process.env,
  DATABASE_URL: `sqlite:///${join(folder, "v3-browser-completion.db").replaceAll("\\", "/")}`,
  REQUIRE_WALLET_LOGIN: "true",
  WALLET_SESSION_SECRET: "isolated-completion-browser-secret-32-characters",
  DEMO_WALLET_PIN: "123456",
  NVIDIA_ENABLED: "false",
  PAYPAL_ENABLED: "false",
  TEST_DATABASE_URL: "",
  V3_RAIL_KEY: "completion-rail-test-only",
  V3_FOOD_KEY: "completion-food-test-only",
  VERIFICATION_PORT: "8196",
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
    "5196",
    "--strictPort",
  ],
  { windowsHide: true, stdio: "ignore" },
);
const output = resolve("../artifacts/prompt-completion");
await mkdir(output, { recursive: true });
let browser;
try {
  for (let i = 0; i < 300; i++) {
    try {
      if ((await fetch("http://127.0.0.1:8196/health")).ok) {
        await fetch("http://127.0.0.1:5196");
        break;
      }
    } catch {}
    if (backend.exitCode !== null) throw Error("Isolated API exited");
    await new Promise((r) => setTimeout(r, 100));
  }
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: process.env.DESKTOP_ONLY ? {width:1280,height:800} : { width: 390, height: 844 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => {
    window.EventSource = class {
      close() {}
    };
    Object.defineProperty(window, "BarcodeDetector", {
      value: undefined,
      configurable: true,
    });
  });
  await page.route("**/api/**", (route) => {
    const u = new URL(route.request().url());
    return route.continue({
      url: "http://127.0.0.1:8196" + u.pathname + u.search,
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
        if (!r.ok) throw Error(`Test API ${r.status}`);
        return r.json();
      },
      { path, body, method },
    );
  }
  async function shot(name) {
    await page.screenshot({
      path: join(output, name + ".png"),
      animations: "disabled",
    });
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      name + " page overflow",
    );
    const d = page.getByRole("dialog");
    if (await d.count())
      assert.ok(
        await d.last().evaluate((el) => el.scrollWidth <= el.clientWidth),
        name + " dialog overflow",
      );
  }
  await page.goto("http://127.0.0.1:5196", {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page.getByLabel("Wallet PIN", { exact: true }).fill("123456");
  await page
    .getByRole("button", { name: "Unlock wallet", exact: true })
    .click();
  await page.getByText("Your wallet.", { exact: true }).waitFor();
  for (const [name, handle] of [
    ["Rahul", "+919111111111"],
    ["Priya", "+919222222222"],
  ])
    await call("/api/recipients", { name, handle });
  await navigate(page, "Pay");
  await page
    .getByRole("button", { name: "Paste payment link", exact: true })
    .click();
  for (const [width, height] of (process.env.DESKTOP_ONLY ? [[1024,900],[1280,800],[1440,900]] : [
    [360, 800],
    [390, 844],
    [430, 932],
    [768, 1024],
    [1024, 900],
    [1440, 900],
  ])) {
    await page.setViewportSize({ width, height });
    await shot(`intake-${width}`);
  }
  await page.setViewportSize(process.env.DESKTOP_ONLY ? {width:1280,height:800} : { width: 390, height: 844 });
  await page
    .getByLabel("HTTPS checkout link (optional for manual entry)")
    .fill("https://127.0.0.1/private");
  await page.getByLabel("Claimed merchant").fill("Claimed store");
  await page.getByLabel("Amount", { exact: true }).fill("125");
  await page
    .getByRole("button", { name: "Save unverified checkout", exact: true })
    .click();
  await page
    .getByRole("alert")
    .getByText(/Use an HTTPS checkout URL/)
    .waitFor();
  await page
    .getByLabel("HTTPS checkout link (optional for manual entry)")
    .fill("https://example.com/checkout");
  await page
    .getByRole("button", { name: "Save unverified checkout", exact: true })
    .click();
  await page.getByText("Saved · Unverified", { exact: true }).waitFor();
  await shot("import-saved-unverified");
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await navigate(page, "Inbox");
  await page
    .getByRole("button", { name: "Review saved details", exact: true })
    .click();
  await page.getByText(/cannot execute this imported checkout/).waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Confirm action", exact: true })
      .count(),
    0,
  );
  await shot("unverified-review");
  await page
    .getByRole("button", { name: "Hold imported checkout", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Restore imported checkout", exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "Restore imported checkout", exact: true })
    .click();
  await page.waitForFunction(
    () =>
      !document.querySelector('dialog button[aria-label="Close dialog"]')
        ?.disabled,
  );
  await page.keyboard.press("Escape");
  await page.getByRole("dialog").waitFor({ state: "detached" });
  await navigate(page, "Pay");
  await page.getByRole("button", { name: "Scan QR", exact: true }).click();
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await page.getByText(/QR scanning is unavailable/).waitFor();
  await shot("qr-paste-fallback");
  await page.keyboard.press("Escape");
  await page.evaluate(() => {
    window.__cameraStopped = 0;
    HTMLMediaElement.prototype.play = async () => {};
    navigator.mediaDevices.getUserMedia = async () => {
      const s = new MediaStream();
      s.getTracks = () => [
        {
          stop() {
            window.__cameraStopped++;
          },
        },
      ];
      return s;
    };
    Object.defineProperty(window, "BarcodeDetector", {
      configurable: true,
      value: class {
        async detect() {
          return [{ rawValue: "https://example.com/qr-checkout" }];
        }
      },
    });
  });
  await page.getByRole("button", { name: "Scan QR", exact: true }).click();
  await page.getByRole("button", { name: "Start camera", exact: true }).click();
  await page
    .getByLabel("HTTPS checkout link (optional for manual entry)")
    .filter({ visible: true })
    .waitFor();
  await page.waitForFunction(
    () =>
      document.querySelector("input[type=url]")?.value ===
      "https://example.com/qr-checkout",
  );
  assert.ok(await page.evaluate(() => window.__cameraStopped >= 1));
  await shot("synthetic-qr-decoded-no-payment");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Split a bill", exact: true }).click();
  await page.getByLabel("Total amount (INR)").fill("100.01");
  await page
    .getByLabel("Participants, separated by commas")
    .fill("me, Rahul, Priya");
  await page
    .getByRole("button", { name: "Preview exact split", exact: true })
    .click();
  await page.getByText("Review each share", { exact: true }).waitFor();
  assert.equal(
    (await call("/api/product/money-requests", null, "GET")).length,
    0,
  );
  await shot("exact-split-preview");
  await page
    .getByRole("button", { name: "Confirm creating requests", exact: true })
    .click();
  await page
    .getByText("Requests created · Not paid", { exact: true })
    .waitFor();
  assert.equal(
    (await call("/api/product/money-requests", null, "GET")).length,
    2,
  );
  await shot("split-requests-created");
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await navigate(page, "Activity");
  await page.getByRole('button',{name:'Documents & Receipts',exact:true}).click();
  await page
    .getByRole("button", { name: "Import bill / invoice PDF", exact: true })
    .click();
  const request = await call("/api/merchant/payment-requests", {
    type: "movie",
  });
  const batch = await call("/api/payment-batches", {
    payment_ids: [request.id],
  });
  const bytes = await page.evaluate(
    async (id) =>
      Array.from(
        new Uint8Array(
          await (
            await fetch(`/api/product/documents/batches/${id}.pdf`)
          ).arrayBuffer(),
        ),
      ),
    batch.id,
  );
  await page.getByLabel("Document title").fill("My uploaded cinema bill");
  await page
    .getByLabel("PDF file (maximum 2 MiB)")
    .setInputFiles({
      name: "bill.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from(bytes),
    });
  await shot("document-import");
  await page
    .getByRole("button", { name: "Save unverified document", exact: true })
    .click();
  await page.getByText("My uploaded cinema bill", { exact: true }).waitFor();
  await page.getByLabel("Search documents").fill("cinema");
  await page
    .getByRole("button", { name: "Preview record", exact: true })
    .first()
    .click();
  await shot("document-preview");
  await page.getByText("Uploaded by you — not verified and not proof of payment", { exact: true }).waitFor();
  assert.equal(await page.getByText("USER_UPLOADED_NOT_PAYMENT_PROOF", { exact: true }).count(), 0);
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Open account and Settings", exact: true })
    .click();
  await page
    .getByRole("navigation", { name: "Settings sections" })
    .getByRole("button", { name: "Notifications", exact: true })
    .click();
  await page
    .getByText("Notification categories & privacy", { exact: true })
    .waitFor();
  await shot("notification-categories");
  assert.equal(
    (await call("/api/wallet", null, "GET")).available_balance,
    1000000,
  );
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify(
      {
        status: "passed",
        screenshots: output,
        intake_viewports: process.env.DESKTOP_ONLY ? 3 : 6,
        journeys: [
          "unsafe URL rejected",
          "unverified intake cannot execute",
          "hold/restore imported details",
          "QR unavailable fallback",
          "synthetic QR decode stops camera",
          "exact split preview has no requests",
          "confirmed split creates two requests without debit",
          "real PDF upload/catalog/preview",
          "notification category controls",
        ],
        live_camera: false,
        live_providers: false,
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

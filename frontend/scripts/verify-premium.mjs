// UI/lifecycle fixtures only. V3 separately proves actual isolated backend settlement.
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import assert from "node:assert/strict";
const web = spawn(
  process.execPath,
  [
    "node_modules/vite/bin/vite.js",
    "--host",
    "127.0.0.1",
    "--port",
    "5199",
    "--strictPort",
  ],
  { windowsHide: true, stdio: "ignore" },
);
const output = resolve("../artifacts/premium-assistant");
await mkdir(output, { recursive: true });
let browser;
try {
  for (let n = 0; n < 150; n++) {
    try {
      await fetch("http://127.0.0.1:5199");
      break;
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  browser = await chromium.launch({ headless: true });
  for (const [width, height] of [
    [390, 844],
    [430, 932],
    [768, 1024],
    [1440, 900],
  ]) {
    const page = await browser.newPage({ viewport: { width, height } });
    await page.clock.install();
    const turns = [],
      errors = [];
    let batchState = "REVIEW",
      authorized = 0,
      confirmations = 0;
    page.on("pageerror", (e) => errors.push(e.message));
    await page.addInitScript(() => {
      window.EventSource = class {
        close() {}
      };
      window.__audio = { stopped: 0, denied: false };
      navigator.mediaDevices.getUserMedia = async () => {
        if (window.__audio.denied)
          throw new DOMException(
            "Fixture permission denied",
            "NotAllowedError",
          );
        return {
          getTracks: () => [
            {
              stop() {
                window.__audio.stopped++;
              },
            },
          ],
        };
      };
      window.MediaRecorder = class {
        static isTypeSupported() {
          return true;
        }
        state = "inactive";
        mimeType = "audio/webm";
        start() {
          this.state = "recording";
        }
        stop() {
          this.state = "inactive";
          this.ondataavailable?.({
            data: new Blob(["synthetic speech"], { type: "audio/webm" }),
          });
          queueMicrotask(() => this.onstop?.());
        }
      };
      window.AudioContext = class {
        resume() {
          return Promise.resolve();
        }
        close() {
          return Promise.resolve();
        }
        createAnalyser() {
          return { fftSize: 2048, getFloatTimeDomainData: (a) => a.fill(0.06) };
        }
        createMediaStreamSource() {
          return { connect() {} };
        }
      };
    });
    const payments = [
      {
        id: "rail",
        merchant: "Demo Railway",
        amount: 125000,
        currency: "INR",
        status: "PENDING",
        category: "travel",
        description: "Train ticket",
        verified: true,
        expires_at: new Date(Date.now() + 720000).toISOString(),
        trace: { urgency: "URGENT" },
      },
      {
        id: "food",
        merchant: "Demo Kitchen",
        amount: 40000,
        currency: "INR",
        status: "PENDING",
        category: "food",
        description: "Food order",
        verified: true,
      },
    ];
    const batch = () => ({
      id: "fixture-batch",
      status: batchState,
      source: "AI_WALLET",
      total: 165000,
      available_balance: 1000000,
      reserved_amount: 0,
      remaining_after_payment: 835000,
      can_authorize: batchState === "REVIEW",
      items: payments.map((p) => ({
        ...p,
        blocked: false,
        reason_codes: [],
        receipt:
          batchState === "SUCCEEDED"
            ? {
                journal_id: "FIXTURE-JOURNAL-" + p.id,
                status: "SUCCEEDED",
                timestamp: new Date().toISOString(),
              }
            : null,
        status: batchState === "SUCCEEDED" ? "SUCCEEDED" : p.status,
      })),
    });
    await page.route("https://**/*", (r) => r.abort());
    await page.route("**/api/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      let data = [];
      if (path === "/api/auth/session")
        data = { authenticated: true, required: true };
      else if (path === "/api/wallet")
        data = {
          posted_balance: 1000000,
          available_balance: 1000000,
          reserved_amount: 0,
        };
      else if (path === "/api/payments") data = payments;
      else if (path === "/api/notifications")
        data = {
          items: payments.map((p) => ({
            ...p,
            payment_id: p.id,
            stage: "URGENT",
            deadline: p.expires_at,
          })),
          preferences: { enabled: false },
        };
      else if (path === "/api/assistant/status")
        data = { browser_tts_fallback: false };
      else if (path.includes("/conversations/")) data = { messages: [] };
      else if (path === "/api/voice/transcribe")
        data = {
          transcript: "What is my balance?",
          provider: "synthetic-STT-fixture",
        };
      else if (path === "/api/assistant/turn") {
        const body = route.request().postDataJSON();
        turns.push(body);
        await new Promise((r) => setTimeout(r, 700));
        data = {
          conversation_id: body.conversation_id,
          provider: "demo-parser",
          response: body.text.includes("Pay")
            ? "Review these exact two simulated payments. Your PIN is required."
            : "Your available simulated balance is 10,000 INR.",
          data: body.text.includes("Pay")
            ? payments
            : { available_balance: 1000000, reserved_amount: 0 },
          ...(body.text.includes("Pay")
            ? {
                action_preview: {
                  kind: "payment_batch",
                  batch_id: "fixture-batch",
                  requires_confirmation: true,
                },
              }
            : {}),
        };
      } else if (path === "/api/payment-batches/fixture-batch/authorize") {
        authorized++;
        data = { approval_token: "fixture-token" };
      } else if (path === "/api/payment-batches/fixture-batch/confirm") {
        confirmations++;
        batchState = "SUCCEEDED";
        data = batch();
      } else if (path === "/api/payment-batches/fixture-batch") data = batch();
      await route.fulfill({ json: data });
    });
    const conversation = page.getByRole("region", {
      name: "Wallet conversation",
    });
    async function capture(name) {
      await page.screenshot({ path: resolve(output, `${name}-${width}.png`),animations:'disabled' });
      assert.ok(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        name + ": overflow",
      );
      if (await conversation.isVisible())
        assert.ok(
          await conversation.evaluate((el) => el.scrollWidth <= el.clientWidth),
          name + ": assistant overflow",
        );
    }
    await page.goto("http://127.0.0.1:5199");
    await page
      .getByRole("heading", { name: "Your wallet.", exact: true })
      .waitFor();
    await capture("voice-idle");
    const homeBefore = await page
      .getByRole("region", { name: "Wallet overview" })
      .boundingBox();
    await page
      .getByRole("button", { name: "Open wallet assistant", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Stop recording", exact: true })
      .waitFor();
    await page.waitForTimeout(350);
    assert.ok(
      Number(
        await page
          .locator(".voice-hud .guardian-orb")
          .evaluate((el) => el.style.getPropertyValue("--voice-level")),
      ) > 0,
      "Ring reflects actual analyser samples",
    );
    const homeAfter = await page
      .getByRole("region", { name: "Wallet overview" })
      .boundingBox();
    assert.equal(homeBefore.y, homeAfter.y, "Opening voice never moves Home");
    assert.equal(await page.locator("#voice-home-session").count(), 0);
    await capture("voice-listening");
    await page
      .getByRole("navigation")
      .getByRole("button", { name: "Wallet", exact: true })
      .click();
    assert.ok(await conversation.isVisible(), "Navigation preserves assistant");
    await page
      .getByRole("button", { name: "Stop recording", exact: true })
      .click();
    await page.getByText("Transcript ready", { exact: true }).waitFor();
    assert.equal(turns.length, 0, "Default transcript review does not submit");
    await page
      .getByLabel("Ask about your wallet or payments")
      .fill("What is my balance?");
    await page.getByRole("button", { name: "Send request" }).click();
    await page.getByText("Understanding…", { exact: true }).waitFor();
    await capture("voice-thinking");
    await page.locator(".answer-balance").waitFor();
    await capture("voice-quick-answer");
    await page.waitForTimeout(100);
    await page.clock.fastForward(16000);
    await conversation.waitFor({ state: "hidden" });
    await page
      .getByRole("button", { name: "Open wallet assistant", exact: true })
      .waitFor();
    await page.evaluate(() =>
      window.dispatchEvent(
        new CustomEvent("wallet-assistant-open", { detail: "chat" }),
      ),
    );
    await page
      .getByLabel("Conversation history")
      .getByText("What is my balance?", { exact: true })
      .waitFor();
    await capture("chat-history");
    await page
      .getByLabel("Ask about your wallet or payments")
      .fill("Pay railway and food");
    await page.getByRole("button", { name: "Send request" }).click();
    await conversation
      .getByRole("region", { name: "Exact payment review" })
      .waitFor();
    const review = conversation.getByRole("region", {
      name: "Exact payment review",
    });
    await review.getByLabel("Six-digit wallet PIN").waitFor();
    await capture("exact-batch-review");
    assert.equal(
      turns[0].conversation_id,
      turns[1].conversation_id,
      "Voice and chat share one server conversation",
    );
    await conversation
      .getByRole("button", { name: "Voice", exact: true })
      .click();
    await review.getByText("Demo Railway", { exact: true }).waitFor();
    await page
      .getByRole("button", { name: "Stop recording", exact: true })
      .click();
    await page.getByText("Transcript ready", { exact: true }).waitFor();
    await page.clock.fastForward(16000);
    assert.ok(await conversation.isVisible(), "Approval never auto-dismisses");
    await capture("voice-payment-preview");
    await review.getByLabel("Six-digit wallet PIN").fill("123456");
    await capture("pin-review");
    await review
      .getByRole("button", { name: "Approve exact payments", exact: true })
      .evaluate((b) => {
        b.click();
        b.click();
      });
    await review
      .getByRole("heading", { name: "All selected payments completed" })
      .waitFor();
    assert.equal(authorized, 1);
    assert.equal(confirmations, 1);
    await capture("recorded-fixture-success");
    await page.keyboard.press("Escape");
    assert.ok(await page.evaluate(() => window.__audio.stopped >= 2));
    await page.evaluate(() => {
      window.__audio.denied = true;
    });
    await page
      .getByRole("button", { name: "Open wallet assistant", exact: true })
      .click();
    await page
      .getByText(
        "Microphone permission was not granted. Type your request instead.",
      )
      .waitFor();
    await capture("microphone-error");
    await page.clock.fastForward(16000);
    assert.ok(await conversation.isVisible(), "Errors never auto-dismiss");
    await conversation
      .getByRole("button", { name: "Chat", exact: true })
      .click();
    if (width < 500) {
      await page.setViewportSize({ width, height: 520 });
      const composer = await page.locator(".assistant-composer").boundingBox();
      assert.ok(
        composer.y + composer.height <= 520,
        "Composer remains above simulated keyboard viewport",
      );
      await capture("keyboard-viewport");
    }
    await page.emulateMedia({ reducedMotion: "reduce" });
    assert.equal(
      await page
        .locator(".orb-rim")
        .first()
        .evaluate((el) => getComputedStyle(el).animationName),
      "none",
    );
    assert.deepEqual(errors, []);
    await page.close();
  }
  console.log(
    "PASSED: premium assistant at 390/430/768/1440: stable overlay, measured audio ring, navigation continuity, editable transcript opt-in, thinking and balance cards, shared chat, read-only collapse, persistent approval/error, duplicate approval guard, track cleanup, reduced motion and simulated keyboard viewport. All provider/payment responses in this suite are fixtures.",
  );
} finally {
  await browser?.close();
  web.kill();
}

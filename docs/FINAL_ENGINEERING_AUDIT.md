# Final engineering audit — 12 November 2026

**Superseded pending list:** [FINAL_COMPLETION.md](FINAL_COMPLETION.md) records completion of the repository/UI items previously listed in section 9, including Unicode fonts/tables, guided PIN, common controls, Activity consolidation, integrated Settings, typed reviews and expanded visual verification. This document retains the original audit evidence; its pending-code statements are historical.

## Owner-requested follow-up and publication

The owner subsequently requested a final cross-check and push to the current branch (`main`). The no-push statements below describe the earlier audit checkpoint. The follow-up corrected two additional issues: Activity now resolves funding source and amount from exact-attempt evidence instead of assuming every reservation-less attempt is PayPal; cancelling Change PIN clears all entered digits and the prior error. A regression explicitly covers unresolved funding evidence. Latest targeted unit run: **39 passed**, 41.20 seconds. TypeScript/Vite production build passed again. Earlier full-suite counts below remain historical, not reruns of the new test. GitHub CI and live-provider checks remain unexecuted. No claim is made that every remaining item in section 9 is complete.

Follow-up isolated PostgreSQL receipt/source suite: **5 passed**, 6.67 seconds, one upstream Starlette/httpx warning; migrations succeeded. The six-viewport consumer browser journey passed again. Only the disposable audit database was restarted, then stopped. Publication outcome is reported in chat after Git returns; no normal Docker deployment is included.

Baseline and current branch: `29bf5e3`, `main`. This audit is local and uncommitted; no push or application deployment was requested or performed. The pre-existing untracked `.playwright-mcp/` directory was preserved. No private `.env` edits, development database resets, volume deletions, new dependencies or live money-moving requests.

## 1. Confirmed bugs fixed

- Historical document entries previously linked to the request's latest receipt. New attempt-specific JSON/PDF routes resolve the exact attempt, reservation, journal and associated PayPal order/capture. The legacy request URL is explicitly a latest-attempt compatibility view.
- Failed batch items could inherit a journal posted by a later successful retry of the same request. A receipt now requires that item's successful attempt and consumed reservation. An actual simulated-wallet fail/retry regression verifies a single debit and no journal in the failed record.
- Home Send now opens Pay, reusing the existing Drafts/recipient engine.
- New Chat no longer sends DELETE. Explicit confirmed deletion awaits the response, reports errors, blocks duplicate submissions and resets stale result cards only after successful deletion. Previous server history remains when starting a new chat.
- Desktop notification presentation no longer calls `showModal()`. It uses a nonmodal dialog, outside-click/Escape dismissal and focus restoration. Mobile keeps the native modal sheet. Navigation/profile closes it.
- Attention notification IDs no longer change with urgency stage. Existing stage-qualified read/dismiss states are respected.
- Consumer/completion/premium browser scripts now run sequentially in CI; synthetic screenshots are uploaded with seven-day retention. Remote CI has **not** run for these unpushed changes.

## 2. Design improvements and screenshot audit

Product Design audit instructions were used: current screenshots were opened before evaluating Settings/voice, then corrected and recaptured. No saved Product Design context was present. Playwright and Product Design instructions were available; no Componentry/Skecher/Arc MCP capability was found. Componentry and Skecher documentation were inspected as references only; Arc's page timed out. No external component code or assets were copied.

1. Home/Pay/Inbox: existing navigation, manual batch selection and financial controls retained; Home Send routing corrected. Consumer captures cover 360/390/430/768/1024/1440.
2. Settings: original six-button strip was visibly redundant. Replaced by grouped rows, focused detail pages and desktop category sidebar. Existing security and AutoPay services reused.
3. Notifications: desktop screenshot confirms an undimmed main application and constrained panel. Row management actions moved under More. Mobile remains a sheet.
4. Activity: now has readable status labels, a typed timeline model, focused exact-attempt detail and visible Documents & Receipts entry. Technical references are expandable. Secondary legacy histories are still available, not deleted.
5. Voice: original listening capture was a tall mini-page. Compact state reduces the surface/orb and removes welcome/diagnostics while listening/thinking. Transcript review, errors and financial actions remain expanded and persistent.
6. Dark mode: captures added for Home/Pay/Inbox/Activity/Accounts. A loading-state Activity capture was rejected; the capture helper now waits for actual Activity rows. Screenshot presence is not a WCAG certificate or physical-device test.

## 3. Settings and forms

`SettingsNavigation.tsx` extracts grouped categories. Security and AutoPay render separately without their old nested switch. The existing masked six-digit Change PIN, mismatch validation, lockout errors, backend approval invalidation and change/re-login journey remain. Merchant permission creation now guides business → limits → expiry → review → existing PIN authorization. Global request rules and merchant allowances remain distinct. Theme is an immediate, persisted Light/Dark/System segmented control. Privacy text describes actual deletion semantics.

## 4. Voice assistant

NVIDIA adapters and backend tool behavior are unchanged. Compact presentation applies only to suitable voice states; actionable previews/errors/transcript review are not hidden or auto-approved. Chat and voice use the same persistent controller. Browser fixtures verify new chat does not issue DELETE, failed deletion is visible, explicit retry succeeds, microphone tracks stop, duplicate approval is blocked and reduced motion is respected. These are **synthetic audio/model fixtures**, not live NVIDIA or physical microphone evidence.

## 5. Batch Pay

Exact immutable review, one PIN for the eligible simulated-wallet batch, real per-item statuses, currency-separated totals and statements are retained. No autonomous execution, policy weakening or external universal PIN. Batch receipt association is corrected without changing reservation/execution policy. Existing consumer and V3 journeys execute real isolated simulated-wallet journals; pending/partial provider presentation remains fixture evidence.

## 6. Financial records

`documents.py` supplies attempt-specific fields and safe attachment filenames, no-store caching, evidence-based source labels and explicit missing-evidence states. Owned PayPal orders and reservation wallets are checked within the existing single-owner security model. Catalog entries expose attempt/payment IDs, source, references, timestamp and attempt-specific URL. Refunds retain capture references and expose only recorded verified refund-event references/amounts; no partial refund support is invented. PDF branding, amount emphasis, dividers and page footer improve the existing lightweight renderer without adding a library. **The renderer remains WinAnsi Helvetica; full Unicode/non-Latin font support is not complete.**

## 7. Verification

- `cd backend; python -m pytest -q --tb=short`: **286 passed, 100 skipped**, 194.53 seconds. 99 PostgreSQL-only cases skipped in this local run; one optional local Web Push adapter dependency missing.
- Separate isolated PostgreSQL project `walletvoice-final-audit`: migrations succeeded; `python -m pytest -p no:cacheprovider -q tests/integration --tb=short`: **99 passed, zero failed/skipped**, 147.93 seconds. One upstream Starlette/httpx deprecation warning. Only its tmpfs test database was used and stopped afterward; development services/volumes untouched.
- Targeted final document/consumer/planning regressions: **38 passed**, 56.46 seconds.
- `cd frontend; npm.cmd run build`: TypeScript and Vite passed.
- `node scripts/verify-product.mjs`: passed five viewport product journeys, including guided permission review and recipient drafts.
- `node scripts/verify-completion.mjs`: passed nine journeys and six intake sizes after selectors were adapted to the new Settings/document navigation.
- `node scripts/verify-premium.mjs`: passed four viewport assistant fixtures, including explicit deletion failure/retry and non-destructive New Chat.
- `node scripts/verify-guardian.mjs`: passed nine fixture scenarios.
- `node scripts/verify-v3.mjs`: passed actual isolated wallet/PIN/journal/recipient journey; STT synthetic.
- `node scripts/verify-consumer.mjs`: six-size navigation, exact settlement, PIN change/re-login and PDF journeys passed during this audit. Final stable-capture rerun outcome is appended below, not inferred.
- Python compilation, quiet Compose configuration and diff whitespace checks passed.

Initial sandbox pytest could not create its temporary directory; host-permission rerun used disposable databases. An initial receipt test exposed changed wording and passed after restoring compatibility. Browser assertions exposed obsolete Settings selectors, which were updated to exercise the replacement controls; assertions were not removed. A broad network-idle screenshot wait timed out and was replaced by a loaded-Activity assertion. One attempted test invocation named a nonexistent `test_batches.py`; no tests ran in that invocation, and correct existing suites were then executed.

## 8. Screenshots

Local ignored artifacts (synthetic/demo data only):

- `artifacts/consumer-product/settings-390.png`, `settings-1440.png`, `notifications-1440.png`, `change-pin-mismatch.png`, `voice-settings.png`, `dark-pay.png`, `dark-activity.png` plus six-size main screens.
- `artifacts/premium-assistant/voice-listening-390.png`, `voice-thinking-390.png`, `voice-quick-answer-390.png`, `exact-batch-review-390.png` and corresponding four-size lifecycle captures.
- `artifacts/premium-review/permission-approval.png` and product captures.
- `artifacts/prompt-completion/document-preview.png`, upload/split/intake captures.

Settings mobile, desktop notifications, compact listening and dark Pay/Activity files were opened for inspection during this audit. The first dark Activity screenshot contained loading and was rejected. Not every generated capture has received manual visual inspection; do not claim comprehensive screenshot acceptance. Earlier files are overwritten by their suite's current run, so a complete immutable before/after archive was not retained.

## 9. Remaining work — not a full acceptance claim

- Full Unicode-capable licensed embedded fonts and polished internationalized PDF tables remain unfinished. Standard currency codes are used; non-Latin glyph rendering is not certified.
- Broad shared form-primitives extraction, a genuinely three-screen PIN wizard, complete removal of legacy detailed-history UI and remaining `any` models are not completed. Existing forms/security behavior are preserved.
- New Settings navigation is implemented, but account/destination shortcuts remain in a separate account panel rather than fully interleaved into category rows. Unsupported account/profile features remain explicitly unavailable.
- Not every mandatory screen/state/viewport has been manually visually inspected; notification empty/unread and every error/form capture need a formal acceptance sweep. Physical keyboards, real devices and full WCAG 2.2 AA certification remain unexecuted.
- Live NVIDIA, actual PayPal buyer/capture/webhook delivery, physical microphone/camera, real Web Push and production upload malware scanning are unexecuted/not supplied. Bank/card linking and real bank balances remain unsupported, not mocked as connected.
- GitHub Actions was edited but not pushed or remotely executed. Local success is not proof of green remote CI.

## 10. Changed-file responsibilities

- Backend `documents.py`: exact evidence/JSON/PDF, source/ownership checks, refund metadata and document layout; `planning.py`: attempt catalog/activity URLs; `payment_batches.py`: exact journal association; `product.py`: stable notification IDs.
- New `test_attempt_documents.py` and integration companion: failure/retry, PayPal fixtures, refund retention and notification stage persistence.
- `App.tsx`: Send routing and notification closure; `ConsumerScreens.tsx`, new `SettingsNavigation.tsx`, `Workspace.tsx`: focused Settings, guided merchant permissions, discoverable documents and theme controls.
- `ActivityTimeline.tsx`, `PaymentGuardian.tsx`: exact-attempt details/downloads; `Dialog.tsx`, `NotificationCenter.tsx`: nonmodal desktop interaction and quieter row actions.
- `useWalletAssistant.ts`, `AssistantPreferences.tsx`: explicit deletion and new-chat safety; `FloatingAssistant.tsx`, `premium.css`: conditional compact voice surface; `consumer.css`: existing-file grouped Settings styling.
- Browser `navigation.mjs`, `verify-product/consumer/completion/premium.mjs`: updated public navigation, new assertions/captures; `.github/workflows/verify.yml`: sequential browser coverage and synthetic screenshot artifacts.

No commit, push or deployment performed. This is a verified correctness pass and substantial UI refinement, **not completion of every broad visual acceptance criterion**.

### Final capture acceptance

The final `verify-consumer.mjs` rerun passed all six viewport journeys, including native-modal/nonmodal assertions and dark-screen captures. Final desktop Settings, desktop notification More-menu layout and loaded dark Activity screenshots were opened and accepted after the capture-wait correction. The dark Activity image now shows actual batch records, not loading. This adds to, rather than removes, the explicitly unexecuted visual/device checks above.

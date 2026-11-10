# Wallet-Voice Guardian conversation verification

## Implemented behavior

The assistant reads actual backend payment requests. One urgent result selects that request; multiple results require a business or ordinal choice. “Pay that one” and “use PayPal instead” prepare a review for the selected request. “Why that one?” reads its actual deadline/state. Source choice survives intervening balance questions. Unknown/multiple businesses, expired/held/completed requests, foreign currency and invalid amounts do not produce an executable review. Holds require confirmation and do not schedule a payment.

AI tools never call payment execution or authorize transfers. Drafts only save details. Preparation and conversation messages commit together. Server replay receipts cover the latest 32 request IDs per conversation, and concurrent context changes are rejected before applying an obsolete turn. Financial operation idempotency remains a separate existing boundary. Inference runs outside a database transaction; PostgreSQL locks serialize acceptance of the completed turn.

Obvious PIN/OTP/password disclosures are blocked before conversation storage or Nemotron submission. Legacy secret-shaped history is filtered before inference. This is a heuristic, not comprehensive secret detection. Audio necessarily reaches Whisper before its transcript can be checked: never speak credentials into the microphone.

Transcripts are editable before sending by default. Automatic sending requires opting out of transcript review. Spoken replies require an explicit opt-in each panel session; Read aloud is a separate deliberate action. Closing or switching modes stops tracks and invalidates pending transcription/playback callbacks. A failed assistant request retains its request ID for retry. Unknown businesses require acknowledgement before payment controls are enabled. Fractional rupee amounts remain visible in reviews.

## Evaluation dataset and modes

`backend/tests/voice_cases.json` contains 40 synthetic cases with expected tools and arguments, selected IDs/list context, and expected ambiguity/no-review outcomes. It includes decimals, missing amounts, multiple matches, expired and paid requests, source switching, holds, cancellation, secrets, invalid currencies and attempts to bypass approval.

From the repository root:

```powershell
python scripts/evaluate_voice.py --mode deterministic
python scripts/evaluate_voice.py --mode model
```

Use a fresh terminal for model evaluation if test-only environment overrides disabled NVIDIA in another shell. The script reads the existing private configuration without printing credentials. Model mode skips explicitly when disabled/unconfigured; it never silently substitutes the demo parser. All tool execution for these evaluations uses synthetic in-memory SQLite data, never the development database or payment providers.

Mode labels report what actually handled the turn: `nvidia-nemotron`, `demo-parser`, or `context-resolver`. Configuration status is not live verification. Transcription and playback providers have separate labels, including browser speech fallback. Free-form model prose is not accepted as payment evidence or execution confirmation.

## Observed results, 2026-11-10

- Final local regression: **162 passed, 16 PostgreSQL tests skipped**, exit code 0. TypeScript/Vite production build and Python compilation passed. Existing four-viewport Playwright verification passed; the new seven-journey voice fixture suite also passed with exact fractional-rupee review checks. An intermediate local run exposed a missing skip guard on the new PostgreSQL-only test; that test configuration was corrected before the clean final run.
- Deterministic dataset: all 40 cases passed in the focused pytest run.
- Live configured model: `nvidia/nemotron-3.5-bolt-e4b`. Three evaluation runs each scored 36/40 combined cases. The final run made 12 real Nemotron requests: 8 met exact expected tool/argument outcomes and 4 returned no usable preparation tool. Another 24 cases used the context resolver and 4 were blocked by the secret guard. **36/40 is not a claim of 40 live model inferences or 90% model-only accuracy.**
- Final live failures: `decimal-topup`, `withdraw`, `unknown-business`, `multiple-trains`. They returned safe clarification/no preparation, not a successful payment. Tool-specific prompt clarification and named-tool requests did not eliminate these provider-quality failures. The demo must retain Payments/Wallet as a manual preparation path.
- An earlier run proposed an unrequested AutoPay field. The adapter now removes fields not requested and rejects an opposite switch. Mocked provider tests cover that guard, invalid arguments, incorrect amount units, unrequested payment sources and fabricated-success prose.
- PostgreSQL assistant race: 1 passed, exit code 0, using independent sessions in a new schema in the dedicated tmpfs test database. Two simultaneous submissions with one request ID created one draft and two conversation messages, with no payment attempt or additional journal. No reset/TRUNCATE/development volume was used.
- Voice browser fixtures: 7 journeys passed (editable transcript, close/switch during transcription, close while listening, opt-in automatic sending, stable retry ID, interrupted playback). These simulate microphone/recognition behavior; they do not establish real audio quality.
- Physical microphone, live Whisper transcription and audible Magpie/browser playback were not tested in this phase. Real Sandbox checkout/webhook verification remains separate.

The assistant PostgreSQL case skipped locally was executed separately as described above. The other 15 PostgreSQL cases were not rerun in this phase: 13 original financial/migration tests require prohibited resets, and the two PayPal-specific races belong to the previous phase. Do not report the whole integration suite as passed.

## Reproducible checks

From `backend`, run `python -m pytest -q -ra`. Local tests use isolated SQLite fixtures; PostgreSQL cases skip without their isolated URL. From `frontend`, run:

```powershell
npm.cmd run build
node scripts/verify-product.mjs
node scripts/verify-voice.mjs
```

For the PostgreSQL assistant race, use the existing isolated Compose services and override their reset command:

```powershell
docker compose -p walletvoice-paypal-verification -f docker-compose.yml -f docker-compose.test.yml --profile test up -d --no-deps test-db
docker compose -p walletvoice-paypal-verification -f docker-compose.yml -f docker-compose.test.yml --profile test build test
docker compose -p walletvoice-paypal-verification -f docker-compose.yml -f docker-compose.test.yml --profile test run --rm --no-deps test python -m pytest -p no:cacheprovider -q tests/integration/test_assistant_concurrency.py
docker compose -p walletvoice-paypal-verification -f docker-compose.yml -f docker-compose.test.yml --profile test stop test-db
```

The original financial/migration suite still invokes reset operations and is not represented as run by this narrower test.

## Real manual voice test

1. Start the application with your configured NVIDIA services and sign in. Disable automatic incoming payments for this manual scenario through the normal UI. Create one fresh railway request and record its amount/deadline and the current wallet balance.
2. Open Talk. Grant microphone permission and say “Which payments are urgent?” Stop or pause. Confirm Listening changes to Transcribing, the microphone indicator stops, and the editable transcript is correct. Nothing should submit until Send while transcript review is checked.
3. Send once. Confirm Thinking changes to a backend-derived answer identifying the actual railway request and its deadline. Confirm the provider label reports NVIDIA only if that turn used it. No payment or reservation should exist.
4. Say “pay that one,” review/edit the transcript, then send. Confirm the exact merchant, amount including paise, deadline and source. Say “use PayPal instead” and confirm the old wallet review is replaced with PayPal Sandbox review. Stop before buyer approval to verify preparation alone has not moved money.
5. Say “cancel.” Confirm the preview disappears; ask “pay that one” again and expect clarification. Repeat with two urgent requests and verify no arbitrary selection. Choose the second request by ordinal and verify its actual ID/amount through the UI/backend record.
6. Select a request, say “hold that one,” and explicitly confirm only the hold. Confirm no debit. A date such as Friday must not create a schedule or authorize future payment. Try a stale/expired request and an unknown business; neither may result in silent payment.
7. Test a decimal top-up, a missing amount and a dollar amount. Check exact paise display and the PIN boundary. If live Nemotron refuses the tool, record that failure and use the labeled Wallet path; do not claim voice preparation worked.
8. Keep spoken replies off and verify silence. Enable them and test audible playback; confirm NVIDIA Magpie vs browser fallback labels. Interrupt, switch modes, close the panel, and start a new recording while a prior synthesis response is delayed. Old audio must never start afterward.
9. Test denial of microphone permission, unplugged microphone, silence, background noise and slow speech. Confirm the longer-pause option, 60-second limit, editable transcription and typed fallback. Test on a real desktop browser and a mobile browser over a secure origin.
10. Temporarily interrupt connectivity during transcription and interpretation. Confirm a useful failure, no stale review, no duplicate send, and a retry of the same assistant request. Check microphone release after closing. Use only synthetic dummy PIN/OTP examples when testing rejection; never real credentials.

Record device/browser, revision, exact synthetic phrase, expected/actual transcript, observed provider, processing times, result and any journal/attempt change. The browser fixture suite cannot replace this evidence.

## Remaining boundaries

Voice is turn-based with heuristic silence detection, not continuous listening, partial transcription or semantic interruption. Context is bounded and single-owner, not unlimited personal memory. Secret detection and merchant matching are conservative heuristics. Request replay is bounded to 32 recent IDs and requires clients to reuse IDs. Live tool selection is not yet reliable for the four failures above. No real microphone, speech round-trip, PayPal approval or payment success is inferred from these evaluation scores.

## Files changed in this phase

- `backend/app/voice.py`: grounded request resolution, precise amounts/currencies, constrained model arguments, no free-prose payment claims, and bounded Riva futures off the event loop.
- `backend/app/context.py`: references, explanations, source memory, cancel/hold, currency/amount guards and secret-shaped input detection.
- `backend/app/agentic.py`: transaction-free inference, optimistic conversation rechecks and bounded replay receipts committing alongside drafts/messages.
- `backend/app/main.py`: delegates conversation turns, accepts replay IDs, moves conversion off the event loop, checks transcribed secrets and reports provider/configuration facts.
- `frontend/src/components/VoiceAssistantPanel.tsx`: editable transcript review, explicit speech opt-in, accurate provider labels, generation/abort guards, same-ID retries and unknown-business acknowledgement.
- `frontend/src/components/FloatingAssistant.tsx`: instructions matching transcript review and human approval behavior.
- `frontend/src/lib/formatting.ts`: preserves paise in monetary review displays instead of rounding to whole rupees.
- `backend/tests/voice_cases.json`: 40 expected conversational tool/argument cases.
- `backend/tests/voice_eval_support.py`: isolated synthetic data and non-execution assertions shared by deterministic/live evaluations.
- `backend/tests/test_voice_evaluation.py`: deterministic dataset regression checks only.
- `backend/tests/test_voice_journey.py`: HTTP-backed multi-turn, replay, privacy, ambiguity, expiry and currency tests.
- `backend/tests/test_voice_model_adapter.py`: mocked NVIDIA argument/safety contract and Riva future/deadline tests, separate from live checks.
- `backend/tests/integration/test_assistant_concurrency.py`: independent-session PostgreSQL duplicate-turn test without resets.
- `scripts/evaluate_voice.py`: separately labeled deterministic/live evaluation CLI and measured outcomes.
- `frontend/scripts/verify-voice.mjs`: synthetic microphone lifecycle, no-approval, decimal-display and retry browser checks.
- `docs/VOICE_TESTING.md`, `docs/TESTING.md`, `IMPLEMENTATION_STATUS.md`: actual evidence, limitations and manual voice verification instructions.

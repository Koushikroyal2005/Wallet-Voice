import { Mic, Send, Square } from "lucide-react";
import type { WalletAssistant } from "../hooks/useWalletAssistant";

export function AssistantComposer({
  assistant: a,
}: {
  assistant: WalletAssistant;
}) {
  return (
    <form
      className="assistant-composer"
      onSubmit={(e) => {
        e.preventDefault();
        void a.ask();
      }}
    >
      <label className="sr-only" htmlFor="wallet-command">
        Ask about your wallet or payments
      </label>
      <button
        type="button"
        className="composer-mic"
        disabled={a.busy || a.submitting}
        aria-label={
          a.state === "RECORDING"
            ? "Stop recording"
            : a.state === "SPEAKING"
              ? "Interrupt and speak"
              : "Start recording"
        }
        onClick={() => (a.state === "RECORDING" ? a.stop() : void a.start())}
      >
        {a.state === "RECORDING" ? <Square size={18} /> : <Mic size={20} />}
      </button>
      <input
        id="wallet-command"
        value={a.text}
        disabled={a.state === "RECORDING" || a.busy || a.submitting}
        placeholder="Ask your wallet…"
        autoComplete="off"
        onChange={(e) => {
          a.setText(e.target.value);
          a.setPreview(undefined);
          a.setPinRequired(false);
          a.setRecognizedMerchant(false);
          a.stopVoice();
          if (a.state === "ACTION_PREVIEW") a.setState("IDLE");
        }}
      />
      <button
        type="submit"
        aria-label="Send request"
        disabled={
          a.busy || a.submitting || a.state === "RECORDING" || !a.text.trim()
        }
      >
        <Send size={18} />
      </button>
    </form>
  );
}

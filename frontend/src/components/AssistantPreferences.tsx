import type { WalletAssistant } from "../hooks/useWalletAssistant";

export function AssistantPreferences({
  assistant: a,
}: {
  assistant: WalletAssistant;
}) {
  return (
    <details className="assistant-technical">
      <summary>Assistant details and voice preferences</summary>
      <p aria-label="Assistant provider">
        {a.provider === "nvidia-nemotron"
          ? "Reasoning: NVIDIA Nemotron"
          : a.provider === "demo-parser"
            ? "Reasoning: deterministic demo parser (NVIDIA was not used)"
            : a.provider === "context-resolver"
              ? "Reasoning: saved conversation context and backend facts (no model call this turn)"
              : "Reasoning: no provider result yet"}
        {a.speechProvider && ` · Last transcription: ${a.speechProvider}`}
        {a.playbackProvider && ` · Last playback: ${a.playbackProvider}`}
      </p>
      <label>
        <input
          type="checkbox"
          checked={a.reviewTranscript}
          disabled={a.state === "RECORDING" || a.busy}
          onChange={(e) => {
            a.setReviewTranscript(e.target.checked);
            localStorage.setItem(
              "wallet-review-transcript",
              e.target.checked ? "on" : "off",
            );
          }}
        />
        Review transcript before sending
      </label>
      <label>
        <input
          type="checkbox"
          checked={a.readReplies}
          onChange={(e) => {
            a.setReadReplies(e.target.checked);
            localStorage.setItem('wallet-read-replies', e.target.checked?'on':'off');
            if (!e.target.checked) a.stopVoice();
          }}
        />
        Read replies aloud in voice mode
      </label>
      <label>
        <input
          type="checkbox"
          checked={a.patientListening}
          disabled={a.state === "RECORDING"}
          onChange={(e) => {
            a.setPatientListening(e.target.checked);
            localStorage.setItem(
              "wallet-patient-listening",
              String(e.target.checked),
            );
          }}
        />
        Give me more time to pause between words (next recording)
      </label>
      <p>
        Recording starts only when you choose the microphone. Never speak your
        PIN or OTP.
      </p>
      <button
        className="text-button"
        disabled={a.busy || a.state === "RECORDING" || a.submitting}
        onClick={() => void a.newConversation()}
      >
        New chat
      </button>
    </details>
  );
}

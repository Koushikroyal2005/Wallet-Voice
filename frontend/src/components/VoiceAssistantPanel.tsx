import { useEffect, useRef, useState } from "react";
import {
  Bot,
  LoaderCircle,
  Mic,
  Send,
  Square,
  Volume2,
  VolumeX,
  RotateCcw,
} from "lucide-react";
import { PayPalCheckoutPanel } from "./PayPalCheckoutPanel";
import { WalletPinDialog } from "./WalletPinDialog";
import { WalletCompanion } from "./WalletCompanion";
import { money } from "../lib/formatting";
import { operationKey, finishOperation } from "../lib/api";

type Preview = {
  kind: string;
  amount?: number;
  total?: number;
  count?: number;
  changes?: Record<string, unknown>;
  payment_id?: string;
  merchant?: string;
  deadline?: string | null;
  payment_source?: string;
  verified?: boolean;
  requires_confirmation?: boolean;
  payment_ids?: string[];
};
type Turn = {
  conversation_id: string;
  response: string;
  action_preview?: Preview;
  data?: unknown;
};
type Message = { role: "user" | "assistant"; content: string };
type VoiceState =
  | "IDLE"
  | "RECORDING"
  | "UPLOADING"
  | "TRANSCRIBING"
  | "TRANSCRIPT_READY"
  | "THINKING"
  | "ACTION_PREVIEW"
  | "SPEAKING"
  | "COMPLETED"
  | "ERROR";
const stateCopy: Record<VoiceState, string> = {
  IDLE: "Ready when you are",
  RECORDING: "Listening",
  UPLOADING: "Preparing audio",
  TRANSCRIBING: "Transcribing",
  TRANSCRIPT_READY: "Transcript ready",
  THINKING: "Thinking",
  ACTION_PREVIEW: "Waiting for confirmation",
  SPEAKING: "Speaking",
  COMPLETED: "Response complete",
  ERROR: "Needs attention",
};

export function VoiceAssistantPanel({
  onConfirmed,
  mode = "chat",
  autoStart = false,
}: {
  onConfirmed: () => void;
  mode?: "chat" | "voice";
  autoStart?: boolean;
}) {
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const [preview, setPreview] = useState<Preview>();
  const [state, setState] = useState<VoiceState>("IDLE");
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [pinRequired, setPinRequired] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [dataRows, setDataRows] = useState<any[]>([]);
  const inFlight = useRef(false);
  const starting = useRef(false);
  const [patientListening, setPatientListening] = useState(() => localStorage.getItem("wallet-patient-listening") === "true");
  const [conversationId, setConversationId] = useState(
    () => localStorage.getItem("ai-wallet-conversation") || "",
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const recorder = useRef<MediaRecorder>();
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<number>();
  const audio = useRef<HTMLAudioElement>();
  const mounted = useRef(true);
  const streamRef = useRef<MediaStream>();
  const contextRef = useRef<AudioContext>();
  const silenceTimer = useRef<number>();
  const audioUrl = useRef<string>();
  const playbackGeneration = useRef(0);
  const historyGeneration = useRef(0);
  useEffect(
    () => () => {
      mounted.current = false;
      playbackGeneration.current++;
      if (timer.current) window.clearInterval(timer.current);
      window.clearInterval(silenceTimer.current);
      if (recorder.current) { recorder.current.onstop = null; if (recorder.current.state === "recording") recorder.current.stop(); }
      streamRef.current?.getTracks().forEach(track => track.stop());
      void contextRef.current?.close();
      audio.current?.pause();
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
      window.speechSynthesis?.cancel();
    },
    [],
  );
  useEffect(() => {
    if (!conversationId) return;
    const generation = historyGeneration.current;
    fetch(`/api/assistant/conversations/${conversationId}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => { if (data && mounted.current && historyGeneration.current === generation) setMessages(items => items.length ? items : data.messages || []); })
      .catch(() => undefined);
  }, []);
  const speak = async (value: string) => {
    const generation = ++playbackGeneration.current;
    try {
      const response = await fetch("/api/voice/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: value }),
      });
      if (!response.ok) throw new Error();
      const blob = await response.blob();
      if (!mounted.current || generation !== playbackGeneration.current) return;
      const url = URL.createObjectURL(blob);
      audioUrl.current = url;
      audio.current = new Audio(url);
      audio.current.onended = () => {
        URL.revokeObjectURL(url);
        setState("COMPLETED");
      };
      setState("SPEAKING");
      await audio.current.play();
    } catch {
      if (!mounted.current || generation !== playbackGeneration.current) return;
      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(value);
        utterance.onend = () => mounted.current && setState("COMPLETED");
        utterance.onerror = () => mounted.current && setState("COMPLETED");
        setState("SPEAKING");
        window.speechSynthesis.speak(utterance);
      }
    }
  };
  const ask = async (value = text) => {
    if (!value.trim() || inFlight.current || recorder.current?.state === "recording") return;
    inFlight.current = true;
    setPreview(undefined);
    setPinRequired(false);
    setDataRows([]);
    stopVoice();
    setState("THINKING");
    setError("");
    try {
      const response = await fetch("/api/assistant/turn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: value,
          conversation_id: conversationId || undefined,
        }),
      });
      const data: Turn = await response.json();
      if (!mounted.current) return;
      if (!response.ok) throw new Error(JSON.stringify(data));
      if (data.conversation_id) {
        setConversationId(data.conversation_id);
        localStorage.setItem("ai-wallet-conversation", data.conversation_id);
      }
      setReply(data.response);
      setMessages((items) => [
        ...items,
        { role: "user", content: value },
        { role: "assistant", content: data.response },
      ]);
      setPreview(data.action_preview);
      setDataRows(Array.isArray(data.data) ? data.data : []);
      setText("");
      onConfirmed();
      setState(data.action_preview ? "ACTION_PREVIEW" : "COMPLETED");
      if (mode === "voice") void speak(data.response);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Assistant request failed",
      );
      setState("ERROR");
    } finally {
      inFlight.current = false;
    }
  };
  const newConversation = async () => {
    historyGeneration.current++;
    stopVoice();
    if (conversationId)
      await fetch(`/api/assistant/conversations/${conversationId}`, {
        method: "DELETE",
      }).catch(() => undefined);
    localStorage.removeItem("ai-wallet-conversation");
    setConversationId("");
    setMessages([]);
    setReply("");
    setPreview(undefined);
    setText("");
    setState("IDLE");
  };
  const start = async () => {
    if (starting.current || inFlight.current || recorder.current?.state === "recording" || state === "TRANSCRIBING" || state === "UPLOADING") return;
    starting.current = true;
    setPreview(undefined);
    setPinRequired(false);
    stopVoice();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current) { stream.getTracks().forEach(track => track.stop()); return; }
      streamRef.current = stream;
      const mime = [
        "audio/webm;codecs=opus",
        "audio/ogg;codecs=opus",
        "audio/wav",
      ].find((value) => MediaRecorder.isTypeSupported(value));
      chunks.current = [];
      const nextRecorder = new MediaRecorder(
        stream,
        mime ? { mimeType: mime } : undefined,
      );
      recorder.current = nextRecorder;
      nextRecorder.ondataavailable = (event) =>
        event.data.size && chunks.current.push(event.data);
      nextRecorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        window.clearInterval(timer.current);
        window.clearInterval(silenceTimer.current);
        void contextRef.current?.close();
        contextRef.current = undefined;
        if (!mounted.current) return;
        setState("UPLOADING");
        try {
          const blob = new Blob(chunks.current, {
            type: nextRecorder.mimeType || "audio/webm",
          });
          const form = new FormData();
          form.append("audio", blob, "wallet-command");
          setState("TRANSCRIBING");
          const response = await fetch("/api/voice/transcribe", {
            method: "POST",
            body: form,
          });
          const data = await response.json();
          if (!mounted.current) return;
          if (!response.ok)
            throw new Error(data.detail || "Transcription failed");
          setText(data.transcript);
          setState("TRANSCRIPT_READY");
          if (mode === "voice" && data.transcript?.trim()) await ask(data.transcript);
        } catch (cause) {
          setError(
            cause instanceof Error ? cause.message : "Recording upload failed",
          );
          setState("ERROR");
        }
      };
      nextRecorder.start();
      if (mode === "voice") {
        const context = new AudioContext();
        contextRef.current = context;
        await context.resume();
        const analyser = context.createAnalyser();
        analyser.fftSize = 2048;
        context.createMediaStreamSource(stream).connect(analyser);
        const samples = new Float32Array(analyser.fftSize);
        const began = performance.now();
        let lastSpeech = began;
        let voicedFrames = 0;
        silenceTimer.current = window.setInterval(() => {
          analyser.getFloatTimeDomainData(samples);
          const rms = Math.sqrt(samples.reduce((sum, sample) => sum + sample * sample, 0) / samples.length);
          const now = performance.now();
          if (rms > 0.018) { voicedFrames++; lastSpeech = now; }
          if (voicedFrames >= 3 && now - lastSpeech > (patientListening ? 2600 : 1600)) stop();
          else if (!voicedFrames && now - began > 10000) {
            nextRecorder.onstop = null;
            stop();
            stream.getTracks().forEach(track => track.stop());
            void context.close();
            contextRef.current = undefined;
            setState("IDLE");
            setError("I didn’t hear anything. Tap the microphone to try again, or switch to chat.");
          }
        }, 100);
      }
      setSeconds(0);
      timer.current = window.setInterval(
        () => setSeconds((value) => value + 1),
        1000,
      );
      setState("RECORDING");
    } catch {
      if (recorder.current?.state === "recording") { recorder.current.onstop = null; recorder.current.stop(); }
      streamRef.current?.getTracks().forEach(track => track.stop());
      window.clearInterval(silenceTimer.current);
      void contextRef.current?.close();
      contextRef.current = undefined;
      setError(
        "Microphone permission was not granted. Type your request instead.",
      );
      setState("ERROR");
    } finally {
      starting.current = false;
    }
  };
  const stop = () => {
    window.clearInterval(silenceTimer.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
    if (timer.current) window.clearInterval(timer.current);
  };
  useEffect(() => {
    if (seconds >= 60 && state === "RECORDING") stop();
  }, [seconds, state]);
  const stopVoice = () => {
    playbackGeneration.current++;
    audio.current?.pause();
    if (audioUrl.current) { URL.revokeObjectURL(audioUrl.current); audioUrl.current = undefined; }
    window.speechSynthesis?.cancel();
    setState("COMPLETED");
  };
  useEffect(() => { if (autoStart) void start(); }, []);
  const confirm = async () => {
    if (!preview || inFlight.current) return;
    if (
      preview.kind === "prepare_topup" ||
      preview.kind === "prepare_withdrawal"
    ) {
      setPinRequired(true);
      return;
    }
    inFlight.current = true;
    setSubmitting(true);
    try {
      let path = "",
        body: any = {
          idempotency_key: operationKey(
            `voice:${preview.kind}:${preview.payment_id || preview.amount || "batch"}`,
          ),
        };
      if (preview.kind === "autopay") {
        path = "/api/autopay/settings";
        body = preview.changes;
      } else if (preview.kind === "batch") {
        path = "/api/payments/batch/confirm";
        body.payment_ids = preview.payment_ids;
      } else if (preview.kind === "hold" && preview.payment_id) {
        path = `/api/payments/${preview.payment_id}/hold`;
      } else if (preview.kind === "payment" && preview.payment_id) {
        path = `/api/payments/${preview.payment_id}/pay`;
        body.confirm_unknown_merchant = !preview.verified;
      } else return;
      const response = await fetch(path, {
        method: preview.kind === "autopay" ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(await response.text());
      const outcome = await response.json();
      if (outcome.status === "FAILED") {
        finishOperation(
          `voice:${preview.kind}:${preview.payment_id || preview.amount || "batch"}`,
        );
        onConfirmed();
        throw new Error(
          outcome.failure_reason || "Payment failed. Your funds were released.",
        );
      }
      setReply(preview.kind === "hold"
        ? "This request will wait for you. No payment was made."
        : preview.kind === "autopay"
          ? "Your automatic request payment settings were updated."
          : preview.kind === "batch"
            ? "Your batch was submitted. Check Payments for each payment’s result."
            : outcome.status === "SUCCEEDED"
              ? `${preview.merchant || "The business"} was paid ${money(preview.amount)} from your demo wallet.`
              : "Your payment is still being checked. Check Payments for its status before trying again.");
      setPreview(undefined);
      setState("COMPLETED");
      onConfirmed();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Confirmation failed");
      setState("ERROR");
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  };
  const previewText =
    preview?.kind === "payment"
      ? `${preview.merchant} · ${money(preview.amount)} · ${preview.payment_source === "PAYPAL_SANDBOX" ? "PayPal Sandbox" : "AI Wallet balance"}${preview.deadline ? ` · ${new Date(preview.deadline).toLocaleString()}` : ""}`
      : preview?.kind === "batch"
        ? `${preview.count || 0} eligible payments · ${money(preview.total)} total`
        : preview
          ? `${preview.kind.replace("prepare_", "")} · ${money(preview.amount)}`
          : "";
  const busy = ["UPLOADING", "TRANSCRIBING", "THINKING"].includes(state);
  return (
    <section
      className={`voice-panel state-${state.toLowerCase()}`}
      aria-label="Voice assistant"
    >
      <div className="voice-heading">
        <div className="assistant-mark">
          <Bot size={20} />
        </div>
        <div>
          <span className="eyebrow">YOUR WALLET ASSISTANT</span>
          <h3>Ask AI Wallet</h3>
          <p>
            Find a payment, understand urgency, or prepare an action for your
            approval.
          </p>
        </div>
        <span className="voice-state">
          {busy && <LoaderCircle size={14} />}
          <i />
          {stateCopy[state]}
        </span>
        <button
          className="text-button conversation-reset"
          onClick={newConversation}
          disabled={busy || submitting || state === "RECORDING"}
        >
          <RotateCcw size={14} /> New chat
        </button>
      </div>
      {mode === "voice" && <><div className={`voice-aura ${state === "RECORDING" || state === "SPEAKING" ? "active" : ""}`} aria-hidden="true"><WalletCompanion/><i/><i/></div><label className="assistant-privacy"><input type="checkbox" checked={patientListening} disabled={state === "RECORDING"} onChange={event => { setPatientListening(event.target.checked); localStorage.setItem("wallet-patient-listening",String(event.target.checked)); }}/> Give me more time to pause between words (next recording)</label></>}
      {messages.length > 0 && (
        <div
          className="conversation-timeline"
          aria-label="Conversation history"
        >
          {messages.slice(-6).map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`conversation-message ${message.role}`}
            >
              <span>{message.role === "user" ? "You" : "AI Wallet"}</span>
              <p>{message.content}</p>
            </div>
          ))}
        </div>
      )}
      <div className="voice-workspace">
        <button
          className={`mic-action ${state === "RECORDING" ? "recording" : ""}`}
          onClick={state === "RECORDING" ? stop : start}
          disabled={busy || submitting}
          aria-label={
            state === "RECORDING" ? "Stop recording" : "Start recording"
          }
        >
          {state === "RECORDING" ? <Square size={22} /> : <Mic size={24} />}
          <span>{state === "RECORDING" ? `${seconds}s` : "Speak"}</span>
        </button>
        <div className="voice-compose">
          <label htmlFor="wallet-command">
            Ask about your wallet or payments
          </label>
          <div>
            <input
              id="wallet-command"
              disabled={state === "RECORDING" || busy}
              value={text}
              onChange={(event) => {
                setText(event.target.value);
                setPreview(undefined);
                setPinRequired(false);
                if (state === "ACTION_PREVIEW") setState("IDLE");
              }}
              onKeyDown={(event) => event.key === "Enter" && void ask()}
              placeholder="Which payment is urgent?"
            />
            <button
              onClick={() => void ask()}
              disabled={busy || state === "RECORDING" || !text.trim()}
              aria-label="Send request"
            >
              <Send size={17} />
            </button>
          </div>
          <small>Voice input never authorizes a financial action.</small>
        </div>
      </div>
      {dataRows.length > 0 && (
        <div className="assistant-data">
          {dataRows.slice(0, 8).map((item, index) => (
            <div key={item.id || index}>
              <span>{item.merchant || item.kind || "Payment"}</span>
              <strong>
                {typeof item.amount === "number"
                  ? money(item.amount)
                  : item.status}
              </strong>
            </div>
          ))}
        </div>
      )}
      {(error || reply) && (
        <div className={`assistant-message ${error ? "error" : ""}`}>
          <span>{error ? "Issue" : "AI Wallet"}</span>
          <p>{error || reply}</p>
          {state === "SPEAKING" && (
            <button className="text-button" onClick={stopVoice}>
              <VolumeX size={14} /> Stop audio
            </button>
          )}
          {reply && state !== "SPEAKING" && (
            <button className="text-button" onClick={() => void speak(reply)} disabled={state === "RECORDING" || busy}>
              <Volume2 size={14} /> Read aloud
            </button>
          )}
        </div>
      )}
      {preview?.requires_confirmation && (
        <div className="voice-preview">
          <div>
            <span className="eyebrow">CONFIRMATION REQUIRED</span>
            <b>{previewText}</b>
            <p>Review this preview. The assistant cannot approve it for you.</p>
          </div>
          <div className="preview-actions">
            {preview.kind === "payment" &&
            preview.payment_source === "PAYPAL_SANDBOX" &&
            preview.payment_id ? (
              <PayPalCheckoutPanel
                paymentId={preview.payment_id}
                amount={preview.amount || 0}
                onComplete={() => {
                  setReply(
                    "PayPal capture completed and was confirmed by the backend.",
                  );
                  setPreview(undefined);
                  onConfirmed();
                }}
              />
            ) : (
              <button disabled={submitting || busy} onClick={confirm}>
                {submitting ? "Processing…" : "Confirm action"}
              </button>
            )}
            <button
              className="secondary"
              onClick={() => {
                setPreview(undefined);
                setState("COMPLETED");
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      {preview &&
        pinRequired &&
        (preview.kind === "prepare_topup" ||
          preview.kind === "prepare_withdrawal") && (
          <WalletPinDialog
            action={preview.kind === "prepare_topup" ? "TOPUP" : "WITHDRAWAL"}
            amount={preview.amount || 0}
            title={
              preview.kind === "prepare_topup"
                ? "Authorize voice-prepared top-up"
                : "Authorize voice-prepared withdrawal"
            }
            onClose={() => setPinRequired(false)}
            onApproved={async (approvalToken) => {
              const path =
                preview.kind === "prepare_topup"
                  ? "/api/bank/topups"
                  : "/api/bank/withdrawals";
              const response = await fetch(path, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  amount: preview.amount,
                  idempotency_key: operationKey(
                    `voice:${preview.kind}:${preview.amount}`,
                  ),
                  approval_token: approvalToken,
                }),
              });
              if (!response.ok) throw new Error(await response.text());
              finishOperation(`voice:${preview.kind}:${preview.amount}`);
              setPinRequired(false);
              setPreview(undefined);
              setReply(
                "Authorized. The backend completed the exact wallet transfer you approved.",
              );
              setState("COMPLETED");
              onConfirmed();
            }}
          />
        )}
    </section>
  );
}

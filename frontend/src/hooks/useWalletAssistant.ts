import { useEffect, useRef, useState } from "react";
import { money } from "../lib/formatting";
import { api, operationKey, finishOperation } from "../lib/api";

type Preview = {
  kind: string;
  amount?: number;
  total?: number;
  count?: number;
  changes?: Record<string, unknown>;
  payment_id?: string;
  resource_id?: string;
  merchant?: string;
  deadline?: string | null;
  payment_source?: string;
  verified?: boolean;
  requires_confirmation?: boolean;
  payment_ids?: string[];
  batch_id?: string;
  intent_id?: string;
  recipient_name?: string;
  recipient_handle?: string;
  version?: number;
  source?: string;
};
type Turn = {
  conversation_id: string;
  response: string;
  action_preview?: Preview;
  data?: unknown;
  provider?: string;
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
  THINKING: "Understanding your request",
  ACTION_PREVIEW: "Review and approve securely",
  SPEAKING: "Speaking",
  COMPLETED: "Response ready",
  ERROR: "Needs attention",
};

export function useWalletAssistant({
  onConfirmed,
  mode = "chat",
  autoStart = false,
  active = false,
}: {
  onConfirmed: () => void;
  mode?: "chat" | "voice";
  autoStart?: boolean;
  active?: boolean;
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
  const [resultData, setResultData] = useState<any>();
  const inFlight = useRef(false);
  const starting = useRef(false);
  const [heard, setHeard] = useState("");
  const [level, setLevel] = useState(0);
  const [provider, setProvider] = useState("");
  const [speechProvider, setSpeechProvider] = useState("");
  const [playbackProvider, setPlaybackProvider] = useState("");
  const [reviewTranscript, setReviewTranscript] = useState(
    () => localStorage.getItem("wallet-review-transcript") !== "off",
  );
  const [readReplies, setReadReplies] = useState(()=>localStorage.getItem('wallet-read-replies')==='on');
  const readRepliesRef = useRef(readReplies);
  readRepliesRef.current = readReplies;
  const [browserSpeechAllowed, setBrowserSpeechAllowed] = useState(false);
  const [recognizedMerchant, setRecognizedMerchant] = useState(false);
  const requestGeneration = useRef(0);
  const turnRequest = useRef<AbortController>();
  const transcriptionRequest = useRef<AbortController>();
  const synthesisRequest = useRef<AbortController>();
  const pendingTurn = useRef<{ text: string; id: string }>();
  const previewRef = useRef(preview);
  previewRef.current = preview;
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const [patientListening, setPatientListening] = useState(
    () => localStorage.getItem("wallet-patient-listening") === "true",
  );
  const [conversationId, setConversationId] = useState(() => {
    const id =
      localStorage.getItem("ai-wallet-conversation") || crypto.randomUUID();
    localStorage.setItem("ai-wallet-conversation", id);
    return id;
  });
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
  useEffect(() => {
    let disposed = false;
    void api("/api/assistant/status")
      .then((result) => {
        if (!disposed)
          setBrowserSpeechAllowed(result.browser_tts_fallback === true);
      })
      .catch(() => undefined);
    return () => {
      disposed = true;
    };
  }, []);
  useEffect(
    () => () => {
      mounted.current = false;
      requestGeneration.current++;
      turnRequest.current?.abort();
      transcriptionRequest.current?.abort();
      synthesisRequest.current?.abort();
      playbackGeneration.current++;
      if (timer.current) window.clearInterval(timer.current);
      window.clearInterval(silenceTimer.current);
      if (recorder.current) {
        recorder.current.onstop = null;
        if (recorder.current.state === "recording") recorder.current.stop();
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
      void contextRef.current?.close().catch(() => undefined);
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
      .then((data) => {
        if (data && mounted.current && historyGeneration.current === generation)
          setMessages((items) => (items.length ? items : data.messages || []));
      })
      .catch(() => undefined);
  }, []);
  const speak = async (value: string) => {
    stopVoice();
    const generation = ++playbackGeneration.current;
    const controller = new AbortController();
    synthesisRequest.current = controller;
    try {
      const response = await fetch("/api/voice/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: value }),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error();
      const blob = await response.blob();
      if (!mounted.current || generation !== playbackGeneration.current) return;
      const url = URL.createObjectURL(blob);
      audioUrl.current = url;
      audio.current = new Audio(url);
      audio.current.onended = () => {
        URL.revokeObjectURL(url);
        if (mounted.current && generation === playbackGeneration.current)
          setState(
            previewRef.current?.requires_confirmation
              ? "ACTION_PREVIEW"
              : "COMPLETED",
          );
      };
      audio.current.onerror = () => {
        if (mounted.current && generation === playbackGeneration.current) {
          setError(
            "Audio playback failed. Your written response is still available; try Read aloud again.",
          );
          setState(
            previewRef.current?.requires_confirmation
              ? "ACTION_PREVIEW"
              : "COMPLETED",
          );
        }
      };
      setPlaybackProvider(
        response.headers.get("X-Voice-Provider") === "nvidia-magpie"
          ? "NVIDIA Magpie"
          : "Backend audio",
      );
      setState("SPEAKING");
      await audio.current.play();
    } catch {
      if (!mounted.current || generation !== playbackGeneration.current) return;
      if (browserSpeechAllowed && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(value);
        utterance.onend = () =>
          mounted.current &&
          generation === playbackGeneration.current &&
          setState(
            previewRef.current?.requires_confirmation
              ? "ACTION_PREVIEW"
              : "COMPLETED",
          );
        utterance.onerror = utterance.onend;
        setPlaybackProvider("Browser speech fallback");
        setState("SPEAKING");
        window.speechSynthesis.speak(utterance);
      } else {
        setError("Audio is unavailable. Please read the written response.");
        setState(
          previewRef.current?.requires_confirmation
            ? "ACTION_PREVIEW"
            : "COMPLETED",
        );
      }
    }
  };
  const ask = async (value = text) => {
    if (
      !value.trim() ||
      inFlight.current ||
      recorder.current?.state === "recording"
    )
      return;
    inFlight.current = true;
    const generation = requestGeneration.current;
    const controller = new AbortController();
    turnRequest.current = controller;
    if (pendingTurn.current?.text !== value)
      pendingTurn.current = { text: value, id: crypto.randomUUID() };
    setPreview(undefined);
    setPinRequired(false);
    setRecognizedMerchant(false);
    setDataRows([]);
    stopVoice();
    setState("THINKING");
    setError("");
    setProvider("");
    setReply("");
    try {
      const data = await api<Turn>("/api/assistant/turn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: value,
          conversation_id: conversationId || undefined,
          request_id: pendingTurn.current!.id,
        }),
        signal: controller.signal,
      });
      if (!mounted.current || generation !== requestGeneration.current) return;
      pendingTurn.current = undefined;
      setProvider(data.provider || "unreported");
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
      setResultData(data.data);
      setText("");
      onConfirmed();
      setState(data.action_preview ? "ACTION_PREVIEW" : "COMPLETED");
      if (modeRef.current === "voice" && readRepliesRef.current)
        void speak(data.response);
    } catch (cause) {
      if (
        !mounted.current ||
        generation !== requestGeneration.current ||
        controller.signal.aborted
      )
        return;
      setError(
        cause instanceof Error ? cause.message : "Assistant request failed",
      );
      setState("ERROR");
    } finally {
      if (generation === requestGeneration.current) inFlight.current = false;
    }
  };
  const newConversation = async () => {
    historyGeneration.current++;
    requestGeneration.current++;
    turnRequest.current?.abort();
    transcriptionRequest.current?.abort();
    pendingTurn.current = undefined;
    inFlight.current = false;
    stopVoice();
    const id = crypto.randomUUID();
    localStorage.setItem("ai-wallet-conversation", id);
    setConversationId(id);
    setMessages([]);
    setDataRows([]);
    setResultData(undefined);
    setPinRequired(false);
    setRecognizedMerchant(false);
    setReply("");
    setPreview(undefined);
    setText("");
    setHeard("");
    setProvider("");
    setSpeechProvider("");
    setPlaybackProvider("");
    setError("");
    setState("IDLE");
  };
  const deleteConversation = async () => {
    if (!conversationId || inFlight.current) return;
    inFlight.current = true;
    setSubmitting(true);
    stopVoice();
    try {
      const response = await fetch(`/api/assistant/conversations/${conversationId}`, { method: "DELETE" });
      if (!response.ok) throw new Error(response.status === 401 ? "Session expired. Sign in before deleting this conversation." : "Conversation was not deleted. Please retry.");
      await newConversation();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Conversation was not deleted.");
      setState("ERROR");
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  };
  const start = async () => {
    if (
      starting.current ||
      inFlight.current ||
      recorder.current?.state === "recording" ||
      state === "TRANSCRIBING" ||
      state === "UPLOADING"
    )
      return;
    starting.current = true;
    const generation = requestGeneration.current;
    const requestedMode = modeRef.current;
    setError("");
    setSpeechProvider("");
    setPinRequired(false);
    stopVoice();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (
        !mounted.current ||
        generation !== requestGeneration.current ||
        requestedMode !== modeRef.current
      ) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
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
        void contextRef.current?.close().catch(() => undefined);
        contextRef.current = undefined;
        if (!mounted.current || generation !== requestGeneration.current)
          return;
        setLevel(0);
        setState("UPLOADING");
        try {
          const blob = new Blob(chunks.current, {
            type: nextRecorder.mimeType || "audio/webm",
          });
          const form = new FormData();
          form.append("audio", blob, "wallet-command");
          setState("TRANSCRIBING");
          const controller = new AbortController();
          transcriptionRequest.current = controller;
          const response = await fetch("/api/voice/transcribe", {
            method: "POST",
            body: form,
            signal: controller.signal,
          });
          const data = await response.json();
          if (!mounted.current || generation !== requestGeneration.current)
            return;
          if (response.status === 401)
            window.dispatchEvent(new Event("wallet-session-expired"));
          if (!response.ok)
            throw new Error(data.detail || "Transcription failed");
          if (typeof data.transcript !== "string" || !data.transcript.trim())
            throw new Error(
              "I did not hear a clear request. Please try again or type it.",
            );
          setText(data.transcript);
          setHeard(data.transcript || "");
          setSpeechProvider(
            data.provider === "nvidia-riva-whisper-large-v3"
              ? "NVIDIA Whisper"
              : "Unreported transcription provider",
          );
          setState("TRANSCRIPT_READY");
          if (
            modeRef.current === "voice" &&
            !reviewTranscript &&
            data.transcript?.trim()
          )
            await ask(data.transcript);
        } catch (cause) {
          if (!mounted.current || generation !== requestGeneration.current)
            return;
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
        let noiseFloor = 0.004;
        silenceTimer.current = window.setInterval(() => {
          analyser.getFloatTimeDomainData(samples);
          const rms = Math.sqrt(
            samples.reduce((sum, sample) => sum + sample * sample, 0) /
              samples.length,
          );
          setLevel(Math.min(1, rms * 15));
          const now = performance.now();
          const threshold = Math.max(0.01, Math.min(0.05, noiseFloor * 2.8));
          if (rms < threshold) noiseFloor = noiseFloor * 0.94 + rms * 0.06;
          if (rms > threshold) {
            voicedFrames++;
            lastSpeech = now;
          }
          if (
            voicedFrames >= 3 &&
            now - lastSpeech > (patientListening ? 2600 : 1600)
          )
            stop();
          else if (!voicedFrames && now - began > 10000) {
            nextRecorder.onstop = null;
            stop();
            stream.getTracks().forEach((track) => track.stop());
            void context.close().catch(() => undefined);
            contextRef.current = undefined;
            setState("IDLE");
            setError(
              "I didn’t hear anything. Tap the microphone to try again, or switch to chat.",
            );
          }
        }, 100);
      }
      setSeconds(0);
      timer.current = window.setInterval(
        () => setSeconds((value) => value + 1),
        1000,
      );
      setState("RECORDING");
    } catch (cause) {
      if (recorder.current?.state === "recording") {
        recorder.current.onstop = null;
        recorder.current.stop();
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
      window.clearInterval(silenceTimer.current);
      void contextRef.current?.close().catch(() => undefined);
      contextRef.current = undefined;
      if (!mounted.current || generation !== requestGeneration.current) return;
      setError(
        cause instanceof DOMException && cause.name === "NotAllowedError"
          ? "Microphone permission was not granted. Type your request instead."
          : "Recording could not start. Check your microphone and browser audio support, or type your request.",
      );
      setState("ERROR");
    } finally {
      starting.current = false;
    }
  };
  const stop = () => {
    setLevel(0);
    window.clearInterval(silenceTimer.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
    if (timer.current) window.clearInterval(timer.current);
  };
  useEffect(() => {
    if (seconds >= 60 && state === "RECORDING") stop();
  }, [seconds, state]);
  const stopVoice = () => {
    playbackGeneration.current++;
    synthesisRequest.current?.abort();
    audio.current?.pause();
    if (audioUrl.current) {
      URL.revokeObjectURL(audioUrl.current);
      audioUrl.current = undefined;
    }
    window.speechSynthesis?.cancel();
    setState(
      previewRef.current?.requires_confirmation
        ? "ACTION_PREVIEW"
        : "COMPLETED",
    );
  };
  useEffect(()=>{
    const update=()=>{
      setReviewTranscript(localStorage.getItem('wallet-review-transcript')!=='off');
      const read=localStorage.getItem('wallet-read-replies')==='on';
      setReadReplies(read);
      setPatientListening(localStorage.getItem('wallet-patient-listening')==='true');
      if(!read)stopVoice();
    };
    window.addEventListener('wallet-voice-preferences-changed',update);
    return()=>window.removeEventListener('wallet-voice-preferences-changed',update);
  },[]);
  useEffect(() => {
    requestGeneration.current++;
    turnRequest.current?.abort();
    transcriptionRequest.current?.abort();
    inFlight.current = false;
    if (active && autoStart) void start();
    else {
      if (recorder.current?.state === "recording") {
        recorder.current.onstop = null;
        recorder.current.stop();
      }
      window.clearInterval(timer.current);
      window.clearInterval(silenceTimer.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
      void contextRef.current?.close().catch(() => undefined);
      contextRef.current = undefined;
      setLevel(0);
      stopVoice();
    }
  }, [mode, active]);
  const confirm = async () => {
    if (!preview || inFlight.current) return;
    if (preview.kind === "payment" && !preview.verified && !recognizedMerchant)
      return;
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
        body.confirm_unknown_merchant = recognizedMerchant;
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
      setReply(
        preview.kind === "hold"
          ? "This request will wait for you. No payment was made."
          : preview.kind === "autopay"
            ? "Your automatic request payment settings were updated."
            : preview.kind === "batch"
              ? "Your batch was submitted. Check Payments for each payment’s result."
              : outcome.status === "SUCCEEDED"
                ? `${preview.merchant || "The business"} was paid ${money(preview.amount)} from your demo wallet.`
                : "Your payment is still being checked. Check Payments for its status before trying again.",
      );
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
  return {
    text,
    setText,
    reply,
    setReply,
    preview,
    setPreview,
    state,
    setState,
    error,
    setError,
    seconds,
    pinRequired,
    setPinRequired,
    submitting,
    dataRows,
    resultData,
    heard,
    level,
    provider,
    speechProvider,
    playbackProvider,
    reviewTranscript,
    setReviewTranscript,
    speak,
    readReplies,
    setReadReplies,
    patientListening,
    setPatientListening,
    messages,
    busy,
    ask,
    start,
    stop,
    stopVoice,
    newConversation,
    deleteConversation,
    confirm,
    previewText,
    recognizedMerchant,
    setRecognizedMerchant,
    retry: () => pendingTurn.current && ask(pendingTurn.current.text),
    canRetry: !!pendingTurn.current,
  };
}
export type WalletAssistant = ReturnType<typeof useWalletAssistant>;
export { stateCopy };

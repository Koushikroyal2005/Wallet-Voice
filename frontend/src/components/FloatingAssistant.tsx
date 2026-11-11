import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MessageCircle, Mic, X } from "lucide-react";
import { AssistantOrb } from "./AssistantOrb";
import { VoiceAssistantPanel } from "./VoiceAssistantPanel";
import { useWalletAssistant } from "../hooks/useWalletAssistant";

export function FloatingAssistant({
  requested,
  onClose,
  onConfirmed,
}: {
  requested: boolean;
  onClose: () => void;
  onConfirmed: () => void;
}) {
  const [mode, setMode] = useState<"chat" | "voice">("chat");
  const [active, setActive] = useState(false);
  const previousFocus = useRef<HTMLElement | null>(null);
  const surface = useRef<HTMLElement>(null);
  const closeHandler = useRef(onClose);
  closeHandler.current = onClose;
  const assistant = useWalletAssistant({
    mode,
    active,
    autoStart: mode === "voice",
    onConfirmed,
  });
  useEffect(() => {
    const viewport = window.visualViewport;
    const update = () => {
      const height = viewport?.height || window.innerHeight;
      document.documentElement.style.setProperty(
        "--assistant-viewport",
        `${height}px`,
      );
      document.documentElement.style.setProperty(
        "--assistant-keyboard",
        `${Math.max(0, window.innerHeight - height - (viewport?.offsetTop || 0))}px`,
      );
    };
    update();
    viewport?.addEventListener("resize", update);
    viewport?.addEventListener("scroll", update);
    window.addEventListener("resize", update);
    return () => {
      viewport?.removeEventListener("resize", update);
      viewport?.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
      document.documentElement.style.removeProperty("--assistant-viewport");
      document.documentElement.style.removeProperty("--assistant-keyboard");
    };
  }, []);
  const close = useCallback(() => {
    setActive(false);
    closeHandler.current();
    previousFocus.current?.focus();
  }, []);
  const open = useCallback((next: "chat" | "voice") => {
    previousFocus.current = document.activeElement as HTMLElement;
    setMode(next);
    setActive(true);
  }, []);
  useEffect(() => {
    const launch = (e: Event) =>
      open((e as CustomEvent).detail === "voice" ? "voice" : "chat");
    window.addEventListener("wallet-assistant-open", launch);
    return () => window.removeEventListener("wallet-assistant-open", launch);
  }, [open]);
  useEffect(() => {
    if (requested) open("chat");
  }, [requested, open]);
  useEffect(() => {
    if (!active) return;
    surface.current?.focus({ preventScroll: true });
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !document.querySelector("dialog[open]")) {
        e.preventDefault();
        close();
      }
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [active, close]);
  useEffect(() => {
    if (
      !active ||
      mode !== "voice" ||
      assistant.state !== "COMPLETED" ||
      !assistant.reply ||
      assistant.reply.length > 340 ||
      assistant.preview ||
      assistant.error ||
      assistant.text ||
      assistant.dataRows.length > 3
    )
      return;
    const timeout = window.setTimeout(() => {
      const focused = document.activeElement;
      const editing =
        surface.current?.contains(focused) &&
        ["INPUT", "TEXTAREA", "SELECT"].includes(focused?.tagName || "");
      if (!editing && !surface.current?.querySelector("details[open]")) close();
    }, 14000);
    return () => window.clearTimeout(timeout);
  }, [
    active,
    mode,
    assistant.state,
    assistant.reply,
    assistant.preview,
    assistant.error,
    assistant.text,
    assistant.dataRows.length,
    close,
  ]);
  return createPortal(
    <div
      className={`guardian-assistant-layer ${active ? "is-open" : ""} mode-${mode}`}
    >
      {active && (
        <>
          <div className="assistant-context-backdrop" aria-hidden="true" />
          <section
            ref={surface}
            tabIndex={-1}
            className={`assistant-surface ${assistant.preview ? "has-action" : ""} ${mode === "voice" && !assistant.preview && !assistant.error && !assistant.text && assistant.state !== "TRANSCRIPT_READY" && assistant.dataRows.length <= 3 ? "is-compact" : ""}`}
            aria-label="Wallet conversation"
          >
            <header className="assistant-surface-header">
              <div>
                <span className="assistant-brand-dot" />
                Wallet-Voice{" "}
                <small>{mode === "voice" ? "Voice" : "Conversation"}</small>
              </div>
              <button
                className="icon-button"
                aria-label="Close conversation"
                onClick={close}
              >
                <X size={19} />
              </button>
            </header>
            <div className="assistant-mode-switch">
              <button
                aria-pressed={mode === "chat"}
                onClick={() => setMode("chat")}
              >
                <MessageCircle size={15} />
                Chat
              </button>
              <button
                aria-pressed={mode === "voice"}
                onClick={() => setMode("voice")}
              >
                <Mic size={15} />
                Voice
              </button>
            </div>
            <VoiceAssistantPanel
              assistant={assistant}
              mode={mode}
              onChanged={onConfirmed}
            />
          </section>
        </>
      )}
      <div className="assistant-launcher">
        <AssistantOrb
          state={active ? assistant.state : "IDLE"}
          level={assistant.level}
          label={active ? "Close wallet assistant" : "Open wallet assistant"}
          onClick={() => (active ? close() : open("voice"))}
        />
      </div>
    </div>,
    document.body,
  );
}

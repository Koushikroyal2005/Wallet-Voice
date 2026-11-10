import { useEffect, useState } from "react";
import { MessageCircle, Mic } from "lucide-react";
import { WalletCompanion } from "./WalletCompanion";
import { Dialog } from "./Dialog";
import { VoiceAssistantPanel } from "./VoiceAssistantPanel";

export function FloatingAssistant({ requested, onClose, onConfirmed }: { requested: boolean; onClose: () => void; onConfirmed: () => void }) {
  const [mode, setMode] = useState<"chat" | "voice" | null>(null);
  const open = (next: "chat" | "voice") => setMode(next);
  useEffect(() => {
    const launch = (event: Event) => open((event as CustomEvent).detail === "voice" ? "voice" : "chat");
    window.addEventListener("wallet-assistant-open", launch);
    return () => window.removeEventListener("wallet-assistant-open", launch);
  }, []);
  useEffect(() => { if (requested) open("chat"); }, [requested]);
  return <>
    <div className="assistant-dock">
      <div className="assistant-dock-actions">
        <button onClick={() => open("voice")}><Mic size={16}/>Talk</button>
        <button onClick={() => open("chat")}><MessageCircle size={16}/>Type</button>
      </div>
      <button className="assistant-orb" aria-label="Open wallet assistant" onClick={() => open("chat")}><WalletCompanion/></button>
    </div>
    {mode && <Dialog title={mode === "voice" ? "Let’s talk" : "Your wallet assistant"} onClose={() => { setMode(null); onClose(); }}>
      <div className="assistant-mode-switch"><button aria-pressed={mode === "chat"} onClick={() => setMode("chat")}><MessageCircle size={16}/>Chat</button><button aria-pressed={mode === "voice"} onClick={() => setMode("voice")}><Mic size={16}/>Voice</button></div>
      <p className="assistant-privacy">{mode === "voice" ? "Speak, then check your transcript before sending. You can change this in the options below." : "Type naturally. Your conversation stays connected across turns."} Payments still require your approval. Never share a PIN or OTP here.</p>
      <VoiceAssistantPanel mode={mode} autoStart={mode === "voice"} onConfirmed={onConfirmed}/>
    </Dialog>}
  </>;
}

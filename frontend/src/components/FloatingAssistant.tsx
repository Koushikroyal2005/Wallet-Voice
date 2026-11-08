import { useEffect, useRef, useState } from "react";
import { MessageCircle, Mic } from "lucide-react";
import { WalletCompanion } from "./WalletCompanion";
import { Dialog } from "./Dialog";
import { VoiceAssistantPanel } from "./VoiceAssistantPanel";

export function FloatingAssistant({ requested, onClose, onConfirmed }: { requested: boolean; onClose: () => void; onConfirmed: () => void }) {
  const [mode, setMode] = useState<"chat" | "voice" | null>(null);
  const [position, setPosition] = useState(() => Math.max(100, Math.min(window.innerHeight - 120, Number(localStorage.getItem("wallet-assistant-y")) || window.innerHeight - 150)));
  const [tip, setTip] = useState(true);
  const [tips, setTips] = useState(() => localStorage.getItem("wallet-assistant-tips") !== "off");
  const [menu, setMenu] = useState(false);
  const [choice, setChoice] = useState<"chat" | "voice" | null>(null);
  const gesture = useRef({ x: 0, y: 0, origin: 0, moved: false, second: false, radial: false });
  const lastTap = useRef(0);
  const hold = useRef<number>();
  const click = useRef<number>();
  const open = (next: "chat" | "voice") => { setMenu(false); setMode(next); setTips(false); localStorage.setItem("wallet-assistant-tips", "off"); };
  useEffect(() => {
    const launch = (event: Event) => open((event as CustomEvent).detail === "voice" ? "voice" : "chat");
    window.addEventListener("wallet-assistant-open", launch);
    return () => window.removeEventListener("wallet-assistant-open", launch);
  }, []);
  useEffect(() => { if (requested) open("chat"); }, [requested]);
  useEffect(() => {
    const id = window.setTimeout(() => setTip(!tip), tip ? 10000 : 5000);
    return () => window.clearTimeout(id);
  }, [tip]);
  useEffect(() => {
    const resize = () => setPosition(y => Math.max(100, Math.min(window.innerHeight - 120, y)));
    window.addEventListener("resize", resize);
    return () => { window.removeEventListener("resize", resize); window.clearTimeout(hold.current); window.clearTimeout(click.current); };
  }, []);
  return <>
    <div className="assistant-dock" style={{ top: position }}>
      {tips && tip && !mode && !menu && <div className="assistant-tip"><strong>Your personal wallet assistant</strong><span>Double-tap to talk. Hold the second tap for modes.</span><button aria-label="Dismiss assistant tips" onClick={() => { setTips(false); localStorage.setItem("wallet-assistant-tips", "off"); }}>×</button></div>}
      {menu && <div className="assistant-fan" aria-label="Assistant modes">
        <button className={choice === "chat" ? "chosen" : ""} onClick={() => open("chat")}><MessageCircle size={20}/>Chat</button>
        <button className={choice === "voice" ? "chosen" : ""} onClick={() => open("voice")}><Mic size={20}/>Voice</button>
      </div>}
      <button className="assistant-orb" aria-label="Open wallet assistant; Enter for chat, Shift Enter for voice" aria-expanded={!!mode || menu}
        onClick={e => { if (e.detail === 0) open("chat"); }}
        onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(e.shiftKey ? "voice" : "chat"); } if (e.key === "Escape") setMenu(false); }}
        onContextMenu={e => { e.preventDefault(); setMenu(true); }}
        onPointerDown={e => {
          if (e.button !== 0) return;
          e.currentTarget.setPointerCapture(e.pointerId);
          const second = Date.now() - lastTap.current < 400;
          window.clearTimeout(click.current);
          gesture.current = { x: e.clientX, y: e.clientY, origin: position, moved: false, second, radial: false };
          if (second) hold.current = window.setTimeout(() => { gesture.current.radial = true; setMenu(true); }, 320);
        }}
        onPointerMove={e => {
          if (!e.currentTarget.hasPointerCapture(e.pointerId)) return;
          const g = gesture.current;
          if (g.radial) { setChoice(e.clientX < g.x - 25 ? (e.clientY < g.y ? "chat" : "voice") : null); return; }
          if (Math.abs(e.clientY - g.y) > 8) { g.moved = true; window.clearTimeout(hold.current); setPosition(Math.max(100, Math.min(window.innerHeight - 120, g.origin + e.clientY - g.y))); }
        }}
        onPointerCancel={() => { window.clearTimeout(hold.current); setMenu(false); setChoice(null); }}
        onPointerUp={e => {
          window.clearTimeout(hold.current);
          const g = gesture.current;
          e.currentTarget.releasePointerCapture(e.pointerId);
          if (g.radial) { if (e.clientX < g.x - 25) open(e.clientY < g.y ? "chat" : "voice"); setChoice(null); lastTap.current = 0; return; }
          if (g.moved) { localStorage.setItem("wallet-assistant-y", String(position)); lastTap.current = 0; return; }
          if (g.second) { lastTap.current = 0; open("voice"); }
          else { lastTap.current = Date.now(); click.current = window.setTimeout(() => open("chat"), 410); }
        }}><WalletCompanion/></button>
    </div>
    {mode && <Dialog title={mode === "voice" ? "Let’s talk" : "Your wallet assistant"} onClose={() => { setMode(null); onClose(); }}>
      <div className="assistant-mode-switch"><button aria-pressed={mode === "chat"} onClick={() => setMode("chat")}><MessageCircle size={16}/>Chat</button><button aria-pressed={mode === "voice"} onClick={() => setMode("voice")}><Mic size={16}/>Voice</button></div>
      <p className="assistant-privacy">{mode === "voice" ? "Microphone is active only here. Pause after speaking to send automatically." : "Type naturally. Your conversation stays connected across turns."} Payments still require review. Never share a PIN or OTP here.</p>
      <VoiceAssistantPanel key={mode} mode={mode} autoStart={mode === "voice"} onConfirmed={onConfirmed}/>
    </Dialog>}
  </>;
}

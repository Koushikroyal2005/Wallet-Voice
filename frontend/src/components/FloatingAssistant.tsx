import { useEffect, useState, useRef, type ReactNode } from "react";
import { createPortal } from 'react-dom';
import { MessageCircle, Mic } from "lucide-react";
import { WalletCompanion } from "./WalletCompanion";
import { Dialog } from "./Dialog";
import { VoiceAssistantPanel } from "./VoiceAssistantPanel";

function HomeConversation({title,onClose,children}:{title:string;onClose:()=>void;children:ReactNode}) {
  const heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{const previous=document.activeElement as HTMLElement;heading.current?.focus();const escape=(event:KeyboardEvent)=>{if(event.key==='Escape')onClose();};window.addEventListener('keydown',escape);return()=>{window.removeEventListener('keydown',escape);previous?.focus();};},[]);
  return <section className="home-conversation" aria-label="Wallet conversation"><div className="section-heading"><h2 ref={heading} tabIndex={-1}>{title}</h2><button className="secondary" onClick={onClose}>Close conversation</button></div>{children}</section>;
}

export function FloatingAssistant({ requested, onClose, onConfirmed, inlineTarget }: { requested: boolean; onClose: () => void; onConfirmed: () => void; inlineTarget?:string }) {
  const [mode, setMode] = useState<"chat" | "voice" | null>(null);
  const openedAt=useRef(inlineTarget);
  const open = (next: "chat" | "voice") => {openedAt.current=inlineTarget;setMode(next);};
  useEffect(()=>{setMode(null);onClose();},[inlineTarget]);
  useEffect(() => {
    const launch = (event: Event) => open((event as CustomEvent).detail === "voice" ? "voice" : "chat");
    window.addEventListener("wallet-assistant-open", launch);
    return () => window.removeEventListener("wallet-assistant-open", launch);
  }, [inlineTarget]);
  useEffect(() => { if (requested) open("chat"); }, [requested]);
  const close=()=>{setMode(null);onClose();};
  const title=mode==='voice'?'Let’s talk':'Your wallet assistant';
  const content=<><div className="assistant-mode-switch"><button aria-pressed={mode === "chat"} onClick={() => setMode("chat")}><MessageCircle size={16}/>Chat</button><button aria-pressed={mode === "voice"} onClick={() => setMode("voice")}><Mic size={16}/>Voice</button></div><p className="assistant-privacy">{mode === 'voice' ? 'Speak and pause. Review what was heard, then approve securely.' : 'Type naturally. Your conversation stays connected across turns.'} Never speak or type your PIN or OTP. Audio uses a cloud transcription provider.</p><VoiceAssistantPanel mode={mode || 'chat'} autoStart={mode==='voice'} onConfirmed={onConfirmed}/></>;
  const target=inlineTarget?document.getElementById(inlineTarget):null;
  return <>
    <div className="assistant-dock" style={target && mode ? {display:'none'} : undefined}>
      <div className="assistant-dock-actions">
        <button onClick={() => open("voice")}><Mic size={16}/>Talk</button>
        <button onClick={() => open("chat")}><MessageCircle size={16}/>Type</button>
      </div>
      <button className="assistant-orb" aria-label="Open wallet assistant" onClick={() => open("chat")}><WalletCompanion/></button>
    </div>
    {mode && openedAt.current===inlineTarget && (target ? createPortal(<HomeConversation title={title} onClose={close}>{content}</HomeConversation>,target) : <Dialog title={title} onClose={close}>{content}</Dialog>)}
  </>;
}

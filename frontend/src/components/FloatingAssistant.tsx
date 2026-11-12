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
  const launcher = useRef<HTMLDivElement>(null);
  // Moving this stable DOM host preserves React children (including nested PIN
  // dialogs); changing a conversation portal target would remount them.
  const [conversationHost] = useState(()=>document.createElement('div'));
  const [portalHost, setPortalHost] = useState<HTMLElement>(document.body);
  useEffect(()=>{document.body.appendChild(conversationHost);return()=>conversationHost.remove();},[conversationHost]);
  useEffect(() => {
    let frame = 0, disposed = false;
    const update = () => {
      frame = 0;
      const node=launcher.current;if(!node)return;
      // A native modal makes body siblings inert. Keep the same controller, but
      // render its companion in the top layer so it remains keyboard reachable.
      const modal=[...document.querySelectorAll<HTMLDialogElement>('dialog[open]')].filter(el=>el.matches(':modal')).at(-1);
      setPortalHost(modal||document.body);
      if(!modal||!conversationHost.contains(modal)) {
        const parent=modal||document.body;
        if(conversationHost.parentElement!==parent)parent.appendChild(conversationHost);
      }
      const box=node.getBoundingClientRect();
      const viewport=window.visualViewport;
      const left=viewport?.offsetLeft||0, top=viewport?.offsetTop||0;
      const width=viewport?.width||innerWidth,height=viewport?.height||innerHeight;
      const gap=12,minY=top+gap,maxY=top+height-box.height-(width<=768?88:24);
      const root=modal||document.body;
      const controls=[...(root.querySelectorAll<HTMLElement>('button,input,select,textarea,a,summary,strong,b,time,p,small,dt,dd,.payment-amount,.batch-totals,.count,.badge,dialog[open]'))].filter(el=>!el.closest('.guardian-assistant-layer')&&getComputedStyle(el).visibility!=='hidden').map(el=>el.getBoundingClientRect()).filter(r=>r.width&&r.height&&r.bottom>top&&r.top<top+height);
      // Reserve the complete approval surface, not just its buttons: explanations,
      // receipts and the PIN must remain unobscured as the details scroll.
      if(modal&&width>768)controls.push(modal.getBoundingClientRect());
      if(active&&surface.current)controls.push(surface.current.getBoundingClientRect());
      const free=(x:number,y:number)=>!controls.some(r=>r.left<x+box.width+gap&&r.right>x-gap&&r.top<y+box.height+gap&&r.bottom>y-gap);
      const right=left+width-box.width-(width<=768?16:28);
      const xs=[right,...(modal?[modal.getBoundingClientRect().left-box.width-gap]:[]),
        ...[...new Set(controls.flatMap(r=>[r.left-box.width-gap,r.right+gap]))].sort((a,b)=>b-a),left+gap];
      const ys=[maxY,...controls.flatMap(r=>[r.top-box.height-gap,r.bottom+gap]),minY].filter(y=>y>=minY&&y<=maxY).sort((a,b)=>b-a);
      let point: {x:number;y:number}|undefined;
      positions: for(const x of xs) {
        if(x<left+gap||x+box.width>left+width-gap)continue;
        for(const y of ys)if(free(x,y)){point={x,y};break positions;}
      }
      point??={x:right,y:minY};
      node.style.left=`${point.x}px`;node.style.top=`${point.y}px`;
    };
    const schedule=()=>{if(!disposed&&!frame)frame=requestAnimationFrame(update);};
    const observer=new MutationObserver(schedule);observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['open','class']});
    const resize=new ResizeObserver(schedule);resize.observe(document.documentElement);if(surface.current)resize.observe(surface.current);
    window.addEventListener('scroll',schedule,true);window.addEventListener('resize',schedule);window.visualViewport?.addEventListener('resize',schedule);window.visualViewport?.addEventListener('scroll',schedule);document.fonts.ready.then(schedule);schedule();
    return()=>{disposed=true;observer.disconnect();resize.disconnect();cancelAnimationFrame(frame);window.removeEventListener('scroll',schedule,true);window.removeEventListener('resize',schedule);window.visualViewport?.removeEventListener('resize',schedule);window.visualViewport?.removeEventListener('scroll',schedule);};
  },[active,portalHost,conversationHost]);
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
      {createPortal(<div className={`guardian-assistant-layer ${active ? "is-open" : ""} mode-${mode}`}><div className="assistant-launcher" ref={launcher}>
        <AssistantOrb
          state={active ? assistant.state : "IDLE"}
          level={assistant.level}
          label={active ? "Close wallet assistant" : "Open wallet assistant"}
          onClick={() => (active ? close() : open("voice"))}
        />
      </div></div>,portalHost)}
    </div>,
    conversationHost,
  );
}

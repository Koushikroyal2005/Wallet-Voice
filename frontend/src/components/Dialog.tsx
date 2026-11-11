import { useEffect, useId, useRef } from "react";
import { X } from "lucide-react";

export function Dialog({
  title,
  children,
  onClose,
  busy = false,
  variant = "modal",
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  busy?: boolean;
  variant?: "modal" | "drawer" | "popover";
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const latest = useRef({ onClose, busy });
  latest.current = { onClose, busy };
  const id = useId();
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const floating = variant === "popover" && window.matchMedia("(min-width: 769px)").matches;
    if (floating) ref.current?.show();
    else ref.current?.showModal();
    const outside = (event: PointerEvent) => {
      if ((event.target as Element)?.closest?.(".notification-bell")) return;
      if (floating && !ref.current?.contains(event.target as Node) && !latest.current.busy) latest.current.onClose();
    };
    const escape = (event: KeyboardEvent) => {
      if (floating && event.key === "Escape" && !latest.current.busy) { event.preventDefault(); latest.current.onClose(); }
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    if (floating) ref.current?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
      ref.current?.close();
      previous?.focus();
    };
  }, [variant]);
  return (
    <dialog
      ref={ref}
      className={`dialog ${variant === "drawer" ? "review-drawer" : variant==='popover'?'notification-popover':''}`}
      aria-labelledby={id}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <div className="dialog-heading">
        <h2 id={id}>{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          disabled={busy}
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

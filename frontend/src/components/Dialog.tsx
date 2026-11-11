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
  const id = useId();
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.showModal();
    return () => {
      ref.current?.close();
      previous?.focus();
    };
  }, []);
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

import type { CSSProperties } from "react";
import { AudioLines, Square } from "lucide-react";

/** Its ring follows the measured microphone level; only thinking uses rotation. */
export function AssistantOrb({
  state = "IDLE",
  level = 0,
  onClick,
  label,
  large = false,
}: {
  state?: string;
  level?: number;
  onClick?: () => void;
  label: string;
  large?: boolean;
}) {
  return (
    <button
      type="button"
      className={`guardian-orb ${large ? "large" : ""} orb-${state.toLowerCase()}`}
      style={
        { "--voice-level": Math.max(0, Math.min(1, level)) } as CSSProperties
      }
      aria-label={label}
      onClick={onClick}
    >
      <span className="orb-rim" aria-hidden="true" />
      <span className="orb-core" aria-hidden="true">
        {state === "RECORDING" ? (
          <Square size={large ? 25 : 19} />
        ) : (
          <AudioLines size={large ? 32 : 23} />
        )}
      </span>
    </button>
  );
}

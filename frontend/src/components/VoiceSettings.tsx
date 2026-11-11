import { useState } from "react";
const preferences = [
  {
    key: "wallet-review-transcript",
    label: "Review transcript before sending",
    description:
      "Check and edit what was heard before the assistant processes it.",
    defaultValue: true,
  },
  {
    key: "wallet-read-replies",
    label: "Read replies aloud",
    description:
      "Play new replies only while using voice mode. Off by default.",
    defaultValue: false,
  },
  {
    key: "wallet-patient-listening",
    label: "Give me more time to pause",
    description: "Use a longer pause before stopping the next recording.",
    defaultValue: false,
  },
] as const;
export function VoiceSettings() {
  const [values, setValues] = useState(() =>
    Object.fromEntries(
      preferences.map((p) => [
        p.key,
        localStorage.getItem(p.key) === null
          ? p.defaultValue
          : p.key === "wallet-patient-listening"
            ? localStorage.getItem(p.key) === "true"
            : localStorage.getItem(p.key) === "on",
      ]),
    ),
  );
  return (
    <section className="surface consumer-card">
      <h2>AI & Voice</h2>
      <p>
        One conversation across chat and voice. Microphone recording starts only
        when you choose it. Never speak a PIN or OTP.
      </p>
      <div className="voice-setting-list">
        {preferences.map((p) => (
          <label className="voice-setting" key={p.key}>
            <span>
              <strong>{p.label}</strong>
              <small>{p.description}</small>
            </span>
            <input
              type="checkbox"
              checked={values[p.key]}
              onChange={(e) => {
                const checked = e.target.checked;
                setValues({ ...values, [p.key]: checked });
                localStorage.setItem(
                  p.key,
                  p.key === "wallet-patient-listening"
                    ? String(checked)
                    : checked
                      ? "on"
                      : "off",
                );
                window.dispatchEvent(
                  new Event("wallet-voice-preferences-changed"),
                );
              }}
            />
          </label>
        ))}
      </div>
      <button
        className="secondary"
        onClick={() =>
          window.dispatchEvent(
            new CustomEvent("wallet-assistant-open", { detail: "chat" }),
          )
        }
      >
        Open conversation
      </button>
      <p>
        New chat starts fresh without deleting earlier server history. To
        delete the current conversation, use the explicit Delete action in
        assistant details and wait for confirmation.
      </p>
    </section>
  );
}

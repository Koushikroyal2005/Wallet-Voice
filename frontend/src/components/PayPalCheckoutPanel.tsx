import { useEffect, useRef, useState } from "react";
import { api, post } from "../lib/api";
import { money } from "../lib/formatting";

declare global {
  interface Window {
    paypal?: any;
  }
}
let sdkPromise: Promise<void> | undefined;
function loadSdk() {
  if (window.paypal?.createInstance) return Promise.resolve();
  if (sdkPromise) return sdkPromise;
  sdkPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://www.sandbox.paypal.com/web-sdk/v6/core";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      script.remove();
      sdkPromise = undefined;
      reject(new Error("PayPal could not load. Please try again."));
    };
    document.head.appendChild(script);
  });
  return sdkPromise;
}

export function PayPalCheckoutPanel({
  paymentId,
  amount,
  onComplete,
}: {
  paymentId: string;
  amount: number;
  onComplete: () => void;
}) {
  const [state, setState] = useState("Connecting to PayPal…");
  const [config, setConfig] = useState<any>();
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const session = useRef<any>();
  const complete = useRef(onComplete);
  complete.current = onComplete;
  const active = useRef(false);
  const [pendingOrder, setPendingOrder] = useState("");
  const [phase, setPhase] = useState("Connecting");
  const [order, setOrder] = useState<any>();
  const capturing = useRef(false);
  const completed = useRef(false);
  const expectedOrder = useRef("");
  const terminal = useRef(false);
  const generation = useRef(0);
  const receive = (result: any) => {
    setOrder(result);
    terminal.current = ["COMPLETED", "DENIED", "DECLINED", "FAILED", "REFUNDED", "VOIDED"].includes(result.status);
    if (result.status === "COMPLETED") {
      setPendingOrder(""); setPhase("Completed"); setState("The backend verified your PayPal capture.");
      if (!completed.current) { completed.current = true; complete.current(); }
    } else if (["DENIED", "DECLINED", "FAILED", "REFUNDED", "VOIDED"].includes(result.status)) {
      setPendingOrder(""); setPhase(result.status === 'REFUNDED' ? 'Refunded' : "Failed or denied");
      setState(result.status === "REFUNDED" ? "This PayPal payment was refunded." : "PayPal did not complete this payment. Your wallet funds were not used.");
    } else if (result.status === "PENDING") {
      setPendingOrder(result.order_id); setPhase("Processing"); setState("PayPal is processing your capture. Waiting for a confirmed result.");
    } else {
      setPendingOrder(""); setPhase("Ready for approval");
      setState(result.status === "APPROVED" ? "Buyer approval received. You can finish the approved payment." : "Review and approve using your Sandbox buyer account.");
    }
  };
  useEffect(() => {
    let disposed = false;
    const turn = ++generation.current;
    active.current = false; capturing.current = false; completed.current = false; terminal.current = false; expectedOrder.current = "";
    setBusy(false);
    setOrder(undefined); setPendingOrder(""); setPhase("Connecting");
    setReady(false);
    setState("Connecting to PayPal…");
    void (async () => {
      try {
        const c = await api("/api/paypal/config");
        if (!c.configured || c.environment !== "sandbox")
          throw new Error("PayPal Sandbox is not configured yet.");
        if (disposed) return;
        setConfig(c);
        let existing = await api(`/api/paypal/payment-requests/${paymentId}/order`);
        if (disposed) return;
        if (existing) {
          expectedOrder.current = existing.order_id;
          if (["CREATED", "APPROVED", "AWAITING_BUYER_APPROVAL"].includes(existing.status)) {
            existing = await post(`/api/paypal/orders/${existing.order_id}/refresh`);
            if (disposed) return;
          }
          receive(existing);
          if (["COMPLETED", "PENDING", "DENIED", "DECLINED", "FAILED", "REFUNDED", "VOIDED"].includes(existing.status)) return;
        }
        await loadSdk();
        const sdk = await window.paypal.createInstance({
          clientId: c.client_id,
          components: ["paypal-payments"],
          pageType: "checkout",
        });
        const methods = await sdk.findEligibleMethods({
          currencyCode: c.checkout_currency,
        });
        if (!methods?.isEligible?.("paypal"))
          throw new Error("PayPal is unavailable for this checkout.");
        if (disposed) return;
        session.current = sdk.createPayPalOneTimePaymentSession({
          onApprove: async (data: any) => {
            if (disposed || capturing.current || terminal.current || data.orderId !== expectedOrder.current) return;
            capturing.current = true;
            setPhase("Processing");
            setState("Confirming your payment…");
            try {
              const captured = await post(
                `/api/paypal/orders/${data.orderId}/capture`,
              );
              if (disposed) return;
              receive(captured);
            } catch (error) {
              if (!disposed) {
                setPhase("Processing"); setPendingOrder(data.orderId);
                setState(
                  "Capture confirmation was interrupted. Checking the same order; do not start another payment.",
                );
              }
            } finally {
              if (turn === generation.current) { active.current = false; capturing.current = false; }
              if (!disposed) setBusy(false);
            }
          },
          onCancel: () => {
            if (disposed || capturing.current || terminal.current) return;
            active.current = false;
            if (!disposed) {
              setBusy(false);
              setPhase("Ready for approval");
              setState("Checkout closed. Reopen it to finish the same order.");
            }
          },
          onError: () => {
            if (disposed || capturing.current || terminal.current) return;
            active.current = false;
            if (!disposed) {
              setBusy(false);
              setPhase("Status unknown");
              if (expectedOrder.current) setPendingOrder(expectedOrder.current);
              setState(
                "PayPal could not finish. Retry to resume the same order.",
              );
            }
          },
        });
        setReady(true);
        setPhase("Ready for approval");
        setState("Ready for your Sandbox buyer approval.");
      } catch (error) {
        if (!disposed) { setPhase("Unavailable"); setState((error as Error).message); }
      }
    })();
    return () => {
      disposed = true;
      generation.current++;
      session.current = undefined;
    };
  }, [paymentId, retry]);
  useEffect(() => {
    if (!pendingOrder) return;
    let disposed = false;
    let running = false;
    let attempts = 0;
    const timer = window.setInterval(() => {
      if (running || ++attempts > 12) { if (attempts > 12) window.clearInterval(timer); return; }
      running = true;
      void post(`/api/paypal/orders/${pendingOrder}/refresh`)
        .then((order) => {
          if (!disposed) receive(order);
        })
        .catch(() => { if (!disposed) setState("Status confirmation is unavailable. The outcome is still unknown; do not pay again."); })
        .finally(() => { running = false; });
    }, 5000);
    return () => { disposed = true; window.clearInterval(timer); };
  }, [pendingOrder]);
  async function checkout() {
    if (active.current || !session.current || terminal.current) return;
    const turn = generation.current;
    active.current = true;
    setPhase("Waiting for buyer approval");
    setBusy(true);
    setState("Opening PayPal…");
    try {
      await session.current.start(
        { presentationMode: "auto" },
        post("/api/paypal/orders", { payment_request_id: paymentId }).then(
          (created) => {
            if (turn !== generation.current) throw new Error("Checkout closed.");
            expectedOrder.current = created.order_id; setOrder(created);
            if (!["CREATED", "AWAITING_BUYER_APPROVAL", "APPROVED"].includes(created.status)) {
              receive(created); throw new Error("This order already has a recorded result.");
            }
            return { orderId: created.order_id };
          },
        ),
      );
    } catch (error) {
      if (turn !== generation.current || terminal.current || capturing.current) return;
      active.current = false;
      setBusy(false);
      setPhase("Status unknown");
      setState(
        (error as Error).message ||
          "Unable to open PayPal. Retry to resume your order.",
      );
    }
  }
  return (
    <div className="paypal-panel">
      <strong>PayPal Sandbox</strong>
      <span>{money(amount)} · paid externally</span>
      <small>Your internal wallet balance stays unchanged.</small>
      {order && <small>PayPal amount: {order.provider_currency} {order.provider_amount}</small>}
      <strong role="status">{phase}</strong>
      {config?.checkout_currency === "USD" && (
        <small>
          Demo conversion: ₹{config.demo_inr_per_usd} per USD. Review the dollar
          amount at checkout.
        </small>
      )}
      <button disabled={!ready || busy || !!pendingOrder || ["Completed", "Failed or denied", "Refunded"].includes(phase)} onClick={checkout}>
        {busy ? "Waiting for PayPal…" : "Continue with PayPal"}
      </button>
      {(!ready || !!pendingOrder || phase === "Status unknown") && !["Completed", "Failed or denied", "Refunded"].includes(phase) && (
        <button className="secondary" onClick={() => setRetry(retry + 1)}>
          Reconnect
        </button>
      )}
      <span role="status">{state}</span>
      {order?.capture_id && <small>Capture reference: {order.capture_id}</small>}
    </div>
  );
}

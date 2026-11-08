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
  if (window.paypal) return Promise.resolve();
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
  useEffect(() => {
    let disposed = false;
    setReady(false);
    setState("Connecting to PayPal…");
    void (async () => {
      try {
        const c = await api("/api/paypal/config");
        if (!c.configured)
          throw new Error("PayPal Sandbox is not configured yet.");
        if (disposed) return;
        setConfig(c);
        const token = await api("/api/paypal/browser-client-token");
        await loadSdk();
        const sdk = await window.paypal.createInstance({
          clientToken: token.client_token,
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
            if (disposed) return;
            setState("Confirming your payment…");
            try {
              const captured = await post(
                `/api/paypal/orders/${data.orderId}/capture`,
              );
              if (disposed) return;
              if (captured.status === "COMPLETED") {
                setState("Payment completed.");
                complete.current();
              } else if (captured.status === "PENDING") {
                setPendingOrder(data.orderId);
                setState(
                  "PayPal is processing your payment. We’ll wait for confirmation.",
                );
              } else
                setState(
                  `PayPal returned ${captured.status.toLowerCase()}. Your wallet funds were not used.`,
                );
            } catch (error) {
              if (!disposed)
                setState(
                  (error as Error).message +
                    " You can reopen checkout to check this order.",
                );
            } finally {
              active.current = false;
              if (!disposed) setBusy(false);
            }
          },
          onCancel: () => {
            active.current = false;
            if (!disposed) {
              setBusy(false);
              setState("Checkout closed. Reopen it to finish the same order.");
            }
          },
          onError: () => {
            active.current = false;
            if (!disposed) {
              setBusy(false);
              setState(
                "PayPal could not finish. Retry to resume the same order.",
              );
            }
          },
        });
        setReady(true);
        setState("Ready for your Sandbox buyer approval.");
      } catch (error) {
        if (!disposed) setState((error as Error).message);
      }
    })();
    return () => {
      disposed = true;
      session.current = undefined;
    };
  }, [paymentId, retry]);
  useEffect(() => {
    if (!pendingOrder) return;
    const timer = window.setInterval(() => {
      void api(`/api/paypal/orders/${pendingOrder}`)
        .then((order) => {
          if (order.status === "COMPLETED") {
            setPendingOrder("");
            complete.current();
          }
        })
        .catch(() =>
          setState(
            "Status refresh unavailable. Your payment is still being checked.",
          ),
        );
    }, 3000);
    return () => window.clearInterval(timer);
  }, [pendingOrder]);
  async function checkout() {
    if (active.current || !session.current) return;
    active.current = true;
    setBusy(true);
    setState("Opening PayPal…");
    try {
      await session.current.start(
        { presentationMode: "auto" },
        post("/api/paypal/orders", { payment_request_id: paymentId }).then(
          (created) => ({ orderId: created.order_id }),
        ),
      );
    } catch (error) {
      active.current = false;
      setBusy(false);
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
      {config?.checkout_currency === "USD" && (
        <small>
          Demo conversion: ₹{config.demo_inr_per_usd} per USD. Review the dollar
          amount at checkout.
        </small>
      )}
      <button disabled={!ready || busy || !!pendingOrder} onClick={checkout}>
        {busy ? "Waiting for PayPal…" : "Continue with PayPal"}
      </button>
      {!ready && (
        <button className="secondary" onClick={() => setRetry(retry + 1)}>
          Reconnect
        </button>
      )}
      <span role="status">{state}</span>
    </div>
  );
}

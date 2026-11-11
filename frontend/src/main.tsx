import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import "./design.css";
import "./premium.css";

if (isSecureContext && 'serviceWorker' in navigator) {
  void navigator.serviceWorker.register('/sw.js').catch(() => undefined);
}

const client = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 5000, refetchInterval: 15000 },
  },
});
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={client}>
    <App />
  </QueryClientProvider>,
);

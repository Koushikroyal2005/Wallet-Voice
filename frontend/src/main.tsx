import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import "./design.css";

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

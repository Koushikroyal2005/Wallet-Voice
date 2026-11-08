export async function api<T = any>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const data = await response.json().catch(() => null);
  if (response.status === 401 && !path.startsWith("/api/auth/"))
    window.dispatchEvent(new Event("wallet-session-expired"));
  if (!response.ok)
    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : "We could not complete that request. Check your connection and try again.",
    );
  return data as T;
}
export const post = <T = any>(path: string, body?: unknown) =>
  api<T>(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
export function minorUnits(value: string) {
  if (!/^\d+(\.\d{1,2})?$/.test(value.trim())) return 0;
  const amount = Math.round(Number(value) * 100);
  return Number.isSafeInteger(amount) && amount > 0 && amount <= 10_000_000
    ? amount
    : 0;
}
export function operationKey(scope: string) {
  const key = `aiwallet-operation:${scope}`;
  let value = sessionStorage.getItem(key);
  if (!value) {
    value = crypto.randomUUID();
    sessionStorage.setItem(key, value);
  }
  return value;
}
export function finishOperation(scope: string) {
  sessionStorage.removeItem(`aiwallet-operation:${scope}`);
}

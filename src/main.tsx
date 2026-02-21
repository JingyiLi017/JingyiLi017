import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./ui/App";
import "./ui/styles.css";

function headersToRecord(headers?: HeadersInit): Record<string, string> {
  const out: Record<string, string> = {};
  if (!headers) return out;
  if (headers instanceof Headers) {
    headers.forEach((v, k) => {
      out[k] = v;
    });
    return out;
  }
  if (Array.isArray(headers)) {
    for (const [k, v] of headers) out[String(k)] = String(v);
    return out;
  }
  for (const [k, v] of Object.entries(headers)) {
    out[k] = String(v as any);
  }
  return out;
}

function shouldProxyApi(url: URL): boolean {
  return url.pathname.startsWith("/v1/");
}

function installDesktopApiFetchProxy() {
  const api = window.desktopApi as any;
  if (!api || typeof api.httpRequest !== "function") return;
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    try {
      const reqUrl = input instanceof Request ? input.url : String(input);
      const url = new URL(reqUrl, window.location.origin);
      if (!shouldProxyApi(url)) {
        return originalFetch(input as any, init);
      }

      const method = String(init?.method || (input instanceof Request ? input.method : "GET") || "GET").toUpperCase();
      let body: any = undefined;
      if (init?.body !== undefined && init?.body !== null) {
        if (typeof init.body === "string") {
          body = init.body;
        } else if (init.body instanceof URLSearchParams) {
          body = init.body.toString();
        } else {
          // Keep non-string bodies on native fetch path.
          return originalFetch(input as any, init);
        }
      } else if (input instanceof Request && method !== "GET" && method !== "HEAD") {
        body = await input.clone().text();
      }

      const proxyOut = await api.httpRequest({
        path: `${url.pathname}${url.search}`,
        method,
        headers: headersToRecord(init?.headers || (input instanceof Request ? input.headers : undefined)),
        body,
      });
      const status = Number(proxyOut?.status || 0) || 500;
      const text = String(proxyOut?.text || "");
      const respHeaders = new Headers(proxyOut?.headers || {});
      return new Response(text, {
        status,
        statusText: String(proxyOut?.statusText || ""),
        headers: respHeaders,
      });
    } catch {
      return originalFetch(input as any, init);
    }
  };
}

installDesktopApiFetchProxy();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

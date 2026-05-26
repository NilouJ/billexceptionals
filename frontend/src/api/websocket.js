export function openScreeningSocket({ onEvent, onClose, onError } = {}) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${window.location.host}/ws/screen`);

  ws.onmessage = (e) => {
    try { onEvent?.(JSON.parse(e.data)); }
    catch (err) { onError?.(err); }
  };
  ws.onclose = (e) => onClose?.(e);
  ws.onerror = (e) => onError?.(e);

  const sendCase = (caseData) => {
    if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(caseData));
    else ws.addEventListener("open", () => ws.send(JSON.stringify(caseData)), { once: true });
  };

  return { ws, sendCase, close: () => ws.close() };
}
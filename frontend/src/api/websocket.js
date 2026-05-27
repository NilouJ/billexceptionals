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


export function openChatSocket({ onEvent, onClose, onError } = {}) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${window.location.host}/ws/chat`);

  ws.onmessage = (e) => {
    try { onEvent?.(JSON.parse(e.data)); }
    catch (err) { onError?.(err); }
  };
  ws.onclose = (e) => onClose?.(e);
  ws.onerror = (e) => onError?.(e);

  const send = (obj) => {
    if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
    else ws.addEventListener("open", () => ws.send(JSON.stringify(obj)), { once: true });
  };

  return {
    ws,
    init:    (case_id, state, reset = false) => send({ type: "init", case_id, state, reset }),
    message: (text) => send({ type: "message", text }),
    close:   () => ws.close(),
  };
}

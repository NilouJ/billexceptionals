const BASE = "/api";

export async function fetchCases() {
  const res = await fetch(`${BASE}/cases`);
  if (!res.ok) throw new Error(`fetchCases ${res.status}`);
  return res.json();
}

export async function submitFeedback(payload) {
  const res = await fetch(`${BASE}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`submitFeedback ${res.status}`);
  return res.json();
}
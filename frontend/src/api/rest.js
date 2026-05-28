const BASE = "/api";

export async function fetchCases({ page = 1, pageSize = 20, search = "" } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (search) params.set("search", search);
  const res = await fetch(`${BASE}/cases?${params}`);
  if (!res.ok) throw new Error(`fetchCases ${res.status}`);
  return res.json(); // { items, total, page, page_size, pages }
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
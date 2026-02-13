export async function uploadCSVs(air, road) {
  const form = new FormData();
  form.append("air", air);
  form.append("road", road);
  return fetch("http://localhost:8000/upload", { method:"POST", body:form });
}

export async function sendChat(query) {
  const form = new FormData();
  form.append("query", query);
  const res = await fetch("http://localhost:8000/chat", {
    method:"POST",
    body:form
  });
  return res.json();
}

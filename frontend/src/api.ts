export async function uploadJsonl(file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("http://localhost:8000/api/upload", {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

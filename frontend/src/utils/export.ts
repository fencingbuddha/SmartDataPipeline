// frontend/src/utils/export.ts
export function buildCsvUrl(apiBase: string, params: {
  source_name: string; metric: string; start: string; end: string;
}) {
  const q = new URLSearchParams(params as any).toString();
  return `${apiBase}/api/metrics/export/csv?${q}`;
}

export function triggerCsvDownload(url: string, filename?: string) {
  const a = document.createElement("a");
  a.href = url;
  if (filename) a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}
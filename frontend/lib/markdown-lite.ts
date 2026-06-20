/** Conversão leve Markdown → HTML (preview da especificação técnica). */

export function markdownToHtml(markdown: string): string {
  if (!markdown.trim()) return "<p><br></p>";

  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const parts: string[] = [];
  let inUl = false;

  const closeUl = () => {
    if (inUl) {
      parts.push("</ul>");
      inUl = false;
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      closeUl();
      parts.push("<p><br></p>");
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      closeUl();
      const level = heading[1].length;
      parts.push(`<h${level}>${inlineMd(heading[2])}</h${level}>`);
      continue;
    }

    const bullet = line.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      if (!inUl) {
        parts.push("<ul>");
        inUl = true;
      }
      parts.push(`<li>${inlineMd(bullet[1])}</li>`);
      continue;
    }

    closeUl();
    parts.push(`<p>${inlineMd(line)}</p>`);
  }

  closeUl();
  return parts.join("\n");
}

function inlineMd(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

export function extractBodyHtml(fullHtml: string): string {
  const match = fullHtml.match(
    /<div class="tech-spec-body"[^>]*>([\s\S]*?)<\/div>\s*(?:<div class="tech-spec-page-footer"|$)/i
  );
  return match ? match[1].trim() : fullHtml;
}

export function htmlToPlainText(html: string): string {
  if (typeof document === "undefined") return html;
  const el = document.createElement("div");
  el.innerHTML = html;
  return el.innerText || "";
}

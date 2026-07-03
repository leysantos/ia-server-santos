/** Extensões aceitas no chat (espelha backend/core/chat/chat_attachment_service.py) */
export const CHAT_ATTACHMENT_ACCEPT =
  ".pdf,.txt,.md,.json,.csv,.xlsx,.xls,.docx,.dxf,.dwg,.ifc,.rtf,.png,.jpg,.jpeg,.webp,.heic,.heif,.zip,.py,.js,.ts,.tsx,.jsx,.java,.go,.rs,.sql,.yaml,.yml,.xml,.html,.css,.sh";

export const CHAT_ATTACHMENT_MAX_FILES = 10;
export const CHAT_ATTACHMENT_MAX_MB = 30;

export function formatChatAttachmentSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

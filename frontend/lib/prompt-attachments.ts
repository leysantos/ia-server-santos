import { api } from "@/services/api";

export interface PromptAttachmentUploadResult {
  attachmentIds?: string[];
  llmModel: string;
}

/** Envia arquivos para POST /chat/attachments e retorna IDs + modelo sugerido (modo auto). */
export async function uploadPromptAttachments(
  files: File[] | undefined,
  llmModel: string
): Promise<PromptAttachmentUploadResult> {
  if (!files?.length) {
    return { llmModel };
  }

  const upload = await api.chatUploadAttachments(files);
  const attachmentIds = upload.items.map((item) => item.id);
  const resolvedModel =
    llmModel === "auto" && upload.model_hint ? upload.model_hint : llmModel;

  return { attachmentIds, llmModel: resolvedModel };
}

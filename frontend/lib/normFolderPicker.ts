/**
 * Seleção de pasta sem <input webkitdirectory> — evita o popup nativo
 * "Carregar N arquivos para este site?" do Chrome/Edge.
 *
 * Usa File System Access API (botão) e FileSystemEntry (drag-and-drop).
 */

export function supportsDirectoryPicker(): boolean {
  return typeof window !== "undefined" && "showDirectoryPicker" in window;
}

function tagRelativePath(file: File, relativePath: string): File {
  try {
    Object.defineProperty(file, "webkitRelativePath", {
      value: relativePath,
      configurable: true,
    });
  } catch {
    /* ignore */
  }
  return file;
}

export async function collectPdfsFromDirectoryHandle(
  dirHandle: FileSystemDirectoryHandle,
  rootName: string,
  relativePrefix = ""
): Promise<File[]> {
  const pdfs: File[] = [];

  for await (const entry of dirHandle.values()) {
    const rel = relativePrefix ? `${relativePrefix}/${entry.name}` : entry.name;

    if (entry.kind === "file") {
      const file = await (entry as FileSystemFileHandle).getFile();
      if (file.name.toLowerCase().endsWith(".pdf")) {
        pdfs.push(tagRelativePath(file, `${rootName}/${rel}`));
      }
    } else if (entry.kind === "directory") {
      pdfs.push(
        ...(await collectPdfsFromDirectoryHandle(
          entry as FileSystemDirectoryHandle,
          rootName,
          rel
        ))
      );
    }
  }

  return pdfs;
}

export async function pickFolderPdfs(): Promise<{ files: File[]; folderName: string }> {
  if (!supportsDirectoryPicker()) {
    throw new Error("DIRECTORY_PICKER_UNSUPPORTED");
  }

  const dirHandle = await window.showDirectoryPicker({ mode: "read" });
  const files = await collectPdfsFromDirectoryHandle(dirHandle, dirHandle.name);
  return { files, folderName: dirHandle.name };
}

function readDirectoryEntries(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
  return new Promise((resolve, reject) => {
    reader.readEntries(resolve, reject);
  });
}

async function collectPdfsFromDirectoryEntry(
  dirEntry: FileSystemDirectoryEntry,
  rootName: string,
  relativePrefix: string
): Promise<File[]> {
  const reader = dirEntry.createReader();
  const pdfs: File[] = [];
  let batch: FileSystemEntry[];

  do {
    batch = await readDirectoryEntries(reader);
    for (const entry of batch) {
      const rel = relativePrefix ? `${relativePrefix}/${entry.name}` : entry.name;

      if (entry.isFile) {
        const file = await new Promise<File>((resolve, reject) => {
          (entry as FileSystemFileEntry).file(resolve, reject);
        });
        if (file.name.toLowerCase().endsWith(".pdf")) {
          pdfs.push(tagRelativePath(file, `${rootName}/${rel}`));
        }
      } else if (entry.isDirectory) {
        pdfs.push(
          ...(await collectPdfsFromDirectoryEntry(
            entry as FileSystemDirectoryEntry,
            rootName,
            rel
          ))
        );
      }
    }
  } while (batch.length > 0);

  return pdfs;
}

function fileEntryToFile(entry: FileSystemFileEntry, rootName: string): Promise<File | null> {
  return new Promise((resolve, reject) => {
    entry.file(
      (file) => {
        if (!file.name.toLowerCase().endsWith(".pdf")) {
          resolve(null);
          return;
        }
        resolve(tagRelativePath(file, `${rootName}/${file.name}`));
      },
      reject
    );
  });
}

/** Drag-and-drop de pasta ou arquivos — sem input webkitdirectory. */
export async function collectPdfsFromDataTransfer(
  dataTransfer: DataTransfer
): Promise<{ files: File[]; folderName: string | null }> {
  const items = dataTransfer.items;

  if (items?.length && typeof items[0]?.webkitGetAsEntry === "function") {
    const pdfs: File[] = [];
    let folderName: string | null = null;

    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry();
      if (!entry) continue;

      if (entry.isDirectory) {
        folderName = entry.name;
        pdfs.push(
          ...(await collectPdfsFromDirectoryEntry(
            entry as FileSystemDirectoryEntry,
            entry.name,
            ""
          ))
        );
      } else if (entry.isFile) {
        const file = await fileEntryToFile(entry as FileSystemFileEntry, entry.name);
        if (file) pdfs.push(file);
      }
    }

    if (pdfs.length) {
      return { files: pdfs, folderName };
    }
  }

  const fromList = Array.from(dataTransfer.files).filter((f) =>
    f.name.toLowerCase().endsWith(".pdf")
  );
  return { files: fromList, folderName: null };
}

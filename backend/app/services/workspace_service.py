"""Serviços de workspace — projetos, conversas e arquivos."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.database.service import (
    add_project_file_record,
    create_project_record,
    delete_conversation_record,
    delete_project_file_record,
    delete_project_record,
    get_conversation_detail,
    get_project_detail,
    list_conversations,
    list_projects,
    search_workspace,
    update_conversation_record,
    update_project_record,
)

PROJECTS_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "projects"


class WorkspaceService:
    def list_projects(self, limit: int = 50, db: Optional[Session] = None) -> dict:
        items = list_projects(limit=limit, db=db)
        return {"total": len(items), "items": items}

    def create_project(
        self,
        name: str,
        description: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> dict:
        project = create_project_record(name=name, description=description, db=db)
        if not project:
            raise HTTPException(status_code=503, detail="Banco de dados indisponível")
        PROJECTS_DATA_DIR.mkdir(parents=True, exist_ok=True)
        (PROJECTS_DATA_DIR / project["id"]).mkdir(parents=True, exist_ok=True)
        return project

    def get_project(self, project_id: str, db: Optional[Session] = None) -> dict:
        project = get_project_detail(project_id, db=db)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        return project

    def update_project(
        self,
        project_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> dict:
        project = update_project_record(
            project_id,
            name=name,
            description=description,
            db=db,
        )
        if not project:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        return project

    def delete_project(self, project_id: str, db: Optional[Session] = None) -> dict:
        project_dir = PROJECTS_DATA_DIR / project_id
        if not delete_project_record(project_id, db=db):
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        if project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)
        return {"deleted": True, "id": project_id}

    def list_conversations(
        self,
        limit: int = 50,
        project_id: Optional[str] = None,
        unassigned_only: bool = False,
        db: Optional[Session] = None,
    ) -> dict:
        items = list_conversations(
            limit=limit,
            project_id=project_id,
            unassigned_only=unassigned_only,
            db=db,
        )
        return {"total": len(items), "items": items}

    def get_conversation(self, conversation_id: str, db: Optional[Session] = None) -> dict:
        conversation = get_conversation_detail(conversation_id, db=db)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
        return conversation

    def update_conversation(
        self,
        conversation_id: str,
        *,
        title: Optional[str] = None,
        project_id: Optional[str | None] = None,
        update_project: bool = False,
        db: Optional[Session] = None,
    ) -> dict:
        from core.database.service import _SENTINEL, update_conversation_record

        conversation = update_conversation_record(
            conversation_id,
            title=title,
            project_id=project_id if update_project else _SENTINEL,
            db=db,
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
        return conversation

    def delete_conversation(self, conversation_id: str, db: Optional[Session] = None) -> dict:
        if not delete_conversation_record(conversation_id, db=db):
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
        return {"deleted": True, "id": conversation_id}

    async def upload_project_files(
        self,
        project_id: str,
        files: list[UploadFile],
        db: Optional[Session] = None,
    ) -> dict:
        from core.project_rag.project_rag import index_project_file

        project = get_project_detail(project_id, db=db)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")

        project_dir = PROJECTS_DATA_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        saved: list[dict] = []
        indexing: list[dict] = []
        for upload in files:
            filename = upload.filename or f"file-{uuid.uuid4().hex[:8]}"
            safe_name = Path(filename).name
            dest = project_dir / safe_name
            content = await upload.read()
            dest.write_bytes(content)

            row = add_project_file_record(
                project_id=project_id,
                filename=safe_name,
                storage_path=str(dest),
                content_type=upload.content_type,
                size_bytes=len(content),
                db=db,
            )
            if row:
                saved.append(row)
                index_result = index_project_file(
                    project_id,
                    dest,
                    safe_name,
                    force=True,
                )
                indexing.append(index_result)

        if saved:
            try:
                from core.project_memory.service import record_activity

                names = ", ".join(f["filename"] for f in saved[:3])
                record_activity(
                    source="upload",
                    event_type="completed",
                    title=f"Upload: {len(saved)} arquivo(s)",
                    summary=names + ("…" if len(saved) > 3 else ""),
                    project_id=project_id,
                    meta={"file_count": len(saved), "filenames": [f["filename"] for f in saved]},
                    db=db,
                )
            except Exception:
                pass

        return {"uploaded": len(saved), "files": saved, "indexing": indexing}

    def reindex_project(self, project_id: str, db: Optional[Session] = None) -> dict:
        from core.project_rag.project_rag import reindex_project

        project = get_project_detail(project_id, db=db)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        return reindex_project(project_id, project.get("files") or [], force=True)

    def search(self, query: str, limit: int = 30, db: Optional[Session] = None) -> dict:
        result = search_workspace(query, limit=limit, db=db)
        return {
            "query": query.strip(),
            "projects": result["projects"],
            "conversations": result["conversations"],
            "total": len(result["projects"]) + len(result["conversations"]),
        }

    def get_file_preview(
        self,
        project_id: str,
        file_id: str,
        db: Optional[Session] = None,
    ) -> tuple[bytes, str, str]:
        """Retorna bytes, media_type e filename para preview (imagem ou PDF→PNG)."""
        from core.database.repository import DatabaseRepository

        if db is None:
            raise HTTPException(status_code=503, detail="Sessão DB requerida")

        repo = DatabaseRepository(db)
        row = repo.get_project_file(uuid.UUID(file_id))
        if not row or str(row.project_id) != project_id:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")

        path = Path(row.storage_path)
        if not path.is_file():
            alt = PROJECTS_DATA_DIR / project_id / row.filename
            if alt.is_file():
                path = alt
            else:
                raise HTTPException(status_code=404, detail="Arquivo não encontrado no disco")

        ext = path.suffix.lower()
        image_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
        }

        if ext in image_types:
            return path.read_bytes(), image_types[ext], row.filename

        if ext == ".pdf":
            try:
                import fitz
            except ImportError as exc:
                raise HTTPException(status_code=503, detail="PyMuPDF não disponível") from exc
            doc = fitz.open(path)
            try:
                if len(doc) == 0:
                    raise HTTPException(status_code=422, detail="PDF vazio")
                page = doc.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                png_name = Path(row.filename).stem + "_preview.png"
                return pix.tobytes("png"), "image/png", png_name
            finally:
                doc.close()

        raise HTTPException(status_code=415, detail="Preview disponível apenas para imagens e PDF")

    def delete_project_file(
        self,
        project_id: str,
        file_id: str,
        db: Optional[Session] = None,
    ) -> dict:
        from core.database.repository import DatabaseRepository

        if db is None:
            raise HTTPException(status_code=503, detail="Sessão DB requerida")

        repo = DatabaseRepository(db)
        row = repo.get_project_file(uuid.UUID(file_id))
        if not row or str(row.project_id) != project_id:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")

        path = Path(row.storage_path)
        if path.exists():
            path.unlink(missing_ok=True)

        from core.project_rag.project_rag import remove_project_file_index

        remove_project_file_index(project_id, row.storage_path)

        delete_project_file_record(file_id, db=db)
        db.commit()
        return {"deleted": True, "id": file_id}

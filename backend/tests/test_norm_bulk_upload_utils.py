"""Testes — extração de arquivos multipart."""

from starlette.datastructures import FormData, UploadFile
from io import BytesIO

from core.knowledge.norm_bulk.upload_utils import extract_upload_files, is_upload_file


def test_is_upload_file_starlette_not_fastapi():
    upload = UploadFile(file=BytesIO(b"pdf"), filename="NBR-6118.pdf")
    assert is_upload_file(upload) is True


def test_extract_upload_files_from_form():
    f1 = UploadFile(file=BytesIO(b"a"), filename="a.pdf")
    f2 = UploadFile(file=BytesIO(b"b"), filename="b.pdf")
    form = FormData([("files", f1), ("files", f2), ("force", "true")])
    files = extract_upload_files(form)
    assert len(files) == 2
    assert files[0].filename == "a.pdf"

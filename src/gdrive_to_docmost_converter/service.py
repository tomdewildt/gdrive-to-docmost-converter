import io
import re
import time
import zipfile

from loguru import logger

from gdrive_to_docmost_converter.clean import clean_markdown
from gdrive_to_docmost_converter.docmost import DocmostClient
from gdrive_to_docmost_converter.drive import DriveClient, DriveItem
from gdrive_to_docmost_converter.enrich import enrich_markdown
from gdrive_to_docmost_converter.exceptions import ImportFailedError, ImportTimeoutError

_DOCMOST_IMPORT_JOB_TIMEOUT_SECONDS = 300
_DOCMOST_IMPORT_JOB_POLL_INTERVAL_SECONDS = 1


class ConversionService:
    def __init__(self, drive_client: DriveClient, docmost_client: DocmostClient) -> None:
        self._drive_client = drive_client
        self._docmost_client = docmost_client

    def convert_doc(self, space_id: str, doc_id: str) -> None:
        document = self._drive_client.get_item(doc_id)

        files = self._convert_document(document, prefix="")

        self._import_into_docmost(document.name, files, space_id)

    def convert_folder(self, space_id: str, folder_id: str) -> None:
        folder = self._drive_client.get_item(folder_id)
        folder_name = folder.name.replace("/", "-")

        files = self._convert_folder(folder.id, prefix=f"{folder_name}/")
        if files:
            # Docmost skips a lone root folder in the zip, a sibling page of the same name keeps it as parent page.
            files[f"{folder_name}.md"] = f"# {folder.name}\n".encode()

        self._import_into_docmost(folder.name, files, space_id)

    def _convert_document(self, document: DriveItem, prefix: str) -> dict[str, bytes]:
        logger.info("Converting '{name}'", name=document.name)

        image_directory = self._to_filename_slug(document.name)
        cleaned_markdown, markdown_images = clean_markdown(
            self._drive_client.export_markdown(document.id),
            document.name,
            image_directory,
        )
        exported_html, html_images = self._unzip_html_export(self._drive_client.export_html(document.id))
        enriched_markdown, html_image_filenames = enrich_markdown(cleaned_markdown, exported_html, image_directory)

        files = {f"{prefix}{document.name.replace('/', '-')}.md": enriched_markdown.encode()}
        for image_filename, image in markdown_images.items():
            files[f"{prefix}{image_directory}/{image_filename}"] = image
        for html_image_name, image_filename in html_image_filenames.items():
            files[f"{prefix}{image_directory}/{image_filename}"] = html_images[html_image_name]

        return files

    def _convert_folder(self, folder_id: str, prefix: str) -> dict[str, bytes]:
        files: dict[str, bytes] = {}

        for item in self._drive_client.get_folder(folder_id):
            if item.is_folder:
                files |= self._convert_folder(item.id, f"{prefix}{item.name.replace('/', '-')}/")
            elif item.is_document:
                files |= self._convert_document(item, prefix)

        return files

    def _import_into_docmost(self, name: str, files: dict[str, bytes], space_id: str) -> None:
        if not files:
            logger.warning("No documents found in '{name}', skipping import", name=name)
            return

        import_job_id = self._docmost_client.import_zip(
            space_id=space_id,
            filename=f"{self._to_filename_slug(name)}.zip",
            content=self._zip_files(files),
        )

        deadline = time.monotonic() + _DOCMOST_IMPORT_JOB_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            import_job = self._docmost_client.get_import_job(import_job_id)
            if import_job["status"] == "success":
                logger.info("Imported '{name}' ({file_count} files)", name=name, file_count=len(files))
                return
            if import_job["status"] == "failed":
                raise ImportFailedError(import_job_id, import_job.get("errorMessage"))
            time.sleep(_DOCMOST_IMPORT_JOB_POLL_INTERVAL_SECONDS)

        raise ImportTimeoutError(import_job_id)

    @staticmethod
    def _to_filename_slug(name: str) -> str:
        # Replace every run of characters other than letters, digits, "_" and "-" with one "-", then lowercase
        return re.sub(r"[^\w-]+", "-", name).strip("-").lower() or "untitled"

    @staticmethod
    def _unzip_html_export(export: bytes) -> tuple[str, dict[str, bytes]]:
        html = ""
        images: dict[str, bytes] = {}

        with zipfile.ZipFile(io.BytesIO(export)) as archive:
            for entry in archive.namelist():
                if entry.endswith(".html"):
                    html = archive.read(entry).decode()
                elif entry.startswith("images/"):
                    images[entry.removeprefix("images/")] = archive.read(entry)

        return html, images

    @staticmethod
    def _zip_files(files: dict[str, bytes]) -> bytes:
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, "w") as archive:
            for path, content in files.items():
                archive.writestr(path, content)

        return buffer.getvalue()

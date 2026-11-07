import argparse

from gdrive_to_docmost_converter.config import config
from gdrive_to_docmost_converter.docmost import create_docmost_client
from gdrive_to_docmost_converter.drive import create_drive_client, extract_google_drive_file_id
from gdrive_to_docmost_converter.exceptions import UnknownCommandError
from gdrive_to_docmost_converter.service import ConversionService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Google Docs to Docmost pages")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doc_parser = subparsers.add_parser("doc", help="Convert a single Google Doc")
    doc_parser.add_argument("id", metavar="ID_OR_URL", help="Google Doc id or URL")

    folder_parser = subparsers.add_parser("folder", help="Convert a Google Drive folder recursively")
    folder_parser.add_argument("id", metavar="ID_OR_URL", help="Google Drive folder id or URL")

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    docmost_client = create_docmost_client(config)
    service = ConversionService(create_drive_client(config), docmost_client)
    space_id = docmost_client.get_space_id(config.DOCMOST_SPACE_SLUG)

    match args.command:
        case "doc":
            service.convert_doc(space_id, extract_google_drive_file_id(args.id))
        case "folder":
            service.convert_folder(space_id, extract_google_drive_file_id(args.id))
        case _:
            raise UnknownCommandError(args.command)


if __name__ == "__main__":
    main()

import base64
import re

# Image embedded as a reference definition: [image1]: <data:image/png;base64,iVBOR...> "Chart title"
_EMBEDDED_IMAGE_DEFINITION = re.compile(r"^\[(\w+)\]: <data:image/(\w+);base64,([^>]+)>(.*)$", re.MULTILINE)

# Table of contents entry, a link to a heading with a tab and page number: > [**Intro\t1**](#intro)
_TABLE_OF_CONTENTS_ENTRY = re.compile(r"^(?:> )*\[\**[^\]\n]*\t\d+\**\]\(#[\w-]+\)[ \t]*\n?", re.MULTILINE)

# Link to a heading in the same document: [the intro](#intro)
_LINK_TO_HEADING = re.compile(r"\[([^\]\n]*)\]\(#[\w-]+\)")

# Anchor id Google adds to headings that are linked to: # Intro {#intro}
_HEADING_ANCHOR_ID = re.compile(r"[ \t]*\{#[\w-]+\}[ \t]*$", re.MULTILINE)

# Footnote text at the bottom of the document: [^1]: Source
_FOOTNOTE_DEFINITION = re.compile(r"^\[\^(\w+)\]:\s*", re.MULTILINE)

# Footnote marker in the text: Claim[^1]
_FOOTNOTE_REFERENCE = re.compile(r"\[\^(\w+)\]")

# Ticked checklist item that Google also strikes through: - [x] ~~Done~~
_STRUCK_THROUGH_CHECKED_ITEM = re.compile(r"^(\s*[-*] \[x\] )~~(.*)~~", re.MULTILINE)

# Three or more newlines in a row, left behind by removed lines
_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


def clean_markdown(markdown: str, title: str, image_directory: str) -> tuple[str, dict[str, bytes]]:
    markdown_with_image_files, images = _extract_embedded_images(markdown, image_directory)
    markdown_without_table_of_contents = _remove_table_of_contents(markdown_with_image_files)
    markdown_without_heading_links = _convert_links_to_headings_to_text(markdown_without_table_of_contents)
    markdown_without_heading_ids = _remove_heading_anchor_ids(markdown_without_heading_links)
    markdown_with_superscript_footnotes = _convert_footnotes_to_superscript(markdown_without_heading_ids)
    markdown_without_struck_items = _remove_strikethrough_from_checked_items(markdown_with_superscript_footnotes)
    cleaned_markdown = _remove_extra_blank_lines(markdown_without_struck_items)

    # Docmost takes the page title from a leading H1 and drops it from the body
    return f"# {title}\n\n{cleaned_markdown.strip()}\n", images


def _extract_embedded_images(markdown: str, image_directory: str) -> tuple[str, dict[str, bytes]]:
    """Google's markdown export embeds every image as a base64 data URI in a reference definition."""
    images: dict[str, bytes] = {}

    def convert_to_image_file_reference(match: re.Match[str]) -> str:
        image_name, image_type, base64_data, title_suffix = match.groups()
        image_filename = f"{image_name}.{image_type}"
        images[image_filename] = base64.b64decode(base64_data)
        return f"[{image_name}]: {image_directory}/{image_filename}{title_suffix}"

    return _EMBEDDED_IMAGE_DEFINITION.sub(convert_to_image_file_reference, markdown), images


def _remove_table_of_contents(markdown: str) -> str:
    """Docmost shows its own outline, so Google's table of contents is noise."""
    return _TABLE_OF_CONTENTS_ENTRY.sub("", markdown)


def _convert_links_to_headings_to_text(markdown: str) -> str:
    """Docmost can't link to a heading, so the link text is kept as plain text."""
    return _LINK_TO_HEADING.sub(r"\1", markdown)


def _remove_heading_anchor_ids(markdown: str) -> str:
    """Docmost would show the {#id} anchors literally."""
    return _HEADING_ANCHOR_ID.sub("", markdown)


def _convert_footnotes_to_superscript(markdown: str) -> str:
    """Docmost has no footnotes, the markdown importer would show the [^1] syntax literally."""
    markdown_with_definitions = _FOOTNOTE_DEFINITION.sub(r"<sup>\1</sup> ", markdown)

    return _FOOTNOTE_REFERENCE.sub(r"<sup>\1</sup>", markdown_with_definitions)


def _remove_strikethrough_from_checked_items(markdown: str) -> str:
    """Google strikes through ticked checklist items, Docmost already marks them as done with a ticked checkbox."""
    return _STRUCK_THROUGH_CHECKED_ITEM.sub(r"\1\2", markdown)


def _remove_extra_blank_lines(markdown: str) -> str:
    """The removed table of contents leaves a run of blank lines behind, one blank line separates blocks."""
    return _EXTRA_BLANK_LINES.sub("\n\n", markdown)

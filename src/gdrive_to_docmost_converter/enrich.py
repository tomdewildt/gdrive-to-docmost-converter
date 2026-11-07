import bisect
import difflib
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag
from bs4.element import Comment, NavigableString

# A word or a single symbol: "Hello, world" is "Hello", ",", "world"
_MATCHING_WORD = re.compile(r"\w+|[^\w\s]")
_MATCHING_IMAGE_PLACEHOLDER = "￼"
_MATCHING_HORIZONTAL_RULE_PLACEHOLDER = "⸻"

_INSERTION_ORDER_CLOSING_TAG = 0
_INSERTION_ORDER_OPENING_TAG = 1
_INSERTION_ORDER_BLOCK = 2

_HTML_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_HTML_BLOCK_TAGS = {"p", "li", "tr", "td", "th", "hr", "table", "ul", "ol"} | _HTML_HEADING_TAGS
_HTML_TAGS_WITHOUT_USER_STYLING = {"a"} | _HTML_HEADING_TAGS
_HTML_GOOGLE_DEFAULT_TEXT_COLORS = {"#000000"}
_HTML_GOOGLE_DEFAULT_BACKGROUND_COLORS = {"#ffffff", "transparent"}
_HTML_GOOGLE_LINK_COLORS = {"#1155cc", "#0000ee"}

# Markdown syntax at the start of a line: "## ", "> ", "- ", "1. ", "- [x] "
_MARKDOWN_LINE_PREFIX = re.compile(r"[ \t]*(?:(?:#{1,6}|>)[ \t]+)*(?:(?:[-*+]|\d+[.)])[ \t]+(?:\[[ xX]\][ \t]+)?)?")

# Horizontal rule: "---", "***" or "___"
_MARKDOWN_HORIZONTAL_RULE = re.compile(r"^ {0,3}(?:-{3,}|\*{3,}|_{3,})[ \t]*$")

# Line of a table that only separates the header: "| :---- | :---- |"
_MARKDOWN_TABLE_SEPARATOR = re.compile(r"^[\s|:-]*$")

# Reference definition: "[image1]: doc/image1.png"
_MARKDOWN_REFERENCE_DEFINITION = re.compile(r"^\[[^\]]+\]:\s")

# Inline syntax that is not text: an image "![alt][image1]", an escape "\[", math "$x$", code "`x`", a tag "<sup>",
# link brackets and targets, "**", "*", "~~" and "|"
_MARKDOWN_INLINE_SYNTAX = re.compile(
    r"(?P<image>!\[[^\]\n]*\](?:\[[^\]\n]*\]|\([^)\n]*\)))"
    r"|\\\S|\$[^$\n]+\$|`[^`\n]+`|<[^>\n]+>|\]\([^)\n]*\)|\]\[[^\]\n]*\]|\*\*|\*|~~|\[|\]|\|"
)


@dataclass
class _ParsedHtmlInlineElement:
    plain_text_start: int
    plain_text_end: int
    opening_tags: str
    closing_tags: str


@dataclass
class _ParsedHtmlBlockElement:
    plain_text_position: int
    image_filename: str | None = None  # None when the block is an empty line, not an image.


@dataclass
class _ParsedHtml:
    plain_text_characters: list[str]
    inline_elements: list[_ParsedHtmlInlineElement]
    block_elements: list[_ParsedHtmlBlockElement]


@dataclass
class _ParsedMarkdown:
    plain_text_characters: list[str]
    original_markdown_positions: list[int]  # For every plain text character, its position in the original markdown.


@dataclass
class _WordMatches:
    html_word_starts: list[int]
    markdown_words: list[re.Match[str]]
    original_markdown_positions: list[int]
    markdown_word_by_html_word: list[int | None]  # For every HTML word the index of the same markdown word.


@dataclass(order=True)
class _MarkdownInsertion:
    original_markdown_position: int
    order: tuple[int, ...]
    text: str


def enrich_markdown(markdown: str, html: str, image_directory: str) -> tuple[str, dict[str, str]]:
    """Adds the styling, images and empty lines that the markdown lacks, taken from the HTML of the same document.

    Both are reduced to plain text and their words are matched, so everything is placed by its position in the
    whole document rather than by searching for its text. Styled text gets tags around the matching markdown
    words, images and empty lines are added as paragraphs after the last matching word."""
    parsed_html = _read_html(html)
    parsed_markdown = _read_markdown(markdown)
    word_matches = _build_word_matches(parsed_html, parsed_markdown)

    inline_element_markdown_insertions = _build_inline_element_markdown_insertions(
        parsed_html.inline_elements,
        word_matches,
    )
    block_element_markdown_insertions, html_image_filenames = _build_block_element_markdown_insertions(
        parsed_html.block_elements,
        word_matches,
        markdown,
        image_directory,
    )

    enriched_markdown = _apply_markdown_insertions(
        markdown,
        inline_element_markdown_insertions + block_element_markdown_insertions,
    )

    return enriched_markdown, html_image_filenames


def _read_html(html: str) -> _ParsedHtml:
    """Parses the HTML body into plain text, inline elements and block elements."""
    body = BeautifulSoup(html, "html.parser").body
    if body:
        return _read_html_tag(body, plain_text_position=0, should_preserve_styling=True)

    return _ParsedHtml([], [], [])


def _read_html_tag(tag: Tag, plain_text_position: int, should_preserve_styling: bool) -> _ParsedHtml:
    """Reads the children of a tag, counting positions from where the tag starts in the plain text."""
    plain_text_characters: list[str] = []
    inline_elements: list[_ParsedHtmlInlineElement] = []
    block_elements: list[_ParsedHtmlBlockElement] = []

    for child in tag.children:
        child_plain_text_position = plain_text_position + len(plain_text_characters)

        if isinstance(child, NavigableString):
            if not isinstance(child, Comment):
                plain_text_characters.extend(str(child))
            continue
        if not isinstance(child, Tag):
            continue

        # Headers, footers, footnotes and comments live in divs, footnote and comment markers are links.
        if child.name == "div" or str(child.get("href", "")).startswith(("#ftnt", "#cmnt")):
            continue

        if child.name == "img":
            # Equations are unstyled images in the HTML, the markdown has them as LaTeX instead.
            if child.get("style"):
                image_filename = str(child.get("src", "")).removeprefix("images/")
                block_elements.append(_ParsedHtmlBlockElement(child_plain_text_position, image_filename))
                plain_text_characters.append(_MATCHING_IMAGE_PLACEHOLDER)
        elif child.name == "hr":
            plain_text_characters.append(_MATCHING_HORIZONTAL_RULE_PLACEHOLDER)
        elif tag.name == "body" and child.name == "p" and not child.get_text().strip() and not child.find("img"):
            block_elements.append(_ParsedHtmlBlockElement(child_plain_text_position))
        else:
            should_preserve_child_styling = (
                should_preserve_styling and child.name not in _HTML_TAGS_WITHOUT_USER_STYLING
            )
            parsed_child = _read_html_tag(
                child,
                plain_text_position=child_plain_text_position,
                should_preserve_styling=should_preserve_child_styling,
            )

            plain_text_characters.extend(parsed_child.plain_text_characters)
            inline_elements.extend(parsed_child.inline_elements)
            block_elements.extend(parsed_child.block_elements)

            if should_preserve_styling and child.name == "span":
                inline_element = _build_inline_element(
                    parsed_child.plain_text_characters,
                    child_plain_text_position,
                    str(child.get("style", "")),
                )
                if inline_element:
                    inline_elements.append(inline_element)

            if child.name in _HTML_BLOCK_TAGS:
                plain_text_characters.append("\n")

    return _ParsedHtml(plain_text_characters, inline_elements, block_elements)


def _build_inline_element(
    plain_text_characters: list[str],
    plain_text_position: int,
    style: str,
) -> _ParsedHtmlInlineElement | None:
    """Builds the element for a span whose characters begin at plain_text_position, trimmed of surrounding spaces."""
    css_properties = {
        key.strip().lower(): value.strip().lower()
        for key, _, value in (part.partition(":") for part in style.split(";"))
        if value
    }
    tags = _build_html_tags_with_styling(css_properties)

    text = "".join(plain_text_characters)
    trimmed_text = text.strip()
    if not tags or not trimmed_text:
        return None

    trimmed_plain_text_position = plain_text_position + len(text) - len(text.lstrip())
    opening_tags = "".join(opening_tag for opening_tag, _ in tags)
    closing_tags = "".join(closing_tag for _, closing_tag in reversed(tags))

    return _ParsedHtmlInlineElement(
        trimmed_plain_text_position,
        trimmed_plain_text_position + len(trimmed_text),
        opening_tags,
        closing_tags,
    )


def _build_html_tags_with_styling(css_properties: dict[str, str]) -> list[tuple[str, str]]:
    """Returns the opening and closing tags for the user's styling in a span's CSS: underline, highlight, colour, subscript and superscript."""  # noqa: E501
    is_underlined = "underline" in css_properties.get("text-decoration", "")
    color = css_properties.get("color")
    # Google styles links and chips with a blue underline on the span around them, that is not user styling.
    if is_underlined and color in _HTML_GOOGLE_LINK_COLORS:
        return []

    tags: list[tuple[str, str]] = []
    if is_underlined:
        tags.append(("<u>", "</u>"))

    background_color = css_properties.get("background-color")
    if background_color and background_color not in _HTML_GOOGLE_DEFAULT_BACKGROUND_COLORS:
        tags.append((f'<mark style="background-color:{background_color}">', "</mark>"))
    if color and color not in _HTML_GOOGLE_DEFAULT_TEXT_COLORS:
        tags.append((f'<span style="color:{color}">', "</span>"))

    vertical_align = css_properties.get("vertical-align")
    if vertical_align == "sub":
        tags.append(("<sub>", "</sub>"))
    elif vertical_align == "super":
        tags.append(("<sup>", "</sup>"))

    return tags


def _read_markdown(markdown: str) -> _ParsedMarkdown:
    """Parses the markdown into plain text, keeping each character's position in the original markdown."""
    characters_and_positions: list[tuple[str, int]] = []

    is_in_code_block = False
    line_start_original_markdown_position = 0
    for line in markdown.splitlines(keepends=True):
        line_content = line.rstrip("\n")
        if line_content.lstrip().startswith("```"):
            is_in_code_block = not is_in_code_block
        elif not is_in_code_block:
            characters_and_positions.extend(_read_markdown_line(line_content, line_start_original_markdown_position))
        characters_and_positions.append(("\n", line_start_original_markdown_position + len(line_content)))
        line_start_original_markdown_position += len(line)

    return _ParsedMarkdown(
        plain_text_characters=[character for character, _ in characters_and_positions],
        original_markdown_positions=[
            original_markdown_position for _, original_markdown_position in characters_and_positions
        ],
    )


def _read_markdown_line(line: str, line_start_original_markdown_position: int) -> list[tuple[str, int]]:
    """Returns the plain text characters of one markdown line, each with its original markdown position."""
    if _MARKDOWN_HORIZONTAL_RULE.match(line):
        return [(_MATCHING_HORIZONTAL_RULE_PLACEHOLDER, line_start_original_markdown_position)]

    if _MARKDOWN_REFERENCE_DEFINITION.match(line) or _MARKDOWN_TABLE_SEPARATOR.match(line):
        return []

    characters_and_positions: list[tuple[str, int]] = []
    index_in_line = _MARKDOWN_LINE_PREFIX.match(line).end()  # pyright: ignore[reportOptionalMemberAccess]
    for syntax in _MARKDOWN_INLINE_SYNTAX.finditer(line, index_in_line):
        characters_and_positions.extend(
            (line[index], line_start_original_markdown_position + index)
            for index in range(index_in_line, syntax.start())
        )
        if syntax.group("image"):
            characters_and_positions.append(
                (_MATCHING_IMAGE_PLACEHOLDER, line_start_original_markdown_position + syntax.start())
            )
        index_in_line = syntax.end()

    characters_and_positions.extend(
        (line[index], line_start_original_markdown_position + index) for index in range(index_in_line, len(line))
    )

    return characters_and_positions


def _build_word_matches(parsed_html: _ParsedHtml, parsed_markdown: _ParsedMarkdown) -> _WordMatches:
    """Matches the words of both plain texts and records which markdown word each HTML word is."""
    html_words = list(_MATCHING_WORD.finditer("".join(parsed_html.plain_text_characters)))
    markdown_words = list(_MATCHING_WORD.finditer("".join(parsed_markdown.plain_text_characters)))

    matcher = difflib.SequenceMatcher(
        None,
        [word.group() for word in html_words],
        [word.group() for word in markdown_words],
        autojunk=False,
    )

    markdown_word_by_html_word: list[int | None] = [None] * len(html_words)
    for matching_block in matcher.get_matching_blocks():
        for index in range(matching_block.size):
            markdown_word_by_html_word[matching_block.a + index] = matching_block.b + index

    html_word_starts = [word.start() for word in html_words]
    return _WordMatches(
        html_word_starts,
        markdown_words,
        parsed_markdown.original_markdown_positions,
        markdown_word_by_html_word,
    )


def _build_inline_element_markdown_insertions(
    inline_elements: list[_ParsedHtmlInlineElement],
    word_matches: _WordMatches,
) -> list[_MarkdownInsertion]:
    """Builds the tags to insert around each inline element's text in the markdown."""
    markdown_insertions: list[_MarkdownInsertion] = []

    for inline_element in inline_elements:
        original_markdown_positions = _find_original_markdown_positions_for_html_plain_text(
            inline_element.plain_text_start,
            inline_element.plain_text_end,
            word_matches,
        )

        # Only style text that is uninterrupted in the markdown, never across syntax like "**" or a link.
        if (
            original_markdown_positions is None
            or original_markdown_positions[-1] - original_markdown_positions[0] != len(original_markdown_positions) - 1
        ):
            continue

        markdown_insertions.append(
            _MarkdownInsertion(
                original_markdown_positions[0],
                (_INSERTION_ORDER_OPENING_TAG,),
                inline_element.opening_tags,
            )
        )
        markdown_insertions.append(
            _MarkdownInsertion(
                original_markdown_positions[-1] + 1,
                (_INSERTION_ORDER_CLOSING_TAG,),
                inline_element.closing_tags,
            )
        )

    return markdown_insertions


def _build_block_element_markdown_insertions(
    block_elements: list[_ParsedHtmlBlockElement],
    word_matches: _WordMatches,
    markdown: str,
    image_directory: str,
) -> tuple[list[_MarkdownInsertion], dict[str, str]]:
    """Builds the image and empty line paragraphs the markdown lacks, and the image files they need."""
    markdown_insertions: list[_MarkdownInsertion] = []
    html_image_filenames: dict[str, str] = {}

    for block_element in block_elements:
        next_html_word = bisect.bisect_left(word_matches.html_word_starts, block_element.plain_text_position)
        if block_element.image_filename is not None:
            if word_matches.markdown_word_by_html_word[next_html_word] is not None:
                continue
            markdown_image_filename = f"html-{block_element.image_filename}"
            html_image_filenames[block_element.image_filename] = markdown_image_filename
            text = f"\n\n![]({image_directory}/{markdown_image_filename})"
        else:
            # Empty lines at the very start or end of the document are left out.
            if next_html_word in (0, len(word_matches.html_word_starts)):
                continue
            text = "\n\n<p></p>"

        original_markdown_position = _find_original_markdown_position_of_block_end(
            markdown,
            _find_original_markdown_position_before_html_word(next_html_word, word_matches),
        )

        # Blocks keep their document order. An empty line adds no text, so it shares its position with the
        # image that follows it and has to sort first.
        markdown_insertions.append(
            _MarkdownInsertion(
                original_markdown_position,
                (_INSERTION_ORDER_BLOCK, block_element.plain_text_position, block_element.image_filename is not None),
                text,
            )
        )

    return markdown_insertions, html_image_filenames


def _find_original_markdown_positions_for_html_plain_text(
    plain_text_start: int,
    plain_text_end: int,
    word_matches: _WordMatches,
) -> list[int] | None:
    """Returns the original markdown positions of a piece of HTML plain text, or None when the markdown lacks it."""
    html_word_starts = word_matches.html_word_starts
    first_html_word = bisect.bisect_right(html_word_starts, plain_text_start) - 1
    last_html_word = bisect.bisect_right(html_word_starts, plain_text_end - 1) - 1
    first_markdown_word = word_matches.markdown_word_by_html_word[first_html_word]
    if first_markdown_word is None:
        return None

    for html_word in range(first_html_word, last_html_word + 1):
        if word_matches.markdown_word_by_html_word[html_word] != first_markdown_word + html_word - first_html_word:
            return None

    last_markdown_word = first_markdown_word + last_html_word - first_html_word
    markdown_plain_text_start = (
        word_matches.markdown_words[first_markdown_word].start() + plain_text_start - html_word_starts[first_html_word]
    )
    markdown_plain_text_end = (
        word_matches.markdown_words[last_markdown_word].start() + plain_text_end - html_word_starts[last_html_word]
    )

    return word_matches.original_markdown_positions[markdown_plain_text_start:markdown_plain_text_end]


def _find_original_markdown_position_before_html_word(html_word: int, word_matches: _WordMatches) -> int:
    """Returns the original markdown position of the last word before the HTML word that the markdown also has."""
    for previous_html_word in range(html_word - 1, -1, -1):
        markdown_word = word_matches.markdown_word_by_html_word[previous_html_word]
        if markdown_word is not None:
            return word_matches.original_markdown_positions[word_matches.markdown_words[markdown_word].end() - 1]
    return 0


def _find_original_markdown_position_of_block_end(markdown: str, original_markdown_position: int) -> int:
    """Returns where the markdown block (paragraph, list or table) containing the position ends."""
    block_end_position = markdown.find("\n\n", original_markdown_position)

    return len(markdown.rstrip("\n")) if block_end_position == -1 else block_end_position


def _apply_markdown_insertions(markdown: str, markdown_insertions: list[_MarkdownInsertion]) -> str:
    """Returns the markdown with all insertions added, in order of position."""
    parts: list[str] = []

    previous_original_markdown_position = 0
    for markdown_insertion in sorted(markdown_insertions):
        parts.append(markdown[previous_original_markdown_position : markdown_insertion.original_markdown_position])
        parts.append(markdown_insertion.text)
        previous_original_markdown_position = markdown_insertion.original_markdown_position

    parts.append(markdown[previous_original_markdown_position:])

    return "".join(parts)

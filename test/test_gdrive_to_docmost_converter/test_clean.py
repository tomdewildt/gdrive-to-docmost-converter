import base64

from gdrive_to_docmost_converter.clean import clean_markdown


class TestCleanMarkdown:
    def test_clean_markdown_prepends_title_heading(self) -> None:
        # Act
        cleaned_markdown, _ = clean_markdown("# Heading 1\n\nText\n", "My Doc", "my-doc")

        # Assert
        assert cleaned_markdown == "# My Doc\n\n# Heading 1\n\nText\n"

    def test_clean_markdown_extracts_embedded_images_to_files(self) -> None:
        # Arrange
        base64_data = base64.b64encode(b"jpeg-bytes").decode()
        markdown = f'![][image1]\n\n[image1]: <data:image/jpeg;base64,{base64_data}> "Chart"\n'

        # Act
        cleaned_markdown, images = clean_markdown(markdown, "Doc", "doc")

        # Assert
        assert images == {"image1.jpeg": b"jpeg-bytes"}
        assert '[image1]: doc/image1.jpeg "Chart"' in cleaned_markdown

    def test_clean_markdown_removes_table_of_contents(self) -> None:
        # Arrange
        markdown = "[**Intro\t1**](#intro)\n\n> > [Details\t2](#details)\n\nBody\n"

        # Act
        cleaned_markdown, _ = clean_markdown(markdown, "Doc", "doc")

        # Assert
        assert cleaned_markdown == "# Doc\n\nBody\n"

    def test_clean_markdown_converts_links_to_headings_to_text_and_removes_heading_anchor_ids(self) -> None:
        # Arrange
        markdown = "# Intro {#intro}\n\nSee [the intro](#intro) or [Google](https://google.com).\n"

        # Act
        cleaned_markdown, _ = clean_markdown(markdown, "Doc", "doc")

        # Assert
        assert cleaned_markdown == "# Doc\n\n# Intro\n\nSee the intro or [Google](https://google.com).\n"

    def test_clean_markdown_converts_footnotes_to_superscript(self) -> None:
        # Arrange
        markdown = "Claim[^1]\n\n[^1]:  Source\n"

        # Act
        cleaned_markdown, _ = clean_markdown(markdown, "Doc", "doc")

        # Assert
        assert cleaned_markdown == "# Doc\n\nClaim<sup>1</sup>\n\n<sup>1</sup> Source\n"

    def test_clean_markdown_removes_strikethrough_from_checked_items(self) -> None:
        # Arrange
        markdown = "- [x] ~~Done~~  \n- [ ] ~~Open but struck~~\n"

        # Act
        cleaned_markdown, _ = clean_markdown(markdown, "Doc", "doc")

        # Assert
        assert cleaned_markdown == "# Doc\n\n- [x] Done  \n- [ ] ~~Open but struck~~\n"

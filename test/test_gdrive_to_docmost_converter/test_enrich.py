from gdrive_to_docmost_converter.clean import clean_markdown
from gdrive_to_docmost_converter.enrich import enrich_markdown

from .conftest import BuildHtmlDocument, BuildHtmlSpan


class TestEnrichMarkdown:
    def test_enrich_markdown_applies_styles_from_html(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document(
            build_html_span("Under", "text-decoration:underline"),
            build_html_span("Marked", "background-color:#ffff00"),
            build_html_span("Red", "color:#ff0000"),
            build_html_span("Low", "vertical-align:sub") + " " + build_html_span("High", "vertical-align:super"),
        )
        markdown = "Under\n\nMarked\n\nRed\n\nLow High\n"

        # Act
        enriched_markdown, _ = enrich_markdown(markdown, html, "doc")

        # Assert
        assert enriched_markdown == (
            "<u>Under</u>\n\n"
            '<mark style="background-color:#ffff00">Marked</mark>\n\n'
            '<span style="color:#ff0000">Red</span>\n\n'
            "<sub>Low</sub> <sup>High</sup>\n"
        )

    def test_enrich_markdown_styles_the_occurrence_at_the_same_position(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document(
            build_html_span("Repeat this word"),
            build_html_span("Other text"),
            build_html_span("Repeat this ") + build_html_span("word", "text-decoration:underline"),
        )
        markdown = "Repeat this word\n\nOther text\n\nRepeat this word\n"

        # Act
        enriched_markdown, _ = enrich_markdown(markdown, html, "doc")

        # Assert
        assert enriched_markdown == "Repeat this word\n\nOther text\n\nRepeat this <u>word</u>\n"

    def test_enrich_markdown_skips_styled_text_interrupted_by_markdown_syntax(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document(build_html_span("half bold", "text-decoration:underline"))
        markdown = "half **bold**\n"

        # Act
        enriched_markdown, _ = enrich_markdown(markdown, html, "doc")

        # Assert
        assert enriched_markdown == markdown

    def test_enrich_markdown_ignores_link_styling(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document(
            build_html_span('<a href="https://example.com">Example</a>', "text-decoration:underline;color:#1155cc")
        )
        markdown = "[Example](https://example.com)\n"

        # Act
        enriched_markdown, _ = enrich_markdown(markdown, html, "doc")

        # Assert
        assert enriched_markdown == markdown

    def test_enrich_markdown_inserts_images_missing_from_markdown(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document(
            build_html_span("Photo"),
            '<img src="images/image1.png" style="width: 10px">',
            build_html_span("Drawing"),
            '<img src="images/image2.png" style="width: 10px">',
            build_html_span("End"),
        )
        markdown = "Photo\n\n![][image1]\n\nDrawing\n\nEnd\n"

        # Act
        enriched_markdown, html_image_filenames = enrich_markdown(markdown, html, "doc")

        # Assert
        assert html_image_filenames == {"image2.png": "html-image2.png"}
        assert enriched_markdown == "Photo\n\n![][image1]\n\nDrawing\n\n![](doc/html-image2.png)\n\nEnd\n"

    def test_enrich_markdown_does_not_insert_equation_images(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document(build_html_span("Formula"), '<img src="images/image1.png">')
        markdown = "Formula\n\n$x=1$\n"

        # Act
        enriched_markdown, html_image_filenames = enrich_markdown(markdown, html, "doc")

        # Assert
        assert html_image_filenames == {}
        assert enriched_markdown == markdown

    def test_enrich_markdown_restores_empty_lines_between_blocks(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document("", build_html_span("First"), "", "", build_html_span("Second"), "")
        markdown = "First\n\nSecond\n"

        # Act
        enriched_markdown, _ = enrich_markdown(markdown, html, "doc")

        # Assert
        assert enriched_markdown == "First\n\n<p></p>\n\n<p></p>\n\nSecond\n"

    def test_enrich_markdown_places_empty_lines_after_horizontal_rule(self) -> None:
        # Arrange
        html = "<html><body><p><span>Above</span></p><hr><p></p><p><span>Below</span></p></body></html>"
        markdown = "Above\n\n---\n\nBelow\n"

        # Act
        enriched_markdown, _ = enrich_markdown(markdown, html, "doc")

        # Assert
        assert enriched_markdown == "Above\n\n---\n\n<p></p>\n\nBelow\n"

    def test_enrich_markdown_matches_expected_markdown_for_real_google_export(
        self,
        google_markdown_export: str,
        google_html_export: str,
        expected_markdown: str,
    ) -> None:
        # Arrange
        cleaned_markdown, _ = clean_markdown(google_markdown_export, "GDrive to Docmost Converter Test", "test-doc")

        # Act
        enriched_markdown, html_image_filenames = enrich_markdown(cleaned_markdown, google_html_export, "test-doc")

        # Assert
        assert html_image_filenames == {"image2.png": "html-image2.png"}
        assert enriched_markdown == expected_markdown

    def test_enrich_markdown_ignores_default_white_background(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document(build_html_span("Plain", "background-color:#ffffff"))
        markdown = "Plain\n"

        # Act
        enriched_markdown, _ = enrich_markdown(markdown, html, "doc")

        # Assert
        assert enriched_markdown == markdown

    def test_enrich_markdown_ignores_header_and_footer_content(self) -> None:
        # Arrange
        html = (
            '<html><body><div><p><img src="images/logo.png" style="width: 10px"></p></div>'
            "<p><span>Body</span></p>"
            '<div><p><span style="text-decoration:underline">Footer</span></p></div></body></html>'
        )
        markdown = "Body\n"

        # Act
        enriched_markdown, html_image_filenames = enrich_markdown(markdown, html, "doc")

        # Assert
        assert html_image_filenames == {}
        assert enriched_markdown == markdown

    def test_enrich_markdown_keeps_spaces_around_styled_text_outside_the_tags(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document(
            build_html_span("Lead") + build_html_span(" Under ", "text-decoration:underline") + build_html_span("tail")
        )
        markdown = "Lead Under tail\n"

        # Act
        enriched_markdown, _ = enrich_markdown(markdown, html, "doc")

        # Assert
        assert enriched_markdown == "Lead <u>Under</u> tail\n"

    def test_enrich_markdown_nests_multiple_styles_of_one_styled_text(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document(build_html_span("Both", "text-decoration:underline;color:#ff0000"))
        markdown = "Both\n"

        # Act
        enriched_markdown, _ = enrich_markdown(markdown, html, "doc")

        # Assert
        assert enriched_markdown == '<u><span style="color:#ff0000">Both</span></u>\n'

    def test_enrich_markdown_closes_styled_text_before_opening_adjacent_styled_text(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document(
            build_html_span("Under", "text-decoration:underline")
            + build_html_span("Marked", "background-color:#ffff00")
        )
        markdown = "UnderMarked\n"

        # Act
        enriched_markdown, _ = enrich_markdown(markdown, html, "doc")

        # Assert
        assert enriched_markdown == '<u>Under</u><mark style="background-color:#ffff00">Marked</mark>\n'

    def test_enrich_markdown_keeps_document_order_of_blocks_inserted_at_same_position(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document(
            build_html_span("Text"), "", '<img src="images/image1.png" style="width: 10px">', "", build_html_span("End")
        )
        markdown = "Text\n\nEnd\n"

        # Act
        enriched_markdown, _ = enrich_markdown(markdown, html, "doc")

        # Assert
        assert enriched_markdown == "Text\n\n<p></p>\n\n![](doc/html-image1.png)\n\n<p></p>\n\nEnd\n"

    def test_enrich_markdown_appends_missing_image_at_end_of_document(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document(build_html_span("Text"), '<img src="images/image1.png" style="width: 10px">')
        markdown = "Text\n"

        # Act
        enriched_markdown, _ = enrich_markdown(markdown, html, "doc")

        # Assert
        assert enriched_markdown == "Text\n\n![](doc/html-image1.png)\n"

    def test_enrich_markdown_skips_styled_text_whose_words_differ_in_markdown(
        self,
        build_html_document: BuildHtmlDocument,
        build_html_span: BuildHtmlSpan,
    ) -> None:
        # Arrange
        html = build_html_document(build_html_span("Alpha beta gamma", "text-decoration:underline"))
        markdown = "Alpha delta gamma\n"

        # Act
        enriched_markdown, _ = enrich_markdown(markdown, html, "doc")

        # Assert
        assert enriched_markdown == markdown

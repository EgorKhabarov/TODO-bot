import html

# noinspection PyPackageRequirements
from telebot.types import Message, TextQuote

from tgbot.utils import html_to_markdown


class PathedMessage(Message):
    @property
    def html_text(self):
        raw_html_text = super().html_text
        return raw_html_text if self.entities else html.escape(raw_html_text, False)

    @property
    def html_caption(self):
        raw_html_caption = super().html_caption
        return (
            raw_html_caption
            if self.caption_entities
            else html.escape(raw_html_caption, False)
        )

    @property
    def markdown_text(self):
        return html_to_markdown(self.html_text)

    @property
    def markdown_caption(self):
        return html_to_markdown(self.html_caption)


class PathedTextQuote(TextQuote):
    @property
    def html_text(self):
        return (
            Message._Message__html_text(self, self.text, self.entities)  # noqa
            if self.entities
            else html.escape(self.text, False)
        )

    @property
    def markdown_text(self):
        return html_to_markdown(self.html_text)

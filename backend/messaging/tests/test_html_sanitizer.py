from django.test import TestCase

from messaging.models import MessageTemplate
from messaging.sanitizers import sanitize_template_html
from messaging.services import render_message


class EmailHtmlSanitizerTests(TestCase):
    def test_sanitizer_removes_scripts_events_iframes_and_javascript_links(self):
        html = (
            '<p onclick="alert(1)">Olá</p>'
            '<script>alert(1)</script>'
            '<iframe srcdoc="<script>alert(1)</script>"></iframe>'
            '<a href="javascript:alert(1)">link</a>'
        )

        sanitized = sanitize_template_html(html)

        self.assertIn("Olá", sanitized)
        self.assertNotIn("onclick", sanitized)
        self.assertNotIn("script", sanitized.lower())
        self.assertNotIn("iframe", sanitized.lower())
        self.assertNotIn("javascript:", sanitized.lower())

    def test_model_clean_sanitizes_email_html_before_save(self):
        template = MessageTemplate.objects.create(
            name="Email inseguro",
            channel=MessageTemplate.Channel.EMAIL,
            email_subject="Teste",
            email_html_body='<p class="ql-align-center injected" onclick="alert(1)">Olá</p><script>alert(1)</script>',
        )
        template.full_clean()
        template.save()
        template.refresh_from_db()

        self.assertIn("ql-align-center", template.email_html_body)
        self.assertNotIn("injected", template.email_html_body)
        self.assertNotIn("onclick", template.email_html_body)
        self.assertNotIn("script", template.email_html_body.lower())

    def test_render_message_sanitizes_rendered_html(self):
        template = MessageTemplate.objects.create(
            name="Email renderizado",
            channel=MessageTemplate.Channel.EMAIL,
            email_subject="Teste",
            email_html_body='<p>Olá {{ nome_contato }}</p><a href="https://example.com" target="_blank">abrir</a>',
        )

        rendered = render_message(template, raw_email="cliente@example.com")

        self.assertIn("Olá", rendered["html"])
        self.assertIn('target="_blank"', rendered["html"])
        self.assertIn('rel="noopener noreferrer"', rendered["html"])

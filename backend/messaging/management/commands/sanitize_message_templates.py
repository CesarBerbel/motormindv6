from django.core.management.base import BaseCommand

from messaging.models import MessageTemplate
from messaging.sanitizers import sanitize_template_html


class Command(BaseCommand):
    help = "Sanitiza corpos HTML existentes de templates de email, sem alterar templates que ja estao seguros."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra quantos templates seriam atualizados, mas nao grava alteracoes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        updated = 0
        scanned = 0

        for template in MessageTemplate.objects.filter(channel=MessageTemplate.Channel.EMAIL).only("id", "email_html_body"):
            scanned += 1
            sanitized_html = sanitize_template_html(template.email_html_body)
            if sanitized_html == (template.email_html_body or ""):
                continue
            updated += 1
            if not dry_run:
                MessageTemplate.objects.filter(pk=template.pk).update(email_html_body=sanitized_html)

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Templates analisados: {scanned}. Templates que seriam sanitizados: {updated}."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Templates analisados: {scanned}. Templates sanitizados: {updated}."))

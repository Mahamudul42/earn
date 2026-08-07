"""Seed the EARN study with the POPROX-style newsletter stimuli and a researcher
login.

Run with:  python manage.py seed_study

Idempotent — safe to run repeatedly. Pass --reset to delete existing
newsletters first.

The newsletter stimuli live in ``apps/study/seed_data/newsletters.json``. They
follow the POPROX newsletter format (https://github.com/Mahamudul42/poprox_newsletter):
a teal masthead, dark-blue section bars, and article rows with a topic label, a
serif headline, a short summary, and a thumbnail. Each stimulus has the fixed
format used in the study — five sections of three articles each — and is built
from real Associated Press articles (headline, summary, image, and link).
"""
import json
import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.study.models import Newsletter

User = get_user_model()

SEED_FILE = (
    Path(__file__).resolve().parent.parent.parent / "seed_data" / "newsletters.json"
)


class Command(BaseCommand):
    help = "Seed POPROX-style newsletter stimuli and create a researcher account."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Delete existing newsletters first."
        )

    def handle(self, *args, **options):
        if options["reset"]:
            Newsletter.objects.all().delete()
            self.stdout.write(self.style.WARNING("Deleted existing newsletters."))

        newsletters = json.loads(SEED_FILE.read_text(encoding="utf-8"))
        for spec in newsletters:
            obj, created = Newsletter.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "title": spec["title"],
                    "edition_label": spec["edition_label"],
                    "theme": spec.get("theme", ""),
                    "intro": spec.get("intro", ""),
                    "sections": spec["sections"],
                    "is_active": True,
                },
            )
            n_articles = sum(len(s["articles"]) for s in spec["sections"])
            verb = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{verb} newsletter: {obj.slug} "
                    f"({len(spec['sections'])} sections, {n_articles} articles)"
                )
            )

        # Researcher account (staff) for the dashboard / rating tool.
        username = os.environ.get("RESEARCHER_USERNAME", "researcher")
        password = os.environ.get("RESEARCHER_PASSWORD", "researcher123")
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"email": "researcher@example.com", "is_staff": True},
        )
        user.is_staff = True
        user.set_password(password)
        user.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Researcher account ready: {username} / {password} "
                "(change in production)."
            )
        )

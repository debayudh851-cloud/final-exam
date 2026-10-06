from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import nltk


class Command(BaseCommand):
    help = 'Download local NLTK English POS data.'

    def handle(self, *args, **options):
        destination = settings.BASE_DIR / 'artifacts' / 'nltk_data'
        destination.mkdir(parents=True, exist_ok=True)
        if not nltk.download('averaged_perceptron_tagger_eng', download_dir=str(destination), quiet=True):
            raise CommandError('Could not download the NLTK POS tagger.')
        self.stdout.write(self.style.SUCCESS('NLTK POS resource ready.'))

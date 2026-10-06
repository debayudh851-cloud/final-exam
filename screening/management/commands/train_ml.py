import json
from django.core.management.base import BaseCommand
from django.conf import settings
from screening.ml import train_models


class Command(BaseCommand):
    help = 'Train and compare two demo shortlist models.'

    def add_arguments(self, parser):
        parser.add_argument('--data', default=str(settings.BASE_DIR / 'samples' / 'training.csv'))

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(train_models(options['data']), indent=2))

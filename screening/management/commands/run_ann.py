import json
from django.core.management.base import BaseCommand
from django.conf import settings
from screening.dl import run_ann


class Command(BaseCommand):
    help = 'Train, save, reload, and invoke the minimal CPU Keras ANN.'

    def add_arguments(self, parser):
        parser.add_argument('--data', default=str(settings.BASE_DIR / 'samples' / 'training.csv'))

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(run_ann(options['data']), indent=2))

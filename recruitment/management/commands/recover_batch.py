from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta
from recruitment.models import ApplicationBatch


class Command(BaseCommand):
    help = 'Mark a stalled batch failed, only after its worker has been stopped.'

    def add_arguments(self, parser):
        parser.add_argument('batch_id', type=int)
        parser.add_argument('--worker-stopped', action='store_true')

    def handle(self, *args, **options):
        if not options['worker_stopped']:
            raise CommandError('Stop the worker first, then pass --worker-stopped.')
        count = ApplicationBatch.objects.filter(pk=options['batch_id'], status__in=['PROCESSING', 'QUEUED'],
            updated_at__lt=timezone.now() - timedelta(minutes=10)).update(status='FAILED',
                error='Worker interruption detected. Retry the batch.', processed_rows=0)
        if not count:
            raise CommandError('No matching stalled batch older than ten minutes.')
        self.stdout.write('Marked stalled batch failed. Retry it from the portal.')

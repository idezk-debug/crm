from django.core.management.base import BaseCommand
from django.utils import timezone

from MyApp.models import Notification, WorkFile


class Command(BaseCommand):
    help = "Deletes expired notifications and work files (including stored files)."

    def handle(self, *args, **options):
        expired_notifications = Notification.objects.filter(expires_at__lte=timezone.now())
        notification_count = expired_notifications.count()
        expired_notifications.delete()

        expired_files = WorkFile.objects.filter(expires_at__lte=timezone.now())
        file_count = expired_files.count()

        for work_file in expired_files:
            if work_file.file:
                work_file.file.delete(save=False)

        expired_files.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {notification_count} expired notification(s) and {file_count} expired work file(s)."
            )
        )

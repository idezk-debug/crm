from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from MyApp.models import Company


class Command(BaseCommand):
    help = 'Auto-delete companies that have been expired for more than 10 days'

    def handle(self, *args, **options):
        now = timezone.now()
        grace_period = timedelta(days=10)
        
        # Find companies that have been expired for > 10 days
        expired_threshold = now - grace_period
        
        companies_to_delete = Company.objects.filter(
            plan_expires_at__lt=expired_threshold,
            is_active=False
        ) | Company.objects.filter(
            trial_ends_at__lt=expired_threshold,
            plan_status=Company.STATUS_TRIAL,
            is_active=False,
            plan_expires_at__isnull=True
        )
        
        count = companies_to_delete.count()
        
        for company in companies_to_delete:
            company_name = company.name
            company.delete()
            self.stdout.write(
                self.style.SUCCESS(f'✓ Deleted expired company: {company_name} (Code: {company.code})')
            )
        
        if count == 0:
            self.stdout.write(self.style.WARNING('No expired companies to delete.'))
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Successfully deleted {count} expired company/companies.')
            )

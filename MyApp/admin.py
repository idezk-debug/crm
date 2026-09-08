from django.contrib import admin
from .models import (
    CustomUser,
    Company,
    Client,
    Staff,
    Work,
    WorkFile,
    WebsiteSettings,
    CompanySettings,
    Notification,
    DeletionRequest,
    SubscriptionPaymentRequest,
)

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(Company)
admin.site.register(Client)
admin.site.register(Staff)
admin.site.register(Work)
admin.site.register(WorkFile)
admin.site.register(WebsiteSettings)
admin.site.register(CompanySettings)
admin.site.register(Notification)
admin.site.register(DeletionRequest)
admin.site.register(SubscriptionPaymentRequest)

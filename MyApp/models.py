from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from datetime import timedelta
from pathlib import Path
from decimal import Decimal
from cities_light.models import Country, Region, City

# =====================================================================
# CUSTOM USER MANAGER
# =====================================================================

class CustomUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("Users must have a username")
        
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        
        return self.create_user(username, password, **extra_fields)



# =====================================================================
# CUSTOM USER MODEL
# =====================================================================

class CustomUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=150, unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    objects = CustomUserManager()

    USERNAME_FIELD = 'username'   # important!
    REQUIRED_FIELDS = []          # no email required


def default_trial_end():
    return timezone.now() + timedelta(days=7)

def default_plan_price():
    return Decimal("1499.00")


class Company(models.Model):
    STATUS_TRIAL = "trial"
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_TRIAL, "Trial"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_EXPIRED, "Expired"),
    ]

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=80, unique=True)
    first_name = models.CharField(max_length=120, blank=True, default="")
    last_name = models.CharField(max_length=120, blank=True, default="")
    owner_user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="owned_company")
    business_email = models.EmailField(blank=True, default="")
    website_url = models.URLField(max_length=255, blank=True, default="")
    business_phone = models.CharField(max_length=20, blank=True, default="")
    gst_or_udyam_no = models.CharField(max_length=120, blank=True, default="")
    permanent_address = models.CharField(max_length=500, blank=True, default="")
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, related_name="companies")
    state = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, related_name="companies")
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, related_name="companies")
    pincode = models.CharField(max_length=20, blank=True, default="")
    trial_started_at = models.DateTimeField(default=timezone.now)
    trial_ends_at = models.DateTimeField(default=default_trial_end)
    plan_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_TRIAL,
    )
    plan_expires_at = models.DateTimeField(null=True, blank=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=default_plan_price)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def has_active_access(self):
        if not self.is_active:
            return False
        now = timezone.now()
        if self.plan_expires_at and self.plan_expires_at > now:
            return True
        return self.trial_ends_at > now

    def get_access_state(self):
        now = timezone.now()
        if self.plan_expires_at and self.plan_expires_at > now:
            return "active", (self.plan_expires_at - now).days
        if self.trial_ends_at > now:
            return "trial", (self.trial_ends_at - now).days
        return "expired", 0


# =====================================================================
# CLIENT MODEL (Business Customer Within Company)
# =====================================================================

class Client(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="clients", null=True, blank=True)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    client_name = models.CharField(max_length=200)
    client_id = models.CharField(max_length=200)
    business_email = models.EmailField(blank=True, default="")
    business_phone = models.CharField(max_length=20, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("company", "client_id")]

    def __str__(self):
        return self.client_name


class SubscriptionPaymentRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    PLAN_FREE = "free"
    PLAN_BASE = "base"
    PLAN_PREMIUM = "premium"
    PLAN_ENTERPRISE = "enterprise"
    PLAN_CHOICES = [
        (PLAN_FREE, "Free"),
        (PLAN_BASE, "Base"),
        (PLAN_PREMIUM, "Premium"),
        (PLAN_ENTERPRISE, "Enterprise"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="payment_requests", null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="INR")
    transaction_reference = models.CharField(max_length=120, unique=True)
    selected_plan = models.CharField(max_length=30, choices=PLAN_CHOICES, default=PLAN_FREE)
    duration_days = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    note = models.TextField(blank=True, default="")
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_payment_requests",
    )

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.company.name} - {self.transaction_reference}"


# =====================================================================
# STAFF MODEL
# =====================================================================

class Staff(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="staffs", null=True, blank=True)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    staff_name = models.CharField(max_length=200)
    staff_id = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["staff_name"]
        unique_together = [("company", "staff_id")]

    def __str__(self):
        return self.staff_name
    
# =====================================================================
# WORK MODEL
# =====================================================================

class Work(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Ongoing", "Ongoing"),
        ("Completed", "Completed"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="works", null=True, blank=True)
    client = models.ForeignKey(Client, related_name="works", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    deadline = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.client.client_name})"
    

# =====================================================================
# WORK FILE MODEL (Any file type per Work)
# =====================================================================

class WorkFile(models.Model):
    work = models.ForeignKey(
        Work,
        related_name="files",
        on_delete=models.CASCADE
    )
    file = models.FileField(upload_to="work_files/")
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.original_name} ({self.work.title})"

    @property
    def extension(self):
        return Path(self.original_name).suffix.lower().lstrip(".")

    @property
    def is_image(self):
        return self.extension in {"jpg", "jpeg", "png", "gif", "bmp", "webp", "tif", "tiff"}

    @property
    def file_icon(self):
        ext = self.extension
        if ext in {"jpg", "jpeg", "png", "gif", "bmp", "webp", "tif", "tiff"}:
            return "bi-file-image text-success"
        if ext == "pdf":
            return "bi-file-earmark-pdf text-danger"
        if ext in {"doc", "docx"}:
            return "bi-file-earmark-word text-primary"
        if ext in {"xls", "xlsx", "csv"}:
            return "bi-file-earmark-excel text-success"
        if ext == "txt":
            return "bi-file-earmark-text text-secondary"
        return "bi-file-earmark text-secondary"


# =====================================================================
# WEBSITE SETTINGS MODEL (Admin Configuration)
# =====================================================================

class WebsiteSettings(models.Model):
    # Site Information
    site_name = models.CharField(max_length=255, default="My Project")
    site_logo = models.ImageField(upload_to="settings/", null=True, blank=True)
    site_description = models.TextField(blank=True, default="Professional web design and development services")

    # Plan Pricing
    free_plan_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    base_plan_price = models.DecimalField(max_digits=10, decimal_places=2, default=999.00)
    premium_plan_price = models.DecimalField(max_digits=10, decimal_places=2, default=9999.00)
    enterprise_plan_price = models.DecimalField(max_digits=10, decimal_places=2, default=29999.00)

    # Contact Information
    phone = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address = models.CharField(max_length=500, blank=True, default="")

    # Social Links
    facebook_url = models.URLField(blank=True, default="")
    instagram_url = models.URLField(blank=True, default="")
    twitter_url = models.URLField(blank=True, default="")
    linkedin_url = models.URLField(blank=True, default="")

    # Features/Toggles
    maintenance_mode = models.BooleanField(default=False)
    allow_client_registration = models.BooleanField(default=True)
    show_testimonials = models.BooleanField(default=True)
    show_portfolio = models.BooleanField(default=True)

    # Messaging
    maintenance_message = models.TextField(blank=True, default="We are currently under maintenance. Please check back soon!")
    welcome_message = models.TextField(blank=True, default="Welcome to our platform")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Website Settings"
    
    def __str__(self):
        return "Website Settings"
    
    @staticmethod
    def get_settings():
        """Get or create default settings"""
        settings, created = WebsiteSettings.objects.get_or_create(pk=1)
        return settings


class CompanySettings(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="settings")

    # Company Branding
    site_name = models.CharField(max_length=255, default="My Company")
    site_logo = models.ImageField(upload_to="company_settings/", null=True, blank=True)
    site_description = models.TextField(blank=True, default="Company workspace settings")

    # Contact
    phone = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address = models.CharField(max_length=500, blank=True, default="")

    # Social
    facebook_url = models.URLField(blank=True, default="")
    instagram_url = models.URLField(blank=True, default="")
    twitter_url = models.URLField(blank=True, default="")
    linkedin_url = models.URLField(blank=True, default="")

    # Company-level toggles
    maintenance_mode = models.BooleanField(default=False)
    allow_client_registration = models.BooleanField(default=True)
    show_testimonials = models.BooleanField(default=True)
    show_portfolio = models.BooleanField(default=True)

    # Messages
    maintenance_message = models.TextField(blank=True, default="We are currently under maintenance. Please check back soon!")
    welcome_message = models.TextField(blank=True, default="Welcome to our platform")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Company Settings"

    def __str__(self):
        return f"{self.company.name} Settings"

    @staticmethod
    def get_for_company(company):
        settings, created = CompanySettings.objects.get_or_create(
            company=company,
            defaults={
                "site_name": company.name,
                "email": company.business_email,
                "phone": company.business_phone,
            },
        )
        return settings


# =====================================================================
# NOTIFICATION MODEL
# =====================================================================

class Notification(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True)
    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="sent_notifications"
    )
    recipient = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="received_notifications"
    )
    message = models.TextField()
    deletion_request = models.ForeignKey(
        "DeletionRequest",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"From {self.sender.username} to {self.recipient.username}"


class DeletionRequest(models.Model):
    TARGET_CLIENT = "client"
    TARGET_WORK = "work"
    TARGET_STAFF = "staff"
    TARGET_CLIENT_DEACTIVATE = "client_deactivate"
    TARGET_CLIENT_ACTIVATE = "client_activate"
    TARGET_CHOICES = [
        (TARGET_CLIENT, "Client"),
        (TARGET_WORK, "Work"),
        (TARGET_STAFF, "Staff"),
        (TARGET_CLIENT_DEACTIVATE, "Client Deactivation"),
        (TARGET_CLIENT_ACTIVATE, "Client Activation"),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="deletion_requests", null=True, blank=True)
    requested_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="deletion_requests"
    )
    target_type = models.CharField(max_length=20, choices=TARGET_CHOICES)
    target_id = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reason = models.TextField(blank=True, default="")
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_deletion_requests"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_target_type_display()} delete request #{self.pk}"

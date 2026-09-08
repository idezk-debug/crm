from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from MyApp.models import (
    Client as ClientRecord,
    Company,
    Staff,
    SubscriptionPaymentRequest,
    WebsiteSettings,
    Work,
)
from MyApp.utils import validate_password

User = get_user_model()


class PasswordValidationTests(TestCase):
    def test_short_password_rejected(self):
        ok, message = validate_password("abc")
        self.assertFalse(ok)
        self.assertIn("8", message)

    def test_valid_password_accepted(self):
        ok, message = validate_password("securepass")
        self.assertTrue(ok)
        self.assertEqual(message, "")


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.client = Client()
        owner_a = User.objects.create_user(username="company-a", password="ownerpass123")
        owner_b = User.objects.create_user(username="company-b", password="ownerpass123")
        self.company_a = Company.objects.create(name="Company A", code="company-a", owner_user=owner_a)
        self.company_b = Company.objects.create(name="Company B", code="company-b", owner_user=owner_b)

        user_a = User.objects.create_user(username="company-a__client1", password="clientpass123")
        user_b = User.objects.create_user(username="company-b__client1", password="clientpass123")
        self.client_a = ClientRecord.objects.create(
            company=self.company_a,
            user=user_a,
            client_name="Client A",
            client_id="client1",
        )
        self.client_b = ClientRecord.objects.create(
            company=self.company_b,
            user=user_b,
            client_name="Client B",
            client_id="client1",
        )

    def test_company_admin_cannot_view_other_company_client_work(self):
        self.client.login(username="company-a", password="ownerpass123")
        response = self.client.get(reverse("work_view", args=[self.client_b.id]))
        self.assertEqual(response.status_code, 404)


class TrialExpiryTests(TestCase):
    def setUp(self):
        self.client = Client()
        owner = User.objects.create_user(username="trial-co", password="ownerpass123")
        self.company = Company.objects.create(
            name="Trial Co",
            code="trial-co",
            owner_user=owner,
            trial_ends_at=timezone.now() - timedelta(days=1),
            plan_status=Company.STATUS_EXPIRED,
        )

    def test_expired_company_redirects_to_billing(self):
        self.client.login(username="trial-co", password="ownerpass123")
        response = self.client.get(reverse("staff_dashboard"))
        self.assertRedirects(response, reverse("company_billing"))


class PaymentApprovalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username="platform-owner",
            password="superpass123",
        )
        owner = User.objects.create_user(username="pay-co", password="ownerpass123")
        self.company = Company.objects.create(name="Pay Co", code="pay-co", owner_user=owner)
        self.payment = SubscriptionPaymentRequest.objects.create(
            company=self.company,
            amount=Decimal("1499.00"),
            transaction_reference="TXN-TEST-001",
        )

    def test_platform_owner_can_approve_payment(self):
        self.client.login(username="platform-owner", password="superpass123")
        response = self.client.post(
            reverse("review_payment_request", args=[self.payment.id]),
            {"action": "approve"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")

        self.company.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, SubscriptionPaymentRequest.STATUS_APPROVED)
        self.assertEqual(self.company.plan_status, Company.STATUS_ACTIVE)
        self.assertIsNotNone(self.company.plan_expires_at)


class AddClientPasswordTests(TestCase):
    def setUp(self):
        self.client = Client()
        owner = User.objects.create_user(username="add-client-co", password="ownerpass123")
        self.company = Company.objects.create(name="Add Client Co", code="add-client-co", owner_user=owner)
        WebsiteSettings.objects.update_or_create(pk=1, defaults={"allow_client_registration": True})

    def test_add_client_requires_admin_set_password(self):
        self.client.login(username="add-client-co", password="ownerpass123")
        response = self.client.post(
            reverse("add_client"),
            {
                "client_name": "New Client",
                "client_id": "NC001",
                "password": "short",
                "confirm_password": "short",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "error")

    def test_add_client_with_valid_password(self):
        self.client.login(username="add-client-co", password="ownerpass123")
        response = self.client.post(
            reverse("add_client"),
            {
                "client_name": "New Client",
                "client_id": "NC001",
                "password": "clientpass123",
                "confirm_password": "clientpass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertTrue(
            ClientRecord.objects.filter(company=self.company, client_id="NC001").exists()
        )


class SubscriptionPlanTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.platform_owner = User.objects.create_superuser(
            username="platform-owner",
            password="superpass123",
        )
        owner = User.objects.create_user(username="plan-co", password="ownerpass123")
        self.company = Company.objects.create(name="Plan Co", code="plan-co", owner_user=owner)

    def test_selected_plan_is_saved_on_payment_request(self):
        self.client.login(username="plan-co", password="ownerpass123")
        response = self.client.post(
            reverse("submit_payment_request"),
            {
                "transaction_reference": "PLAN-BASE-001",
                "amount": "999",
                "note": "Base plan request",
                "selected_plan": "base",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")

        payment = SubscriptionPaymentRequest.objects.get(transaction_reference="PLAN-BASE-001")
        self.assertEqual(payment.selected_plan, "base")
        self.assertEqual(payment.duration_days, 30)
        self.assertEqual(payment.amount, Decimal("999.00"))

    def test_approval_uses_selected_plan_duration(self):
        payment = SubscriptionPaymentRequest.objects.create(
            company=self.company,
            amount=Decimal("999.00"),
            transaction_reference="PLAN-BASE-002",
            selected_plan="premium",
            duration_days=90,
        )

        self.client.login(username="platform-owner", password="superpass123")
        response = self.client.post(
            reverse("review_payment_request", args=[payment.id]),
            {"action": "approve"},
        )

        self.assertEqual(response.status_code, 200)
        self.company.refresh_from_db()
        self.assertEqual(self.company.plan_status, Company.STATUS_ACTIVE)
        self.assertIsNotNone(self.company.plan_expires_at)


class CompanyRevokeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.platform_owner = User.objects.create_superuser(
            username="platform-owner",
            password="superpass123",
        )
        self.company_owner = User.objects.create_user(username="revoke-co", password="ownerpass123")
        self.company = Company.objects.create(name="Revoke Co", code="revoke-co", owner_user=self.company_owner)

    def test_platform_owner_can_toggle_company_access(self):
        self.client.login(username="platform-owner", password="superpass123")
        response = self.client.get(reverse("platform_dashboard"))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("toggle_company_access", args=[self.company.id]))
        self.assertEqual(response.status_code, 200)
        self.company.refresh_from_db()
        self.assertFalse(self.company.is_active)

        response_data = response.json()
        self.assertEqual(response_data["status"], "success")
        self.assertEqual(response_data["is_active"], False)

    def test_platform_owner_can_manage_selected_company_and_exit(self):
        self.client.login(username="platform-owner", password="superpass123")

        response = self.client.get(reverse("enter_company_admin", args=[self.company.id]))
        self.assertRedirects(response, reverse("company_dashboard"))

        response = self.client.get(reverse("company_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revoke Co Company Dashboard")

        response = self.client.post(
            reverse("add_client"),
            {
                "client_name": "Platform Managed Client",
                "client_id": "PMC001",
                "password": "clientpass123",
                "confirm_password": "clientpass123",
            },
        )
        self.assertEqual(response.json()["status"], "success")
        self.assertTrue(ClientRecord.objects.filter(company=self.company, client_id="PMC001").exists())

        response = self.client.get(reverse("exit_company_admin"))
        self.assertRedirects(response, reverse("platform_dashboard"))

    def test_inactive_company_delete_client_requests_admin(self):
        self.company.is_active = False
        self.company.save(update_fields=["is_active"])

        staff_user = User.objects.create_user(username="revoke-co__staff1", password="staffpass123")
        Staff.objects.create(company=self.company, user=staff_user, staff_name="Staff One", staff_id="S001")
        client_user = User.objects.create_user(username="revoke-co__client1", password="clientpass123")
        client_record = ClientRecord.objects.create(
            company=self.company,
            user=client_user,
            client_name="Client One",
            client_id="C001",
        )

        self.client.login(username="revoke-co__staff1", password="staffpass123")
        response = self.client.post(reverse("delete_client", args=[client_record.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertTrue(
            ClientRecord.objects.filter(id=client_record.id).exists()
        )
        from MyApp.models import DeletionRequest
        self.assertTrue(
            DeletionRequest.objects.filter(target_type=DeletionRequest.TARGET_CLIENT, target_id=client_record.id, status=DeletionRequest.STATUS_PENDING).exists()
        )

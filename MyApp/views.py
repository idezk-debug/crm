from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from pathlib import Path
import mimetypes
from decimal import Decimal, InvalidOperation
import re

from cities_light.models import Country, Region, SubRegion, City

from MyApp.models import (
    Company,
    Client,
    Staff,
    Work,
    CustomUser,
    WorkFile,
    WebsiteSettings,
    CompanySettings,
    Notification,
    DeletionRequest,
    SubscriptionPaymentRequest,
)
from MyApp.utils import validate_password, validate_phone_number
from MyApp.email_notifications import send_company_welcome_email, send_payment_review_email


def get_plan_options():
    settings = WebsiteSettings.get_settings()
    return [
        {
            "value": "free",
            "name": "Trial",
            "price": Decimal(str(settings.free_plan_price)),
            "duration_days": 7,
            "features": [
                "7-day free trial",
                "Basic dashboard access",
                "Client and work management",
                "Core CRM essentials",
            ],
        },
        {
            "value": "base",
            "name": "Basic",
            "price": Decimal(str(settings.base_plan_price)),
            "duration_days": 30,
            "features": [
                "30 days access",
                "Everything in Trial",
                "Team management",
                "Email notifications",
                "Company settings",
            ],
        },
        {
            "value": "premium",
            "name": "Premium",
            "price": Decimal(str(settings.premium_plan_price)),
            "duration_days": 365,
            "features": [
                "Everything in Basic",
                "Advanced reporting",
                "Priority support",
                "Team collaboration tools",
                "Advanced workflow controls",
                "Expanded file management",
            ],
        },
        {
            "value": "enterprise",
            "name": "Enterprise",
            "price": None,
            "duration_days": 365,
            "contact_only": True,
            "features": [
                "Everything in Premium",
                "Unlimited team members",
                "Dedicated onboarding",
                "Custom workflows and integrations",
                "Advanced security and access controls",
                "Dedicated account support",
                "Maximum control and insights",
            ],
        },
    ]


# Create your views here.

def index(request):
    return render(request, 'index.html')

def crm_landing(request):
    return render(request, "crm_landing.html")


def _normalize_login_code(seed_text):
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", (seed_text or "").strip().lower()).strip("-._")
    return cleaned or "company"


def _generate_unique_company_code(seed_text):
    base = _normalize_login_code(seed_text)[:70]
    candidate = base
    index = 1

    while (
        CustomUser.objects.filter(username__iexact=candidate).exists()
        or Company.objects.filter(code__iexact=candidate).exists()
    ):
        index += 1
        suffix = f"-{index}"
        candidate = f"{base[:80 - len(suffix)]}{suffix}"

    return candidate


def _get_register_location_context(post_data=None):
    selected_country = (post_data.get("country") if post_data else "") or ""
    selected_state = (post_data.get("state") if post_data else "") or ""
    selected_district = (post_data.get("district") if post_data else "") or ""

    countries = Country.objects.order_by("name")
    states = Region.objects.select_related("country").order_by("name")
    districts = SubRegion.objects.select_related("country", "region").order_by("name")

    return {
        "countries": countries,
        "states": states,
        "districts": districts,
        "selected_country": str(selected_country),
        "selected_state": str(selected_state),
        "selected_district": str(selected_district),
    }


def register_company(request):
    settings_obj = WebsiteSettings.get_settings()
    if not settings_obj.allow_client_registration:
        messages.error(request, "New company registrations are currently disabled.")
        return redirect("login")

    if request.method == "POST":
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        company_name = (request.POST.get("company_name") or "").strip()
        gst_or_udyam_no = (request.POST.get("gst_or_udyam_no") or "").strip()
        permanent_address = (request.POST.get("permanent_address") or "").strip()
        business_email = (request.POST.get("business_email") or "").strip()
        website_url = (request.POST.get("website_url") or "").strip()
        country_code = (request.POST.get("country_code") or "").strip()
        business_phone = (request.POST.get("business_phone") or "").strip()
        pincode = (request.POST.get("pincode") or "").strip()
        country_id = (request.POST.get("country") or "").strip()
        state_id = (request.POST.get("state") or "").strip()
        district_id = (request.POST.get("district") or "").strip()
        password = request.POST.get("password") or ""
        confirm_password = request.POST.get("confirm_password") or ""
        location_context = _get_register_location_context(request.POST)

        if not all([
            first_name,
            last_name,
            business_email,
            business_phone,
            country_code,
            password,
            confirm_password,
            company_name,
            permanent_address,
            country_id,
            state_id,
            district_id,
            pincode,
        ]):
            messages.error(request, "Please fill all required fields.")
            return render(request, "register_company.html", location_context)

        phone_ok, phone_error = validate_phone_number(country_code, business_phone)
        if not phone_ok:
            messages.error(request, phone_error)
            return render(request, "register_company.html", location_context)

        full_business_phone = f"{country_code} {business_phone}".strip()

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "register_company.html", location_context)

        if website_url and not website_url.startswith(("http://", "https://")):
            website_url = f"https://{website_url}"

        password_ok, password_error = validate_password(password)
        if not password_ok:
            messages.error(request, password_error)
            return render(request, "register_company.html", location_context)

        country = Country.objects.filter(id=country_id).first()
        state = Region.objects.filter(id=state_id).first()
        district = SubRegion.objects.filter(id=district_id).first()

        if not all([country, state, district]):
            messages.error(request, "Please choose valid country, state and district.")
            return render(request, "register_company.html", location_context)

        if state.country_id != country.id:
            messages.error(request, "Selected state does not belong to selected country.")
            return render(request, "register_company.html", location_context)

        if district.country_id != country.id or district.region_id != state.id:
            messages.error(request, "Selected district does not belong to selected country/state.")
            return render(request, "register_company.html", location_context)

        # Keep compatibility with existing Company.city FK by mapping district to any city in that district.
        city_for_district = City.objects.filter(
            country_id=country.id,
            region_id=state.id,
            subregion_id=district.id,
        ).order_by("name").first()

        company_code = _generate_unique_company_code(business_email)

        user = CustomUser.objects.create_user(username=company_code, password=password)
        Company.objects.create(
            first_name=first_name,
            last_name=last_name,
            name=company_name,
            code=company_code,
            owner_user=user,
            business_email=business_email,
            website_url=website_url,
            business_phone=full_business_phone,
            gst_or_udyam_no=gst_or_udyam_no,
            permanent_address=permanent_address,
            country=country,
            state=state,
            city=city_for_district,
            pincode=pincode,
            trial_started_at=timezone.now(),
            trial_ends_at=timezone.now() + timedelta(days=7),
            plan_status=Company.STATUS_TRIAL,
        )

        company = Company.objects.get(code=company_code)
        send_company_welcome_email(company)

        login(request, user)
        messages.success(
            request,
            f"Registration successful. Your login ID is '{company_code}'. Your 7-day free trial has started.",
        )
        return redirect("staff_dashboard")

    return render(request, "register_company.html", _get_register_location_context())


def is_platform_owner(user):
    return user.is_authenticated and user.is_superuser


def get_default_company():
    return (
        Company.objects.filter(code="default-company", is_active=True).first()
        or Company.objects.filter(is_active=True).order_by("id").first()
        or Company.objects.order_by("id").first()
    )


def get_user_company(user, request=None):
    if not user.is_authenticated:
        return None
    selected_company_id = request.session.get("admin_company_id") if request else None
    if is_platform_owner(user) and selected_company_id:
        selected_company = Company.objects.filter(id=selected_company_id).first()
        if selected_company:
            return selected_company
    if is_platform_owner(user):
        return get_default_company()
    company = Company.objects.filter(owner_user=user, is_active=True).first()
    if company:
        return company
    staff = Staff.objects.filter(user=user).select_related("company").first()
    if staff:
        return staff.company
    client = Client.objects.filter(user=user).select_related("company").first()
    if client:
        return client.company
    return None


def get_target_company_from_request(request):
    if not is_platform_owner(request.user):
        return get_user_company(request.user)
    company_id = (request.POST.get("company_id") or request.GET.get("company_id") or "").strip()
    if company_id:
        return Company.objects.filter(id=company_id).first()
    return Company.objects.order_by("id").first()


def is_company_admin(user):
    return is_platform_owner(user) or Company.objects.filter(owner_user=user).exists()


def is_company_staff(user):
    return Staff.objects.filter(user=user).exists()


def is_company_manager(user):
    return is_company_admin(user) or is_company_staff(user)


def get_admin_company(request):
    return get_user_company(request.user, request)


def get_company_access_snapshot(company):
    state, days_left = company.get_access_state()
    return {
        "state": state,
        "days_left": max(days_left, 0),
        "is_active": company.has_active_access(),
    }


def ensure_company_access_or_redirect(request, company):
    if company is None:
        messages.error(request, "Company mapping not found for this account.")
        return redirect("login")
    # Platform owner's own company is free/unlimited.
    if is_platform_owner(request.user):
        return None
    snapshot = get_company_access_snapshot(company)
    if snapshot["is_active"]:
        return None
    messages.error(request, "Your company trial/plan has ended. Please renew to continue access.")
    return redirect("company_billing")


def cleanup_expired_notifications():
    Notification.objects.filter(expires_at__lte=timezone.now()).delete()


def get_active_notifications_for_user(user):
    cleanup_expired_notifications()
    return Notification.objects.filter(
        recipient=user,
        expires_at__gt=timezone.now()
    ).select_related("sender")


def cleanup_expired_work_files():
    expired_files = WorkFile.objects.filter(expires_at__lte=timezone.now())
    for item in expired_files:
        if item.file:
            item.file.delete(save=False)
    expired_files.delete()


def _is_allowed_upload_extension(filename):
    allowed_ext = {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"
    }
    return Path(filename).suffix.lower() in allowed_ext


def categorize_work_files(files):
    image_ext = {"jpg", "jpeg", "png", "gif", "bmp", "webp", "tif", "tiff"}
    document_ext = {"pdf", "doc", "docx", "txt"}
    excel_ext = {"xls", "xlsx", "csv"}

    categories = {
        "images": [],
        "documents": [],
        "excel": [],
        "others": [],
    }

    for item in files:
        ext = item.extension
        if ext in image_ext:
            categories["images"].append(item)
        elif ext in document_ext:
            categories["documents"].append(item)
        elif ext in excel_ext:
            categories["excel"].append(item)
        else:
            categories["others"].append(item)

    return categories


def delete_work_file_assets(work):
    work_files = WorkFile.objects.filter(work=work)
    for item in work_files:
        if item.file:
            item.file.delete(save=False)


def _get_admin_users(company=None):
    if company is not None and not company.has_active_access():
        return CustomUser.objects.filter(is_superuser=True, is_active=True)
    if company is not None and company.owner_user and company.owner_user.is_active:
        return CustomUser.objects.filter(id=company.owner_user_id, is_active=True)
    return CustomUser.objects.filter(is_superuser=True, is_active=True)


def _create_deletion_request_notifications(deletion_request, message):
    now = timezone.now()
    expires_at = now + timedelta(days=7)
    admin_users = [user for user in _get_admin_users(deletion_request.company) if user.id != deletion_request.requested_by_id]

    Notification.objects.bulk_create([
        Notification(
            company=deletion_request.company,
            sender=deletion_request.requested_by,
            recipient=admin_user,
            message=message,
            deletion_request=deletion_request,
            expires_at=expires_at,
        )
        for admin_user in admin_users
    ])


def _request_delete_client(request, client):
    existing_request = DeletionRequest.objects.filter(
        target_type=DeletionRequest.TARGET_CLIENT,
        target_id=client.id,
        status=DeletionRequest.STATUS_PENDING,
    ).first()
    if existing_request:
        return JsonResponse({
            "status": "error",
            "message": "A delete request for this client is already pending admin approval.",
        })

    deletion_request = DeletionRequest.objects.create(
        company=client.company,
        requested_by=request.user,
        target_type=DeletionRequest.TARGET_CLIENT,
        target_id=client.id,
        reason=f"Staff requested deletion of client {client.client_name} ({client.client_id}).",
    )
    _create_deletion_request_notifications(
        deletion_request,
        f"Delete request: Staff {request.user.username} requested deletion of client "
        f"{client.client_name} ({client.client_id}).",
    )
    return JsonResponse({
        "status": "success",
        "message": "Delete request sent to admin for confirmation.",
    })


def _request_delete_work(request, work):
    existing_request = DeletionRequest.objects.filter(
        target_type=DeletionRequest.TARGET_WORK,
        target_id=work.id,
        status=DeletionRequest.STATUS_PENDING,
    ).first()
    if existing_request:
        return JsonResponse({
            "status": "error",
            "message": "A delete request for this work is already pending admin approval.",
        })

    deletion_request = DeletionRequest.objects.create(
        company=work.company,
        requested_by=request.user,
        target_type=DeletionRequest.TARGET_WORK,
        target_id=work.id,
        reason=(
            f"Staff requested deletion of work {work.title} "
            f"for client {work.client.client_name}."
        ),
    )
    _create_deletion_request_notifications(
        deletion_request,
        f"Delete request: Staff {request.user.username} requested deletion of work "
        f"{work.title} for client {work.client.client_name}.",
    )
    return JsonResponse({
        "status": "success",
        "message": "Delete request sent to admin for confirmation.",
    })


def _request_delete_staff(request, staff):
    existing_request = DeletionRequest.objects.filter(
        target_type=DeletionRequest.TARGET_STAFF,
        target_id=staff.id,
        status=DeletionRequest.STATUS_PENDING,
    ).first()
    if existing_request:
        return JsonResponse({
            "status": "error",
            "message": "A delete request for this staff member is already pending admin approval.",
        })

    deletion_request = DeletionRequest.objects.create(
        company=staff.company,
        requested_by=request.user,
        target_type=DeletionRequest.TARGET_STAFF,
        target_id=staff.id,
        reason=f"Company requested deletion of staff {staff.staff_name} ({staff.staff_id}).",
    )
    _create_deletion_request_notifications(
        deletion_request,
        f"Delete request: Staff {request.user.username} requested deletion of staff "
        f"{staff.staff_name} ({staff.staff_id}).",
    )
    return JsonResponse({
        "status": "success",
        "message": "Delete request sent to admin for confirmation.",
    })


def _delete_client_and_assets(client):
    for work in client.works.all():
        delete_work_file_assets(work)
    client.user.delete()


def _delete_work_and_assets(work):
    delete_work_file_assets(work)
    work.delete()


def _delete_staff_and_assets(staff):
    if staff.user:
        staff.user.delete()


def _authenticate_candidate_users(request, candidates, password):
    authenticated_user = None
    for candidate in candidates:
        user = authenticate(request, username=candidate.user.username, password=password)
        if user is not None:
            if authenticated_user is not None:
                return None, "Multiple matching accounts found. Please login using your full login ID."
            authenticated_user = user
    return authenticated_user, None


def _request_client_status_change(request, client, activate):
    target_type = DeletionRequest.TARGET_CLIENT_ACTIVATE if activate else DeletionRequest.TARGET_CLIENT_DEACTIVATE
    action_label = "activate" if activate else "deactivate"

    existing_request = DeletionRequest.objects.filter(
        target_type=target_type,
        target_id=client.id,
        status=DeletionRequest.STATUS_PENDING,
    ).first()
    if existing_request:
        return JsonResponse({
            "status": "error",
            "message": f"A client {action_label} request is already pending approval.",
        })

    deletion_request = DeletionRequest.objects.create(
        company=client.company,
        requested_by=request.user,
        target_type=target_type,
        target_id=client.id,
        reason=(
            f"Staff requested client {action_label} for {client.client_name} ({client.client_id})."
        ),
    )
    _create_deletion_request_notifications(
        deletion_request,
        f"Client {action_label} request: Staff {request.user.username} requested client {action_label} "
        f"for {client.client_name} ({client.client_id}).",
    )
    return JsonResponse({
        "status": "success",
        "message": f"Client {action_label} request sent to admin for approval.",
    })


# ================================================================
# LOGIN
# ================================================================

def _get_portal_redirect(request, user):
    if is_platform_owner(user):
        return redirect("platform_dashboard")
    if is_company_admin(user) or is_company_staff(user):
        company = get_user_company(user)
        blocked = ensure_company_access_or_redirect(request, company)
        if blocked:
            return blocked
        return redirect("staff_dashboard")
    client = Client.objects.filter(user=user).first()
    if client:
        company = client.company
        blocked = ensure_company_access_or_redirect(request, company)
        if blocked:
            return blocked
        return redirect("client_dashboard")
    return None

def login_view(request):
    if request.method == "POST":
        identifier = (request.POST.get("identifier") or "").strip()
        password = request.POST.get("password") or ""

        use_direct_username_first = "__" in identifier or "@" in identifier

        if use_direct_username_first:
            user = authenticate(request, username=identifier, password=password)
            if user is not None:
                redirect_response = _get_portal_redirect(request, user)
                if redirect_response is not None:
                    login(request, user)
                    return redirect_response
                messages.error(request, "You do not have access to this portal.")
                return redirect("login")

        # 2) If username login fails, try client_id lookup.
        client_matches = list(Client.objects.select_related("user", "company").filter(client_id__iexact=identifier)[:2])
        if len(client_matches) == 1:
            client = client_matches[0]
            user = authenticate(request, username=client.user.username, password=password)
            if user is not None:
                login(request, user)
                company = client.company
                blocked = ensure_company_access_or_redirect(request, company)
                if blocked:
                    return blocked
                return redirect("client_dashboard")
        elif len(client_matches) > 1:
            client_user, auth_error = _authenticate_candidate_users(request, client_matches, password)
            if client_user is not None:
                login(request, client_user)
                client = Client.objects.select_related("company").get(user=client_user)
                company = client.company
                blocked = ensure_company_access_or_redirect(request, company)
                if blocked:
                    return blocked
                return redirect("client_dashboard")
            messages.error(request, auth_error or "Client ID exists in multiple companies. Please login using username.")
            return render(request, "login.html")

        # 3) Try staff_id lookup.
        staff_matches = list(Staff.objects.select_related("user", "company").filter(staff_id__iexact=identifier)[:5])
        if len(staff_matches) == 1:
            staff = staff_matches[0]
            user = authenticate(request, username=staff.user.username, password=password)
            if user is not None:
                login(request, user)
                company = staff.company
                blocked = ensure_company_access_or_redirect(request, company)
                if blocked:
                    return blocked
                return redirect("staff_dashboard")
        elif len(staff_matches) > 1:
            staff_user, auth_error = _authenticate_candidate_users(request, staff_matches, password)
            if staff_user is not None:
                login(request, staff_user)
                company = get_user_company(staff_user)
                blocked = ensure_company_access_or_redirect(request, company)
                if blocked:
                    return blocked
                return redirect("staff_dashboard")
            messages.error(request, auth_error or "Staff ID exists in multiple companies. Please login using your full login ID.")
            return render(request, "login.html")

        # 4) If still not found, try company business email login.
        company_matches = list(Company.objects.select_related("owner_user").filter(business_email__iexact=identifier)[:2])
        if len(company_matches) == 1:
            company = company_matches[0]
            user = authenticate(request, username=company.owner_user.username, password=password)
            if user is not None:
                login(request, user)
                blocked = ensure_company_access_or_redirect(request, company)
                if blocked:
                    return blocked
                return redirect("staff_dashboard")
        elif len(company_matches) > 1:
            messages.error(request, "Email exists for multiple companies. Please login using login ID.")
            return render(request, "login.html")

        if not use_direct_username_first:
            user = authenticate(request, username=identifier, password=password)
            if user is not None:
                redirect_response = _get_portal_redirect(request, user)
                if redirect_response is not None:
                    login(request, user)
                    return redirect_response
                messages.error(request, "You do not have access to this portal.")
                return redirect("login")

        messages.error(request, "Invalid login ID/client ID/email or password")

    return render(request, "login.html")

# ================================================================
# LOGOUT
# ================================================================
def user_logout(request):
    logout(request)
    return redirect("login")

# ================================================================
# ADMIN â€“ CLIENT LIST PAGE
# ================================================================
@login_required
def admin_view(request):
    if not is_company_manager(request.user):
        return redirect("login")
    company = get_admin_company(request)
    blocked = ensure_company_access_or_redirect(request, company)
    if blocked:
        return blocked
    clients = Client.objects.filter(company=company).order_by("client_name")
    cleanup_expired_notifications()
    return render(request, "admin_view/main.html", {"clients": clients})


# ================================================================
# ADMIN - STAFF LIST PAGE
# ================================================================
@login_required
def admin_staff_view(request):
    if not is_company_manager(request.user):
        return redirect("login")
    company = get_admin_company(request)
    blocked = ensure_company_access_or_redirect(request, company)
    if blocked:
        return blocked
    cleanup_expired_notifications()
    staffs = Staff.objects.select_related("user").filter(company=company)
    return render(request, "admin_view/staff_view.html", {
        "staffs": staffs,
        "can_add_staff": is_company_admin(request.user),
        "can_manage_staff": is_company_admin(request.user),
    })


# ================================================================
# ADMIN DASHBOARD (STATS PAGE)
# ================================================================
# def admin_dashboard(request):
#     return render(request, "admin_view/dashboard.html", {
#         "total_clients": Client.objects.count(),
#         "pending_count": Work.objects.filter(status="Pending").count(),
#         "ongoing_count": Work.objects.filter(status="Ongoing").count(),
#         "completed_count": Work.objects.filter(status="Completed").count(),

#         "entry_submitted": Entry.objects.filter(status="submitted").count(),
#         "entry_under_review": Entry.objects.filter(status="under_review").count(),
#         "entry_accepted": Entry.objects.filter(status="accepted").count(),
#         "entry_rejected": Entry.objects.filter(status="rejected").count(),
#         "entry_revised": Entry.objects.filter(status="revised").count(),

#         "recent_works": Work.objects.order_by("-created_at")[:10],
#     })

# ================================================================
# ADD CLIENT
# ================================================================
@login_required
@require_POST
def add_client(request):
    if not is_company_manager(request.user):
        return JsonResponse({"status": "error", "message": "Unauthorized"})
    company = get_admin_company(request)
    if company is None:
        return JsonResponse({"status": "error", "message": "No company available. Create/register a company first."})
    blocked = ensure_company_access_or_redirect(request, company)
    if blocked:
        return JsonResponse({"status": "error", "message": "Company plan expired. Renew to continue."})

    name = request.POST.get("client_name")
    client_id = request.POST.get("client_id")
    business_email = (request.POST.get("business_email") or "").strip()
    business_phone = (request.POST.get("business_phone") or "").strip()
    password = request.POST.get("password") or ""
    confirm_password = request.POST.get("confirm_password") or ""

    if not all([name, client_id, password, confirm_password]):
        return JsonResponse({"status": "error", "message": "All required fields must be filled."})

    if password != confirm_password:
        return JsonResponse({"status": "error", "message": "Passwords do not match."})

    password_ok, password_error = validate_password(password)
    if not password_ok:
        return JsonResponse({"status": "error", "message": password_error})

    if Client.objects.filter(company=company, client_id=client_id).exists():
        return JsonResponse({"status": "error", "message": "Client ID already exists!"})

    username = f"{company.code}__{client_id}"
    if CustomUser.objects.filter(username=username).exists():
        return JsonResponse({"status": "error", "message": "Client account already exists for this ID."})

    user = CustomUser.objects.create_user(
        username=username,
        password=password
    )
    client = Client.objects.create(
        company=company,
        user=user,
        client_name=name,
        client_id=client_id,
        business_email=business_email,
        business_phone=business_phone,
    )

    return JsonResponse({
        "status": "success",
        "message": "Client added successfully.",
        "client_id": client.id
    })


# ================================================================
# ADD STAFF
# ================================================================
@login_required
@require_POST
def add_staff(request):
    if not is_company_admin(request.user):
        return JsonResponse({"status": "error", "message": "Unauthorized"})
    company = get_admin_company(request)
    if company is None:
        return JsonResponse({"status": "error", "message": "No company available. Create/register a company first."})
    blocked = ensure_company_access_or_redirect(request, company)
    if blocked:
        return JsonResponse({"status": "error", "message": "Company plan expired. Renew to continue."})

    name = request.POST.get("staff_name")
    staff_id = request.POST.get("staff_id")
    password = request.POST.get("password") or ""
    confirm_password = request.POST.get("confirm_password") or ""

    if not all([name, staff_id, password, confirm_password]):
        return JsonResponse({"status": "error", "message": "All required fields must be filled."})

    if password != confirm_password:
        return JsonResponse({"status": "error", "message": "Passwords do not match."})

    password_ok, password_error = validate_password(password)
    if not password_ok:
        return JsonResponse({"status": "error", "message": password_error})

    if Staff.objects.filter(company=company, staff_id=staff_id).exists():
        return JsonResponse({"status": "error", "message": "Staff ID already exists!"})

    username = f"{company.code}__{staff_id}"
    if CustomUser.objects.filter(username=username).exists():
        return JsonResponse({"status": "error", "message": "Staff account already exists for this ID."})

    user = CustomUser.objects.create_user(
        username=username,
        password=password,
        is_staff=False,
    )

    staff = Staff.objects.create(
        company=company,
        user=user,
        staff_name=name,
        staff_id=staff_id,
    )

    return JsonResponse({
        "status": "success",
        "message": "Staff added successfully.",
        "staff_id": staff.id
    })


@login_required
@require_POST
def delete_staff(request, staff_id):
    if not is_company_admin(request.user):
        return JsonResponse({"status": "error", "message": "Unauthorized"})
    company = get_admin_company(request)
    staff = get_object_or_404(Staff, id=staff_id, company=company)

    if company is None or not company.has_active_access():
        return _request_delete_staff(request, staff)

    # Admin revokes staff access by deactivating the user account.
    staff.user.is_active = False
    staff.user.save(update_fields=["is_active"])
    return JsonResponse({"status": "success", "message": "Staff access revoked successfully."})


@login_required
@require_POST
def delete_client(request, client_id):
    if not is_company_manager(request.user):
        return JsonResponse({"status": "error", "message": "Unauthorized"})

    try:
        company = get_admin_company(request)
        client = get_object_or_404(Client, id=client_id, company=company)

        if not company.has_active_access() or (is_company_staff(request.user) and not is_company_admin(request.user)):
            return _request_delete_client(request, client)

        if is_company_admin(request.user):
            client.user.is_active = False
            client.user.save(update_fields=["is_active"])
            return JsonResponse({"status": "success", "message": "Client access revoked successfully."})

        return JsonResponse({"status": "error", "message": "Unauthorized"})
    except Exception:
        return JsonResponse({"status": "error", "message": "Failed to revoke client access"})


@login_required
@require_POST
def request_client_activate(request, client_id):
    if not is_company_manager(request.user):
        return JsonResponse({"status": "error", "message": "Unauthorized"})

    company = get_admin_company(request)
    client = get_object_or_404(Client, id=client_id, company=company)

    if is_company_admin(request.user):
        client.user.is_active = True
        client.user.save(update_fields=["is_active"])
        return JsonResponse({"status": "success", "message": "Client access activated successfully."})

    return _request_client_status_change(request, client, activate=True)


# ================================================================
# ADMIN → VIEW CLIENT WORK
# ================================================================
@login_required
def work_view(request, client_id):
    if not is_company_manager(request.user):
        return redirect("login")
    company = get_admin_company(request)
    blocked = ensure_company_access_or_redirect(request, company)
    if blocked:
        return blocked
    cleanup_expired_notifications()
    cleanup_expired_work_files()
    client = get_object_or_404(Client, id=client_id, company=company)
    works = Work.objects.filter(company=company, client=client).order_by("-id")

    return render(request, "admin_view/work_view.html", {
        "client": client,
        "works": works,
    })

 
# ================================================================
# ADD WORK
# ================================================================
@login_required
@require_POST
def add_work(request):
    if not is_company_manager(request.user):
        return JsonResponse({"status": "error", "message": "Unauthorized"})
    company = get_admin_company(request)
    if company is None:
        return JsonResponse({"status": "error", "message": "No company available."})
    blocked = ensure_company_access_or_redirect(request, company)
    if blocked:
        return JsonResponse({"status": "error", "message": "Company plan expired. Renew to continue."})
    
    client_id = request.POST.get("client_id")
    title = request.POST.get("title")
    deadline = request.POST.get("deadline")

    if not client_id or not title:
        return JsonResponse({"status": "error", "message": "Required fields missing"})

    client = get_object_or_404(Client, id=client_id, company=company)

    Work.objects.create(
        company=company,
        client=client,
        title=title,
        deadline=deadline,
        description=request.POST.get("description", ""),
        status=request.POST.get("status", "Pending")
    )

    return JsonResponse({"status": "success"})

# ================================================================
# UPDATE WORK
# ================================================================
@login_required
@require_POST
def update_work(request, work_id):
    if not is_company_manager(request.user):
        return JsonResponse({"status": "error", "message": "Unauthorized"})
    company = get_admin_company(request)
    blocked = ensure_company_access_or_redirect(request, company)
    if blocked:
        return JsonResponse({"status": "error", "message": "Company plan expired. Renew to continue."})
    work = get_object_or_404(Work, id=work_id, company=company)

    if request.method == "POST":
        work.title = request.POST.get("title")
        work.description = request.POST.get("description")
        work.status = request.POST.get("status")
        work.deadline = request.POST.get("deadline")
        work.save()

        return JsonResponse({
            "status": "success",
            "message": "Work updated successfully"
        })

# ================================================================
# DELETE WORK
# ================================================================
@login_required
@require_POST
def delete_work(request, work_id):
    if not is_company_manager(request.user):
        return JsonResponse({"status": "error", "message": "Unauthorized"})

    try:
        company = get_admin_company(request)
        work = get_object_or_404(Work, id=work_id, company=company)

        if not company.has_active_access():
            return _request_delete_work(request, work)

        if is_company_staff(request.user) and not is_company_admin(request.user):
            return _request_delete_work(request, work)

        _delete_work_and_assets(work)
        return JsonResponse({"status": "success", "message": "Work deleted successfully"})
    except Exception:
        return JsonResponse({"status": "error", "message": "Failed to delete"})
    
# ================================================================
# CLIENT DASHBOARD
# ================================================================
@login_required
def client_dashboard(request):
    if is_platform_owner(request.user):
        return redirect("platform_dashboard")
    if is_company_manager(request.user):
        return redirect("staff_dashboard")

    cleanup_expired_notifications()
    cleanup_expired_work_files()
    client = Client.objects.select_related("company").get(user=request.user)
    blocked = ensure_company_access_or_redirect(request, client.company)
    if blocked:
        return blocked
    works = client.works.all()
    notifications = get_active_notifications_for_user(request.user)[:10]

    return render(request, "client_view/main.html", {
        "client": client,
        "works": works,
        "total_works": works.count(),
        "ongoing_works": works.filter(status="Ongoing").count(),
        "completed_works": works.filter(status="Completed").count(),
        "notifications": notifications,
        # "total_entries": Entry.objects.filter(work__client=client).count(),
    })


@login_required
def client_tasks(request):
    if is_platform_owner(request.user):
        return redirect("platform_dashboard")
    if is_company_manager(request.user):
        return redirect("staff_dashboard")

    cleanup_expired_work_files()
    client = get_object_or_404(Client.objects.select_related("company"), user=request.user)
    blocked = ensure_company_access_or_redirect(request, client.company)
    if blocked:
        return blocked
    works = client.works.all().order_by("-created_at")

    return render(request, "client_view/tasks.html", {
        "client": client,
        "works": works,
    })


@login_required
def company_billing(request):
    if is_platform_owner(request.user):
        if not request.session.get("admin_company_id"):
            return redirect("platform_dashboard")
    if not is_company_admin(request.user):
        return redirect("staff_dashboard")

    company = get_admin_company(request)
    if company is None:
        return redirect("platform_dashboard" if is_platform_owner(request.user) else "login")
    snapshot = get_company_access_snapshot(company)
    payments = company.payment_requests.all()[:10]

    return render(request, "company_billing.html", {
        "company": company,
        "plan_snapshot": snapshot,
        "payments": payments,
        "plan_options": get_plan_options(),
        "website_settings": WebsiteSettings.get_settings(),
    })


@login_required
@require_POST
def submit_payment_request(request):
    if not is_company_admin(request.user):
        return JsonResponse({"status": "error", "message": "Unauthorized"})

    company = get_admin_company(request)
    if company is None:
        return JsonResponse({"status": "error", "message": "No company available."})
    transaction_reference = (request.POST.get("transaction_reference") or "").strip()
    note = (request.POST.get("note") or "").strip()
    selected_plan = (request.POST.get("selected_plan") or "base").strip().lower()

    if not transaction_reference:
        return JsonResponse({"status": "error", "message": "Transaction reference is required."})

    if SubscriptionPaymentRequest.objects.filter(transaction_reference__iexact=transaction_reference).exists():
        return JsonResponse({"status": "error", "message": "Transaction reference already exists."})

    plan_option = next((plan for plan in get_plan_options() if plan["value"] == selected_plan), None)
    if plan_option is None:
        return JsonResponse({"status": "error", "message": "Invalid plan selected."})

    if plan_option.get("contact_only"):
        return JsonResponse({"status": "error", "message": "Please contact us for Enterprise pricing."})

    amount = plan_option["price"]
    duration_days = plan_option["duration_days"]

    if amount < 0:
        return JsonResponse({"status": "error", "message": "Invalid amount."})

    SubscriptionPaymentRequest.objects.create(
        company=company,
        amount=amount,
        transaction_reference=transaction_reference,
        selected_plan=selected_plan,
        duration_days=duration_days,
        note=note,
    )
    return JsonResponse({"status": "success", "message": f"{plan_option['name']} request submitted. Waiting for admin approval."})


@login_required
@require_POST
def review_payment_request(request, payment_id):
    if not is_platform_owner(request.user):
        return JsonResponse({"status": "error", "message": "Unauthorized"})

    action = (request.POST.get("action") or "").strip().lower()
    payment = get_object_or_404(SubscriptionPaymentRequest.objects.select_related("company"), id=payment_id)

    if payment.status != SubscriptionPaymentRequest.STATUS_PENDING:
        return JsonResponse({"status": "error", "message": "This payment request has already been reviewed."})

    if action not in {"approve", "reject"}:
        return JsonResponse({"status": "error", "message": "Invalid action."})

    payment.reviewed_by = request.user
    payment.reviewed_at = timezone.now()

    if action == "approve":
        payment.status = SubscriptionPaymentRequest.STATUS_APPROVED
        company = payment.company
        base_date = timezone.now()
        if company.plan_expires_at and company.plan_expires_at > base_date:
            base_date = company.plan_expires_at

        company.plan_expires_at = base_date + timedelta(days=payment.duration_days)
        company.plan_status = Company.STATUS_ACTIVE
        company.monthly_price = payment.amount
        company.save(update_fields=["plan_expires_at", "plan_status", "monthly_price"])
        payment.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        send_payment_review_email(payment, approved=True)
        return JsonResponse({"status": "success", "message": "Payment approved and subscription extended."})

    payment.status = SubscriptionPaymentRequest.STATUS_REJECTED
    payment.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    send_payment_review_email(payment, approved=False)
    return JsonResponse({"status": "success", "message": "Payment request rejected."})


@login_required
def toggle_company_access(request, company_id):
    if not is_platform_owner(request.user):
        messages.error(request, "Only platform owner can manage company access.")
        return redirect("platform_dashboard")

    company = get_object_or_404(Company, id=company_id)
    was_active = company.is_active
    company.is_active = not company.is_active
    company.save(update_fields=["is_active"])

    if company.is_active:
        messages.success(
            request,
            f"✓ Company '{company.name}' access has been ACTIVATED. They can now perform all operations directly.",
        )
    else:
        messages.warning(
            request,
            f"⚠ Company '{company.name}' access has been REVOKED. All their delete requests must now go through admin approval.",
        )

    return redirect("platform_dashboard")


@login_required
def platform_dashboard(request):
    if not is_platform_owner(request.user):
        return redirect("login")

    companies = Company.objects.select_related("owner_user").all().order_by("name")
    payments = SubscriptionPaymentRequest.objects.select_related("company").all()
    pending_payments = payments.filter(status=SubscriptionPaymentRequest.STATUS_PENDING)[:8]
    pending_deletion_requests = DeletionRequest.objects.select_related("company", "requested_by").filter(
        status=DeletionRequest.STATUS_PENDING,
        company__is_active=False,
    )[:10]

    total_companies = companies.count()
    active_count = sum(1 for c in companies if c.has_active_access())
    expired_count = max(total_companies - active_count, 0)
    trial_count = sum(1 for c in companies if c.get_access_state()[0] == "trial")

    return render(request, "admin_view/platform_dashboard.html", {
        "website_settings": WebsiteSettings.get_settings(),
        "total_companies": total_companies,
        "active_count": active_count,
        "expired_count": expired_count,
        "trial_count": trial_count,
        "recent_companies": companies.order_by("-created_at")[:8],
        "pending_payments": pending_payments,
        "pending_deletion_requests": pending_deletion_requests,
    })


@login_required
def enter_company_admin(request, company_id):
    if not is_platform_owner(request.user):
        return redirect("login")
    get_object_or_404(Company, id=company_id)
    request.session["admin_company_id"] = company_id
    messages.success(request, "You are now managing this company as its admin.")
    return redirect("company_dashboard")


@login_required
def exit_company_admin(request):
    if not is_platform_owner(request.user):
        return redirect("login")
    request.session.pop("admin_company_id", None)
    return redirect("platform_dashboard")


@login_required
def admin_subscriptions(request):
    if not is_platform_owner(request.user):
        return redirect("login")

    companies = Company.objects.select_related("owner_user").all().order_by("name")
    payments = SubscriptionPaymentRequest.objects.select_related("company").all()
    active_count = sum(1 for c in companies if c.has_active_access())
    expired_count = max(companies.count() - active_count, 0)
    return render(request, "admin_view/subscriptions.html", {
        "website_settings": WebsiteSettings.get_settings(),
        "companies": companies,
        "payments": payments,
        "active_count": active_count,
        "expired_count": expired_count,
        "has_owned_company": is_company_admin(request.user),
    })


@login_required
def work_entry_view(request, work_id):
    if not is_company_manager(request.user):
        return redirect("login")
    company = get_admin_company(request)
    work = get_object_or_404(Work, id=work_id, company=company)
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # AJAX request → return partial HTML
        return render(request, 'admin_view/partials/_upload_article.html', {'work': work})
    
    # Optional: full page render for non-AJAX (if needed)
    return render(request, 'admin_view/work_entry_fullpage.html', {'work': work})

from django.template.loader import render_to_string

@login_required
def upload_images(request, work_id):
    cleanup_expired_work_files()
    work = get_object_or_404(Work.objects.select_related("company", "client"), id=work_id)
    is_manager = is_company_manager(request.user)
    user_company = get_admin_company(request)

    if not user_company or work.company_id != user_company.id:
        return JsonResponse({"status": "error", "message": "Unauthorized"})

    blocked = ensure_company_access_or_redirect(request, user_company)
    if blocked:
        return JsonResponse({"status": "error", "message": "Company plan expired. Renew to continue access."})

    if not is_manager:
        try:
            client = Client.objects.get(user=request.user, company=user_company)
        except Client.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Unauthorized"})

        if work.client_id != client.id:
            return JsonResponse({"status": "error", "message": "Unauthorized"})

    if request.method == "POST":
        if not is_manager:
            return JsonResponse({"status": "error", "message": "Only admin/staff can upload files."})

        files = request.FILES.getlist("files")
        if not files:
            return JsonResponse({"status": "error", "message": "Please choose at least one file."})

        max_size = 200 * 1024 * 1024
        for f in files:
            if f.size > max_size:
                return JsonResponse({
                    "status": "error",
                    "message": f"{f.name} exceeds 200MB size limit."
                })

            if not _is_allowed_upload_extension(f.name):
                return JsonResponse({
                    "status": "error",
                    "message": f"{f.name} has an unsupported file type."
                })

        expires_at = timezone.now() + timedelta(days=7)
        for f in files:
            WorkFile.objects.create(
                work=work,
                file=f,
                original_name=f.name,
                uploaded_by=request.user,
                expires_at=expires_at
            )

        work_files = work.files.filter(expires_at__gt=timezone.now())
        file_groups = categorize_work_files(work_files)
        html = render_to_string(
            "admin_view/partials/_image_grid.html",
            {
                "files": work_files,
                "file_groups": file_groups,
                "can_delete_files": is_manager,
            },
            request=request
        )

        return JsonResponse({
            "status": "success",
            "message": "Files uploaded successfully.",
            "html": html
        })

    work_files = work.files.filter(expires_at__gt=timezone.now())
    file_groups = categorize_work_files(work_files)

    context = {
        "work": work,
        "files": work_files,
        "file_groups": file_groups,
        "can_delete_files": is_manager,
        "can_upload_files": is_manager,
    }

    if is_manager:
        return render(request, "admin_view/partials/_upload_images.html", context)
    return render(request, "client_view/upload_files.html", context)

@login_required
@require_POST
def delete_image(request, image_id):
    if not is_company_manager(request.user):
        return JsonResponse({"status": "error", "message": "Unauthorized"})

    if request.method == "POST":
        company = get_admin_company(request)
        work_file = get_object_or_404(WorkFile.objects.select_related("work"), id=image_id, work__company=company)

        if work_file.file:
            work_file.file.delete(save=False)
        work_file.delete()

        return JsonResponse({"status": "success", "message": "File deleted"})

    return JsonResponse({"status": "error"})


@login_required
def client_work_detail(request, work_id):
    if is_platform_owner(request.user):
        return redirect("platform_dashboard")
    if is_company_manager(request.user):
        return redirect("staff_dashboard")

    cleanup_expired_work_files()
    client = get_object_or_404(Client.objects.select_related("company"), user=request.user)
    blocked = ensure_company_access_or_redirect(request, client.company)
    if blocked:
        return blocked
    name = client.client_name if client else "Unknown Client"

    work = get_object_or_404(
        Work.objects.prefetch_related("files"),
        id=work_id,
        client=client
    )

    active_files = work.files.filter(expires_at__gt=timezone.now())
    context = {
        "work": work,
        "files": active_files,
        "file_groups": categorize_work_files(active_files),
        "client": client,
        "name": name,
        "can_delete_files": False,
    }

    return render(request, "client_view/work_detail.html", context)


@login_required
def preview_work_file(request, file_id):
    cleanup_expired_work_files()
    work_file = get_object_or_404(WorkFile, id=file_id)

    can_access = False
    if is_company_manager(request.user):
        company = get_admin_company(request)
        can_access = company is not None and work_file.work.company_id == company.id and company.has_active_access()
    else:
        try:
            client = Client.objects.select_related("company").get(user=request.user)
            can_access = (work_file.work.client_id == client.id) and client.company.has_active_access()
        except Client.DoesNotExist:
            can_access = False

    if not can_access:
        raise Http404("File not found")

    guessed_type, _ = mimetypes.guess_type(work_file.file.name)
    content_type = guessed_type or "application/octet-stream"

    response = FileResponse(work_file.file.open("rb"), content_type=content_type)
    response["Content-Disposition"] = f'inline; filename="{work_file.original_name}"'
    return response


@login_required
def download_work_file(request, file_id):
    cleanup_expired_work_files()
    work_file = get_object_or_404(WorkFile, id=file_id)

    can_access = False
    if is_company_manager(request.user):
        company = get_admin_company(request)
        can_access = company is not None and work_file.work.company_id == company.id and company.has_active_access()
    else:
        try:
            client = Client.objects.select_related("company").get(user=request.user)
            can_access = (work_file.work.client_id == client.id) and client.company.has_active_access()
        except Client.DoesNotExist:
            can_access = False

    if not can_access:
        raise Http404("File not found")

    guessed_type, _ = mimetypes.guess_type(work_file.file.name)
    content_type = guessed_type or "application/octet-stream"

    response = FileResponse(work_file.file.open("rb"), content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{work_file.original_name}"'
    return response


# ================================================================
# ADMIN DASHBOARD
# ================================================================
@login_required
def admin_dashboard(request):
    """Admin dashboard with statistics and overview"""
    if not is_platform_owner(request.user):
        return redirect("login")
    return redirect("platform_dashboard")


@login_required
def staff_dashboard(request):
    """Company dashboard for company admin/staff"""
    if not is_company_manager(request.user):
        return redirect("login")
    company = get_admin_company(request)
    blocked = ensure_company_access_or_redirect(request, company)
    if blocked:
        return blocked

    cleanup_expired_notifications()

    total_clients = Client.objects.filter(company=company).count()
    pending_count = Work.objects.filter(company=company, status="Pending").count()
    ongoing_count = Work.objects.filter(company=company, status="Ongoing").count()
    completed_count = Work.objects.filter(company=company, status="Completed").count()
    total_works = Work.objects.filter(company=company).count()

    recent_works = Work.objects.filter(company=company).order_by("-created_at")[:10]
    recent_clients = Client.objects.filter(company=company).order_by("-created_at")[:5]

    settings = CompanySettings.get_for_company(company)
    completion_rate = (completed_count / total_works * 100) if total_works > 0 else 0

    context = {
        "total_clients": total_clients,
        "total_works": total_works,
        "pending_count": pending_count,
        "ongoing_count": ongoing_count,
        "completed_count": completed_count,
        "completion_rate": round(completion_rate, 1),
        "recent_works": recent_works,
        "recent_clients": recent_clients,
        "settings": settings,
        "website_settings": WebsiteSettings.get_settings() if is_platform_owner(request.user) else None,
        "dashboard_title": f"{company.name} Company Dashboard",
    }

    return render(request, "admin_view/company_dashboard.html", context)


# ================================================================
# SETTINGS PAGES
# ================================================================
@login_required
def admin_settings(request):
    """Global website settings (platform owner only)."""
    if not is_platform_owner(request.user):
        messages.error(request, "Only platform owner can manage website settings.")
        if is_company_manager(request.user):
            return redirect("staff_dashboard")
        return redirect("login")

    settings = WebsiteSettings.get_settings()

    if request.method == "POST":
        for field_name in ["free_plan_price", "base_plan_price", "premium_plan_price", "enterprise_plan_price"]:
            raw_value = request.POST.get(field_name, "")
            if raw_value == "":
                continue
            try:
                setattr(settings, field_name, Decimal(raw_value))
            except InvalidOperation:
                messages.error(request, f"{field_name.replace('_', ' ').title()} must be a valid amount.")
                return redirect("admin_settings")

        settings.site_name = request.POST.get("site_name", settings.site_name)
        settings.site_description = request.POST.get("site_description", settings.site_description)
        settings.phone = request.POST.get("phone", settings.phone)
        settings.email = request.POST.get("email", settings.email)
        settings.address = request.POST.get("address", settings.address)

        settings.facebook_url = request.POST.get("facebook_url", settings.facebook_url)
        settings.instagram_url = request.POST.get("instagram_url", settings.instagram_url)
        settings.twitter_url = request.POST.get("twitter_url", settings.twitter_url)
        settings.linkedin_url = request.POST.get("linkedin_url", settings.linkedin_url)

        settings.maintenance_mode = request.POST.get("maintenance_mode") == "on"
        settings.allow_client_registration = request.POST.get("allow_client_registration") == "on"
        settings.show_testimonials = request.POST.get("show_testimonials") == "on"
        settings.show_portfolio = request.POST.get("show_portfolio") == "on"

        settings.maintenance_message = request.POST.get("maintenance_message", settings.maintenance_message)
        settings.welcome_message = request.POST.get("welcome_message", settings.welcome_message)

        if "site_logo" in request.FILES:
            settings.site_logo = request.FILES["site_logo"]

        settings.save()
        messages.success(request, "Website settings updated successfully!")
        return redirect("admin_settings")

    context = {"settings": settings, "settings_scope": "website"}
    return render(request, "admin_view/settings.html", context)


@login_required
def settings_switch(request):
    """Switch page for platform owner to navigate between website and company settings."""
    if not is_platform_owner(request.user):
        messages.error(request, "Only platform owner can access settings switch.")
        if is_company_manager(request.user):
            return redirect("staff_dashboard")
        return redirect("login")

    context = {
        "has_owned_company": is_company_admin(request.user),
    }
    return render(request, "admin_view/settings_switch.html", context)


@login_required
def company_settings(request):
    """Per-company settings (company admin only)."""
    if not is_company_admin(request.user):
        messages.error(request, "Only company admin can manage company settings.")
        return redirect("staff_dashboard" if is_company_staff(request.user) else "login")

    company = get_admin_company(request)
    if company is None:
        messages.error(request, "No company found for this account.")
        return redirect("platform_dashboard" if is_platform_owner(request.user) else "login")

    settings = CompanySettings.get_for_company(company)
    company_clients = Client.objects.filter(company=company).order_by("client_name")
    company_staffs = Staff.objects.select_related("user").filter(company=company).order_by("staff_name")
    
    if request.method == "POST":
        if any(key in request.POST for key in ["free_plan_price", "base_plan_price", "premium_plan_price", "enterprise_plan_price"]):
            messages.error(request, "Only the super admin can update plan pricing.")
            return redirect("company_settings")

        form_action = (request.POST.get("form_action") or "").strip()

        if form_action == "reset_client_password":
            client_pk = (request.POST.get("client_pk") or "").strip()
            new_password = request.POST.get("new_password") or ""
            confirm_password = request.POST.get("confirm_password") or ""

            if not client_pk or not new_password or not confirm_password:
                messages.error(request, "Please select client and enter both password fields.")
                return redirect("company_settings")
            if new_password != confirm_password:
                messages.error(request, "Client password confirmation does not match.")
                return redirect("company_settings")
            if len(new_password) < 8:
                messages.error(request, "Client password must be at least 8 characters.")
                return redirect("company_settings")

            client_obj = Client.objects.filter(id=client_pk, company=company).select_related("user").first()
            if not client_obj:
                messages.error(request, "Invalid client selected.")
                return redirect("company_settings")

            client_obj.user.set_password(new_password)
            client_obj.user.save(update_fields=["password"])
            messages.success(request, f"Password updated for client {client_obj.client_name}.")
            return redirect("company_settings")

        if form_action == "reset_staff_password":
            staff_pk = (request.POST.get("staff_pk") or "").strip()
            new_password = request.POST.get("new_password") or ""
            confirm_password = request.POST.get("confirm_password") or ""

            if not staff_pk or not new_password or not confirm_password:
                messages.error(request, "Please select staff and enter both password fields.")
                return redirect("company_settings")
            if new_password != confirm_password:
                messages.error(request, "Staff password confirmation does not match.")
                return redirect("company_settings")
            if len(new_password) < 8:
                messages.error(request, "Staff password must be at least 8 characters.")
                return redirect("company_settings")

            staff_obj = Staff.objects.filter(id=staff_pk, company=company).select_related("user").first()
            if not staff_obj:
                messages.error(request, "Invalid staff selected.")
                return redirect("company_settings")

            staff_obj.user.set_password(new_password)
            staff_obj.user.save(update_fields=["password"])
            messages.success(request, f"Password updated for staff {staff_obj.staff_name}.")
            return redirect("company_settings")

        settings.site_name = request.POST.get("site_name", settings.site_name)
        settings.site_description = request.POST.get("site_description", settings.site_description)
        settings.phone = request.POST.get("phone", settings.phone)
        settings.email = request.POST.get("email", settings.email)
        settings.address = request.POST.get("address", settings.address)
        
        settings.facebook_url = request.POST.get("facebook_url", settings.facebook_url)
        settings.instagram_url = request.POST.get("instagram_url", settings.instagram_url)
        settings.twitter_url = request.POST.get("twitter_url", settings.twitter_url)
        settings.linkedin_url = request.POST.get("linkedin_url", settings.linkedin_url)
        
        settings.maintenance_mode = request.POST.get("maintenance_mode") == "on"
        settings.allow_client_registration = request.POST.get("allow_client_registration") == "on"
        settings.show_testimonials = request.POST.get("show_testimonials") == "on"
        settings.show_portfolio = request.POST.get("show_portfolio") == "on"
        
        settings.maintenance_message = request.POST.get("maintenance_message", settings.maintenance_message)
        settings.welcome_message = request.POST.get("welcome_message", settings.welcome_message)
        
        if "site_logo" in request.FILES:
            settings.site_logo = request.FILES["site_logo"]
        
        settings.save()
        messages.success(request, "Company settings updated successfully!")
        return redirect("company_settings")
    
    context = {
        "settings": settings,
        "settings_scope": "company",
        "company_clients": company_clients,
        "company_staffs": company_staffs,
    }
    return render(request, "admin_view/settings.html", context)


# ================================================================
# NOTIFICATION MANAGEMENT
# ================================================================
@login_required
def notifications_page(request):
    if not is_company_manager(request.user):
        return redirect("login")
    company = get_admin_company(request)
    blocked = ensure_company_access_or_redirect(request, company)
    if blocked:
        return blocked

    cleanup_expired_notifications()
    notifications = Notification.objects.filter(
        company=company,
        expires_at__gt=timezone.now()
    ).filter(
        Q(sender=request.user) | Q(recipient=request.user)
    ).select_related("sender", "recipient", "deletion_request", "deletion_request__requested_by", "deletion_request__reviewed_by")

    return render(request, "admin_view/notifications.html", {
        "notifications": notifications,
        "can_send_to_staff": is_company_admin(request.user),
        "can_delete_notifications": is_company_admin(request.user),
    })


@login_required
@require_POST
def send_notification(request):
    if not is_company_admin(request.user):
        return redirect("login")
    company = get_admin_company(request)
    blocked = ensure_company_access_or_redirect(request, company)
    if blocked:
        return blocked

    message = (request.POST.get("message") or "").strip()
    target = (request.POST.get("target") or "").strip()

    if not message:
        messages.error(request, "Notification message is required.")
        return redirect("notifications_page")

    allowed_targets = {"clients", "staffs", "clients_staffs"}

    if target not in allowed_targets:
        messages.error(request, "Invalid notification target.")
        return redirect("notifications_page")

    recipients = []

    if target in {"clients", "clients_staffs"}:
        recipients.extend(CustomUser.objects.filter(client__company=company))
    if target in {"staffs", "clients_staffs"}:
        recipients.extend(CustomUser.objects.filter(staff__company=company))

    recipient_map = {}
    for user in recipients:
        if user.id != request.user.id:
            recipient_map[user.id] = user

    unique_recipients = list(recipient_map.values())
    now = timezone.now()
    expires_at = now + timedelta(days=1)

    rows = []
    for recipient in unique_recipients:
        recipient_company = get_user_company(recipient)
        if recipient_company:
            rows.append(Notification(
                company=recipient_company,
                sender=request.user,
                recipient=recipient,
                message=message,
                expires_at=expires_at
            ))
    Notification.objects.bulk_create(rows)

    messages.success(request, f"Notification sent to {len(rows)} users.")
    return redirect("notifications_page")


@login_required
@require_POST
def delete_notification(request, notification_id):
    if is_company_admin(request.user):
        company = get_admin_company(request)
        notification = get_object_or_404(Notification, id=notification_id, company=company)
    else:
        return JsonResponse({"status": "error", "message": "Unauthorized"})
    notification.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"status": "success"})

    messages.success(request, "Notification deleted.")
    return redirect("notifications_page")


@login_required
@require_POST
def handle_deletion_request(request, request_id):
    action = (request.POST.get("action") or "").strip().lower()
    deletion_request = get_object_or_404(
        DeletionRequest.objects.select_related("requested_by", "company"),
        id=request_id,
    )

    company = deletion_request.company
    if company and company.has_active_access():
        if not is_company_admin(request.user):
            return JsonResponse({"status": "error", "message": "Unauthorized"})
        user_company = get_admin_company(request)
        if not user_company or user_company.id != company.id:
            return JsonResponse({"status": "error", "message": "Unauthorized"})
    else:
        if not is_platform_owner(request.user):
            return JsonResponse({"status": "error", "message": "Unauthorized"})

    if deletion_request.status != DeletionRequest.STATUS_PENDING:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"status": "error", "message": "This delete request has already been processed."})
        messages.error(request, "This delete request has already been processed.")
        return redirect("notifications_page")

    now = timezone.now()

    if action == "approve":
        if deletion_request.target_type == DeletionRequest.TARGET_CLIENT:
            client = Client.objects.filter(id=deletion_request.target_id).first()
            if client:
                _delete_client_and_assets(client)
        elif deletion_request.target_type == DeletionRequest.TARGET_CLIENT_DEACTIVATE:
            client = Client.objects.filter(id=deletion_request.target_id).select_related('user').first()
            if client and client.user:
                client.user.is_active = False
                client.user.save(update_fields=['is_active'])
        elif deletion_request.target_type == DeletionRequest.TARGET_CLIENT_ACTIVATE:
            client = Client.objects.filter(id=deletion_request.target_id).select_related('user').first()
            if client and client.user:
                client.user.is_active = True
                client.user.save(update_fields=['is_active'])
        elif deletion_request.target_type == DeletionRequest.TARGET_WORK:
            work = Work.objects.filter(id=deletion_request.target_id).first()
            if work:
                _delete_work_and_assets(work)
        elif deletion_request.target_type == DeletionRequest.TARGET_STAFF:
            staff = Staff.objects.filter(id=deletion_request.target_id).first()
            if staff:
                _delete_staff_and_assets(staff)
        else:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"status": "error", "message": "Invalid delete request target."})
            messages.error(request, "Invalid delete request target.")
            return redirect("notifications_page")

        deletion_request.status = DeletionRequest.STATUS_APPROVED
        staff_message = "Your delete request has been approved by admin."
        success_message = "Delete request approved and completed."
    elif action == "reject":
        deletion_request.status = DeletionRequest.STATUS_REJECTED
        staff_message = "Your delete request has been rejected by admin."
        success_message = "Delete request rejected."
    else:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"status": "error", "message": "Invalid action."})
        messages.error(request, "Invalid action.")
        return redirect("notifications_page")

    deletion_request.reviewed_by = request.user
    deletion_request.reviewed_at = now
    deletion_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])

    Notification.objects.filter(deletion_request=deletion_request).delete()
    Notification.objects.create(
        company=deletion_request.company,
        sender=request.user,
        recipient=deletion_request.requested_by,
        message=staff_message,
        deletion_request=deletion_request,
        expires_at=now + timedelta(days=7),
    )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"status": "success", "message": success_message})

    messages.success(request, success_message)
    if is_platform_owner(request.user):
        return redirect("platform_dashboard")
    return redirect("notifications_page")


from django.utils import timezone


def notification_context(request):
    default_context = {
        "notification_count": 0,
        "is_platform_owner": False,
        "is_company_admin": False,
        "is_company_staff": False,
        "current_company": None,
        "current_company_settings": None,
        "admin_workspace_mode": "company",
        "managing_company": False,
        "show_platform_workspace": False,
        "show_company_workspace": False,
        "show_company_controls": False,
    }
    if not request.user.is_authenticated:
        return default_context

    try:
        from MyApp.models import Notification, Company, Staff, Client, CompanySettings

        count = Notification.objects.filter(
            recipient=request.user,
            expires_at__gt=timezone.now()
        ).count()
        is_platform_owner = bool(request.user.is_superuser)
        managing_company = bool(request.session.get("admin_company_id")) if is_platform_owner else False
        owns_company = Company.objects.filter(owner_user=request.user).exists()
        is_company_admin = managing_company or (owns_company and not is_platform_owner)
        is_company_staff = Staff.objects.filter(user=request.user).exists()
        current_company = None
        current_company_settings = None

        if managing_company:
            selected_company_id = request.session.get("admin_company_id")
            current_company = Company.objects.filter(id=selected_company_id).first() if selected_company_id else None
        elif owns_company and not is_platform_owner:
            current_company = Company.objects.filter(owner_user=request.user).first()
        elif is_company_staff:
            staff_row = Staff.objects.select_related("company").filter(user=request.user).first()
            current_company = staff_row.company if staff_row else None
        else:
            client_row = Client.objects.select_related("company").filter(user=request.user).first()
            current_company = client_row.company if client_row else None

        if current_company:
            current_company_settings = CompanySettings.get_for_company(current_company)

        url_name = ""
        if getattr(request, "resolver_match", None):
            url_name = request.resolver_match.url_name or ""
        platform_pages = {
            "admin_dashboard",
            "admin_subscriptions",
            "platform_dashboard",
            "admin_settings",
            "settings_switch",
        }
        admin_workspace_mode = "company" if managing_company or not is_platform_owner else "platform"

        return {
            "notification_count": count,
            "is_platform_owner": is_platform_owner,
            "is_company_admin": is_company_admin,
            "is_company_staff": is_company_staff,
            "current_company": current_company,
            "current_company_settings": current_company_settings,
            "admin_workspace_mode": admin_workspace_mode,
            "managing_company": managing_company,
            "show_platform_workspace": is_platform_owner and not managing_company,
            "show_company_workspace": managing_company or not is_platform_owner,
            "show_company_controls": managing_company or (not is_platform_owner and (is_company_admin or is_company_staff)),
        }
    except Exception:
        return default_context


from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('crm/', views.crm_landing, name='crm_landing'),
    path('login/', views.login_view, name='login'),
    path("register-company/", views.register_company, name="register_company"),
    path("logout/", views.user_logout, name="logout"),
    
    # -------------------------------
    # ADMIN PAGES
    # -------------------------------
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/platform-dashboard/", views.platform_dashboard, name="platform_dashboard"),
    path("admin/company-toggle/<int:company_id>/", views.toggle_company_access, name="toggle_company_access"),
    path("staff/dashboard/", views.staff_dashboard, name="staff_dashboard"),
    path("company/dashboard/", views.staff_dashboard, name="company_dashboard"),
    path("admin/clients/", views.admin_view, name="admin_view"),
    path("admin/staffs/", views.admin_staff_view, name="admin_staff_view"),
    path("admin/settings-switch/", views.settings_switch, name="settings_switch"),
    path("admin/settings/", views.admin_settings, name="admin_settings"),
    path("company/settings/", views.company_settings, name="company_settings"),
    path("admin/notifications/", views.notifications_page, name="notifications_page"),
    path("admin/subscriptions/", views.admin_subscriptions, name="admin_subscriptions"),
    path("admin/company-enter/<int:company_id>/", views.enter_company_admin, name="enter_company_admin"),
    path("admin/company-exit/", views.exit_company_admin, name="exit_company_admin"),
    
    # -------------------------------
    # CLIENT PAGES
    # -------------------------------
    path("add-client/", views.add_client, name="add_client"),
    path("add-staff/", views.add_staff, name="add_staff"),
    path("send-notification/", views.send_notification, name="send_notification"),
    path("delete-notification/<int:notification_id>/", views.delete_notification, name="delete_notification"),
    path("deletion-request/<int:request_id>/", views.handle_deletion_request, name="handle_deletion_request"),
    path("payment-review/<int:payment_id>/", views.review_payment_request, name="review_payment_request"),
    path("delete-client/<int:client_id>/", views.delete_client, name="delete_client"),
    path("delete-staff/<int:staff_id>/", views.delete_staff, name="delete_staff"),
    
    # Client dashboard only for logged-in client
    path("client/dashboard/", views.client_dashboard, name="client_dashboard"),
    path("client/tasks/", views.client_tasks, name="client_tasks"),
    path("company/billing/", views.company_billing, name="company_billing"),
    path("company/submit-payment/", views.submit_payment_request, name="submit_payment_request"),

    # -------------------------------
    # WORK MANAGEMENT
    # -------------------------------
    path("client/<int:client_id>/work/", views.work_view, name="work_view"),
    path("work/add/", views.add_work, name="add_work"),
    path("work/update/<int:work_id>/", views.update_work, name="update_work"),
    path("work/delete/<int:work_id>/", views.delete_work, name="delete_work"),
    
    # path("work/<int:work_id>/entry/", views.work_entry_view, name="entry_data"),
    
    # path('work/<int:work_id>/upload/', views.upload_file, name='upload_file'),
    # path('work/<int:work_id>/files/', views.list_files, name='list_files'),
    # path('file/<int:file_id>/delete/', views.delete_file, name='delete_file'),
    path("work/<int:work_id>/upload-images/", views.upload_images, name="upload_images"),
    path("work/file/<int:file_id>/preview/", views.preview_work_file, name="preview_work_file"),
    path("work/file/<int:file_id>/download/", views.download_work_file, name="download_work_file"),
    path("client/work/<int:work_id>/", views.client_work_detail, name="client_work_detail"),

    path(
    "delete-image/<int:image_id>/",
    views.delete_image,
    name="delete_image"
),
]

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Public & Auth URLs
    path('', views.home, name='home'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/patient/', views.patient_register, name='patient_register'),
    path('register/doctor/', views.doctor_register, name='doctor_register'),
    path('dashboard/redirect/', views.dashboard_redirect, name='dashboard_redirect'),

    # Password Reset & Change URLs
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='appointments/password_reset.html',
        email_template_name='appointments/password_reset_email.html',
        success_url='/password-reset/done/'
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='appointments/password_reset_sent.html'
    ), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='appointments/password_reset_confirm.html',
        success_url='/password-reset/complete/'
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='appointments/password_reset_complete.html'
    ), name='password_reset_complete'),
    path('password-change/', views.change_password, name='password_change'),

    # Dashboards
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/doctor/', views.doctor_dashboard, name='doctor_dashboard'),
    path('dashboard/patient/', views.patient_dashboard, name='patient_dashboard'),

    # Admin CRUD for Doctors
    path('admin/doctor/add/', views.admin_add_doctor, name='admin_add_doctor'),
    path('admin/doctor/edit/<int:doctor_id>/', views.admin_edit_doctor, name='admin_edit_doctor'),
    path('admin/doctor/delete/<int:doctor_id>/', views.admin_delete_doctor, name='admin_delete_doctor'),

    # Admin CRUD for Appointments
    path('admin/appointment/delete/<int:appointment_id>/', views.admin_delete_appointment, name='admin_delete_appointment'),

    # Doctor Views
    path('doctor/status/<int:appointment_id>/', views.doctor_update_status, name='doctor_update_status'),
    path('doctor/patient/<int:patient_id>/', views.doctor_view_patient, name='doctor_view_patient'),
    path('doctor/availability/', views.doctor_manage_availability, name='doctor_manage_availability'),
    path('doctor/availability/<int:slot_id>/delete/', views.doctor_delete_availability, name='doctor_delete_availability'),

    # Admin appointment edit access
    path('admin/appointment/status/<int:appointment_id>/', views.admin_update_appointment_status, name='admin_update_appointment_status'),

    # Patient Views
    path('doctors/', views.patient_doctor_list, name='patient_doctor_list'),
    path('book-appointment/', views.book_appointment, name='book_appointment'),
    path('book-appointment/<int:doctor_id>/', views.book_appointment, name='book_appointment_with_doctor'),
    path('appointments/history/', views.appointment_history, name='appointment_history'),
    path('appointments/cancel/<int:appointment_id>/', views.cancel_appointment, name='cancel_appointment'),

    # New Features: Hospital & Department
    path('hospitals/', views.hospital_list, name='hospital_list'),
    path('hospital/<int:hospital_id>/', views.hospital_detail, name='hospital_detail'),
    path('doctor-discovery/', views.doctor_discovery, name='doctor_discovery'),

    # Nearest Doctor Finder (API & page)
    path('api/nearest-doctors/', views.nearest_doctors_api, name='nearest_doctors_api'),
    path('nearest-doctor-finder/', views.nearest_doctor_finder, name='nearest_doctor_finder'),

    # Emergency Fast Booking
    path('emergency/', views.emergency_fast_booking, name='emergency_fast_booking'),

    # Admin CRUD for Hospitals
    path('admin/hospitals/', views.admin_hospital_list, name='admin_hospital_list'),
    path('admin/hospital/add/', views.admin_add_hospital, name='admin_add_hospital'),
    path('admin/hospital/edit/<int:hospital_id>/', views.admin_edit_hospital, name='admin_edit_hospital'),
    path('admin/hospital/delete/<int:hospital_id>/', views.admin_delete_hospital, name='admin_delete_hospital'),

    # Profile Edit
    path('profile/edit/', views.edit_profile, name='edit_profile'),
]

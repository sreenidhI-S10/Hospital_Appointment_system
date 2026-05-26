from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db.models import Count
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from functools import wraps

from .models import User, DoctorProfile, PatientProfile, Appointment
from .forms import (
    LoginForm,
    PatientRegistrationForm,
    DoctorRegistrationForm,
    PatientProfileForm,
    DoctorProfileForm,
    AppointmentForm
)

# ==========================================
# ACCESS CONTROL DECORATORS
# ==========================================

def role_required(allowed_roles):
    """
    Decorator to restrict access based on user roles.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, "Please log in to access this page.")
                return redirect('login')
            
            # Admins/Superusers bypass doctor/patient checks or are categorized as admin role
            user_role = request.user.role
            if request.user.is_superuser:
                user_role = 'admin'
                
            if user_role in allowed_roles:
                return view_func(request, *args, **kwargs)
            
            messages.error(request, f"Access denied. You do not have permission to view this page.")
            return redirect('dashboard_redirect')
        return _wrapped_view
    return decorator

# Convenience decorators
admin_required = role_required(['admin'])
doctor_required = role_required(['doctor'])
patient_required = role_required(['patient'])


# ==========================================
# PUBLIC VIEWS & AUTHENTICATION
# ==========================================

def home(request):
    """
    Hospital landing page.
    """
    # Grab a few doctors to showcase on the home page
    doctors = DoctorProfile.objects.all().select_related('user')[:3]
    return render(request, 'appointments/home.html', {'doctors': doctors})


@never_cache
@ensure_csrf_cookie
def user_login(request):
    """
    Standard login page. Redirects authenticated users to their dashboards.
    """
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return redirect('dashboard_redirect')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = LoginForm()
    
    return render(request, 'appointments/login.html', {'form': form})


def user_logout(request):
    """
    Logs the user out.
    """
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('home')


@login_required
def dashboard_redirect(request):
    """
    Helper view to redirect logged-in users to their specific dashboard.
    """
    role = request.user.role
    if request.user.is_superuser:
        role = 'admin'

    if role == 'admin':
        return redirect('admin_dashboard')
    elif role == 'doctor':
        return redirect('doctor_dashboard')
    elif role == 'patient':
        return redirect('patient_dashboard')
    
    messages.error(request, "User role not recognized.")
    return redirect('home')


@never_cache
@ensure_csrf_cookie
def patient_register(request):
    """
    Handles patient registration.
    """
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Log the patient in immediately after signup
            login(request, user)
            messages.success(request, "Registration successful! Welcome to the Hospital Management System.")
            return redirect('patient_dashboard')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PatientRegistrationForm()
    
    return render(request, 'appointments/register.html', {'form': form, 'role_title': 'Patient'})


@never_cache
@ensure_csrf_cookie
def doctor_register(request):
    """
    Handles doctor registration.
    """
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = DoctorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            # Log the doctor in immediately after signup
            login(request, user)
            messages.success(request, "Registration successful! Welcome to the medical team.")
            return redirect('doctor_dashboard')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = DoctorRegistrationForm()
    
    return render(request, 'appointments/register.html', {'form': form, 'role_title': 'Doctor'})


# ==========================================
# ADMIN VIEWS
# ==========================================

@admin_required
def admin_dashboard(request):
    """
    Main dashboard for administrator.
    """
    # Count stats
    total_doctors = DoctorProfile.objects.count()
    total_patients = PatientProfile.objects.count()
    total_appointments = Appointment.objects.count()

    # Lists
    doctors = DoctorProfile.objects.all().select_related('user')
    patients = PatientProfile.objects.all().select_related('user')
    appointments = Appointment.objects.all().select_related('patient__user', 'doctor__user').order_by('-created_at')

    context = {
        'total_doctors': total_doctors,
        'total_patients': total_patients,
        'total_appointments': total_appointments,
        'doctors': doctors,
        'patients': patients,
        'appointments': appointments,
    }
    return render(request, 'appointments/admin_dashboard.html', context)


@admin_required
def admin_add_doctor(request):
    """
    Allows administrator to create a doctor user and profile.
    """
    if request.method == 'POST':
        form = DoctorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            doctor_user = form.save()
            messages.success(request, f"Doctor profile for Dr. {doctor_user.first_name} {doctor_user.last_name} created successfully!")
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = DoctorRegistrationForm()
    
    return render(request, 'appointments/admin_doctor_form.html', {'form': form, 'action': 'Add New'})


@admin_required
def admin_edit_doctor(request, doctor_id):
    """
    Allows administrator to edit an existing doctor's details.
    """
    doctor_profile = get_object_or_404(DoctorProfile, id=doctor_id)
    doctor_user = doctor_profile.user

    if request.method == 'POST':
        form = DoctorRegistrationForm(request.POST, request.FILES, instance=doctor_user, is_edit=True)
        if form.is_valid():
            form.save()
            messages.success(request, f"Dr. {doctor_user.first_name} {doctor_user.last_name}'s profile updated successfully.")
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        # Populate form with profile data
        initial_data = {
            'specialization': doctor_profile.specialization,
            'experience': doctor_profile.experience,
            'phone': doctor_profile.phone,
        }
        form = DoctorRegistrationForm(instance=doctor_user, initial=initial_data, is_edit=True)
    
    return render(request, 'appointments/admin_doctor_form.html', {'form': form, 'action': 'Edit', 'doctor_profile': doctor_profile})


@admin_required
def admin_delete_doctor(request, doctor_id):
    """
    Deletes a doctor. It cascade deletes the profile and user.
    """
    doctor_profile = get_object_or_404(DoctorProfile, id=doctor_id)
    doctor_name = f"Dr. {doctor_profile.user.first_name} {doctor_profile.user.last_name}"
    user = doctor_profile.user
    user.delete() # Cascade deletes DoctorProfile
    messages.success(request, f"Doctor profile for {doctor_name} deleted successfully.")
    return redirect('admin_dashboard')


@admin_required
def admin_delete_appointment(request, appointment_id):
    """
    Deletes an appointment.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointment.delete()
    messages.success(request, "Appointment successfully deleted.")
    return redirect('admin_dashboard')


# ==========================================
# DOCTOR VIEWS
# ==========================================

@doctor_required
def doctor_dashboard(request):
    """
    Dashboard for doctors showing their assigned appointments.
    """
    doctor_profile = request.user.doctor_profile
    
    # Calculate stats
    appointments_qs = Appointment.objects.filter(doctor=doctor_profile)
    total_assigned = appointments_qs.count()
    pending = appointments_qs.filter(status='Pending').count()
    approved = appointments_qs.filter(status='Approved').count()
    completed = appointments_qs.filter(status='Completed').count()

    # Appointment list
    appointments = appointments_qs.select_related('patient__user').order_by('-appointment_date', '-appointment_time')

    context = {
        'total_assigned': total_assigned,
        'pending': pending,
        'approved': approved,
        'completed': completed,
        'appointments': appointments,
    }
    return render(request, 'appointments/doctor_dashboard.html', context)


@doctor_required
def doctor_update_status(request, appointment_id):
    """
    Allows a doctor to update the status of their assigned appointments.
    """
    doctor_profile = request.user.doctor_profile
    appointment = get_object_or_404(Appointment, id=appointment_id, doctor=doctor_profile)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['Pending', 'Approved', 'Completed', 'Cancelled']:
            appointment.status = new_status
            appointment.save()
            messages.success(request, f"Appointment status updated to '{new_status}' successfully.")
        else:
            messages.error(request, "Invalid status choice.")
    
    return redirect('doctor_dashboard')


@doctor_required
def doctor_view_patient(request, patient_id):
    """
    Allows a doctor to view patient profile information.
    """
    patient_profile = get_object_or_404(PatientProfile, id=patient_id)
    return render(request, 'appointments/patient_details_modal.html', {'patient': patient_profile})


# ==========================================
# PATIENT VIEWS
# ==========================================

@patient_required
def patient_dashboard(request):
    """
    Dashboard for patients to view summary statistics and recent activity.
    """
    patient_profile = request.user.patient_profile
    appointments_qs = Appointment.objects.filter(patient=patient_profile)
    
    total_booked = appointments_qs.count()
    pending = appointments_qs.filter(status='Pending').count()
    completed = appointments_qs.filter(status='Completed').count()

    recent_appointments = appointments_qs.select_related('doctor__user').order_by('-created_at')[:5]

    context = {
        'total_booked': total_booked,
        'pending': pending,
        'completed': completed,
        'recent_appointments': recent_appointments,
    }
    return render(request, 'appointments/patient_dashboard.html', context)


@patient_required
def patient_doctor_list(request):
    """
    Displays list of all doctors for a patient to view and choose.
    """
    doctors = DoctorProfile.objects.all().select_related('user')
    return render(request, 'appointments/doctor_list.html', {'doctors': doctors})


@never_cache
@ensure_csrf_cookie
@patient_required
def book_appointment(request, doctor_id=None):
    """
    Enables patient to book an appointment with a doctor.
    """
    patient_profile = request.user.patient_profile

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.patient = patient_profile
            appointment.save()
            messages.success(request, "Your appointment has been booked and is currently pending approval!")
            return redirect('appointment_history')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        # Pre-select doctor if passed through the URL
        initial_data = {}
        if doctor_id:
            doctor = get_object_or_404(DoctorProfile, id=doctor_id)
            initial_data['doctor'] = doctor
        form = AppointmentForm(initial=initial_data)

    return render(request, 'appointments/book_appointment.html', {'form': form})


@patient_required
def appointment_history(request):
    """
    Lists history of all appointments booked by the patient.
    """
    patient_profile = request.user.patient_profile
    appointments = Appointment.objects.filter(patient=patient_profile).select_related('doctor__user').order_by('-appointment_date', '-appointment_time')
    return render(request, 'appointments/appointment_history.html', {'appointments': appointments})


@patient_required
def cancel_appointment(request, appointment_id):
    """
    Allows a patient to cancel an appointment if it is Pending or Approved.
    """
    patient_profile = request.user.patient_profile
    appointment = get_object_or_404(Appointment, id=appointment_id, patient=patient_profile)

    if appointment.status in ['Pending', 'Approved']:
        appointment.status = 'Cancelled'
        appointment.save()
        messages.success(request, "Your appointment has been successfully cancelled.")
    else:
        messages.error(request, "Completed or already Cancelled appointments cannot be cancelled.")
    
    return redirect('appointment_history')


# ==========================================
# PROFILE EDIT (UNIFIED)
# ==========================================

@never_cache
@ensure_csrf_cookie
@login_required
def edit_profile(request):
    """
    Allows logged-in patients and doctors to edit their profiles.
    """
    user = request.user
    
    if user.role == 'patient':
        form_class = PatientProfileForm
        template_name = 'appointments/profile_edit.html'
        success_dashboard = 'patient_dashboard'
    elif user.role == 'doctor':
        form_class = DoctorProfileForm
        template_name = 'appointments/profile_edit.html'
        success_dashboard = 'doctor_dashboard'
    else:
        messages.info(request, "Profile updates are only available for Patient and Doctor accounts.")
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect(success_dashboard)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = form_class(instance=user)

    return render(request, template_name, {'form': form, 'role': user.role})


def csrf_failure(request, reason=""):
    """
    Show a recoverable page when the browser submits an old CSRF token.
    """
    return render(
        request,
        'appointments/csrf_failure.html',
        {'reason': reason},
        status=403,
    )


@login_required
def change_password(request):
    """
    Allows logged-in users to change their password securely.
    Ensures they remain logged in after changing the password and
    redirects them to their specific dashboards based on roles.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Keep user session active by updating the cryptographic session auth hash
            update_session_auth_hash(request, user)
            messages.success(request, "Your password has been successfully updated!")
            return redirect('dashboard_redirect')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PasswordChangeForm(request.user)

    # Dynamically inject Bootstrap classes to password fields for clean presentation
    for field in form.fields.values():
        field.widget.attrs.update({'class': 'form-control'})

    return render(request, 'appointments/password_change.html', {'form': form})


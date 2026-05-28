import json
import math
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db.models import Count, Q
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.conf import settings
from functools import wraps

from .models import User, DoctorProfile, PatientProfile, Appointment, Hospital, Department, DoctorAvailability
from .forms import (
    LoginForm,
    PatientRegistrationForm,
    DoctorRegistrationForm,
    PatientProfileForm,
    DoctorProfileForm,
    AppointmentForm,
    DoctorAvailabilityForm,
    HospitalForm,
)

logger = logging.getLogger(__name__)

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


def is_admin_user(user):
    return user.is_authenticated and (user.is_superuser or user.role == 'admin')


def get_doctor_profile_for_user(user):
    return getattr(user, 'doctor_profile', None)


def get_patient_profile_for_user(user):
    return getattr(user, 'patient_profile', None)


def require_doctor_ownership(request, appointment):
    doctor_profile = get_doctor_profile_for_user(request.user)
    logger.debug(
        "Appointment access check user=%s doctor_profile=%s appointment_id=%s appointment_doctor_user=%s",
        request.user.pk,
        getattr(doctor_profile, 'pk', None),
        appointment.pk,
        getattr(getattr(appointment.doctor, 'user', None), 'pk', None),
    )
    if not doctor_profile or appointment.doctor_id != doctor_profile.id:
        raise PermissionDenied("You do not have permission to access this appointment.")
    return doctor_profile


def require_patient_assigned_to_doctor(request, patient_profile):
    doctor_profile = get_doctor_profile_for_user(request.user)
    logger.debug(
        "Patient access check user=%s doctor_profile=%s patient_id=%s",
        request.user.pk,
        getattr(doctor_profile, 'pk', None),
        patient_profile.pk,
    )
    if not doctor_profile or not Appointment.objects.filter(patient=patient_profile, doctor=doctor_profile).exists():
        raise PermissionDenied("You do not have permission to access this patient record.")
    return doctor_profile

# ==========================================
# PUBLIC VIEWS & AUTHENTICATION
# ==========================================

def home(request):
    """
    Hospital landing page.
    """
    doctors = DoctorProfile.objects.all().select_related('user')[:3]
    hospitals = Hospital.objects.all()[:3]
    return render(request, 'appointments/home.html', {'doctors': doctors, 'hospitals': hospitals})

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
    total_doctors = DoctorProfile.objects.count()
    total_patients = PatientProfile.objects.count()
    total_appointments = Appointment.objects.count()
    total_hospitals = Hospital.objects.count()
    doctors = DoctorProfile.objects.all().select_related('user')
    patients = PatientProfile.objects.all().select_related('user')
    appointments = Appointment.objects.all().select_related('patient__user', 'doctor__user').order_by('-created_at')
    hospitals = Hospital.objects.all()
    context = {
        'total_doctors': total_doctors,
        'total_patients': total_patients,
        'total_appointments': total_appointments,
        'total_hospitals': total_hospitals,
        'doctors': doctors,
        'patients': patients,
        'appointments': appointments,
        'hospitals': hospitals,
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
        initial_data = {
            'hospital': doctor_profile.hospital,
            'department': doctor_profile.department,
            'specialization': doctor_profile.specialization,
            'experience': doctor_profile.experience,
            'phone': doctor_profile.phone,
            'consultation_fees': doctor_profile.consultation_fees,
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
    user.delete()
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
    doctor_profile = get_doctor_profile_for_user(request.user)
    if doctor_profile is None:
        messages.error(request, "Doctor profile not found.")
        return redirect('dashboard_redirect')
    logger.debug(
        "Doctor dashboard user=%s doctor_profile=%s",
        request.user.pk,
        doctor_profile.pk,
    )
    appointments_qs = Appointment.objects.filter(doctor=doctor_profile)
    total_assigned = appointments_qs.count()
    pending = appointments_qs.filter(status='Pending').count()
    approved = appointments_qs.filter(status='Approved').count()
    completed = appointments_qs.filter(status='Completed').count()
    appointments = appointments_qs.select_related('patient__user').order_by('-scheduled_datetime')
    context = {
        'total_assigned': total_assigned,
        'pending': pending,
        'approved': approved,
        'completed': completed,
        'appointments': appointments,
    }
    return render(request, 'appointments/doctor_dashboard.html', context)

def _update_appointment_status(request, appointment_id, redirect_target, require_admin=False):
    if require_admin:
        appointment = get_object_or_404(Appointment, id=appointment_id)
    else:
        appointment = get_object_or_404(Appointment, id=appointment_id)

    logger.debug(
        "Appointment status flow user=%s appointment_id=%s appointment_doctor=%s redirect_target=%s require_admin=%s",
        request.user.pk,
        appointment.pk,
        appointment.doctor_id,
        redirect_target,
        require_admin,
    )

    if require_admin:
        if not is_admin_user(request.user):
            raise PermissionDenied("Admin access required.")
    else:
        require_doctor_ownership(request, appointment)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['Pending', 'Approved', 'Completed', 'Cancelled']:
            appointment.status = new_status
            appointment.save()
            messages.success(request, f"Appointment status updated to '{new_status}' successfully.")
        else:
            messages.error(request, "Invalid status choice.")
    return redirect(redirect_target)


@doctor_required
def doctor_update_status(request, appointment_id):
    """
    Allows a doctor to update only their own appointments.
    """
    return _update_appointment_status(request, appointment_id, 'doctor_dashboard', require_admin=False)


@admin_required
def admin_update_appointment_status(request, appointment_id):
    """Allows an admin to update any appointment status."""
    return _update_appointment_status(request, appointment_id, 'admin_dashboard', require_admin=True)

@doctor_required
def doctor_view_patient(request, patient_id):
    """
    Allows a doctor to view patient profile information only for their own appointments.
    Admins can view any patient record.
    """
    doctor_profile = get_doctor_profile_for_user(request.user)
    if doctor_profile is None:
        messages.error(request, "Doctor profile not found.")
        return redirect('dashboard_redirect')
    patient_profile = get_object_or_404(PatientProfile.objects.select_related('user'), id=patient_id)
    require_patient_assigned_to_doctor(request, patient_profile)
    logger.debug(
        "Doctor patient view user=%s doctor_profile=%s patient_id=%s",
        request.user.pk,
        doctor_profile.pk,
        patient_profile.pk,
    )
    return render(request, 'appointments/patient_details_modal.html', {'patient': patient_profile})

@doctor_required
def doctor_manage_availability(request):
    """Create, edit, and list availability slots for the logged-in doctor."""
    doctor_profile = get_doctor_profile_for_user(request.user)
    if doctor_profile is None:
        messages.error(request, "Doctor profile not found.")
        return redirect('dashboard_redirect')
    editing_slot = None
    edit_id = request.POST.get('slot_id') if request.method == 'POST' else request.GET.get('edit')

    if edit_id:
        editing_slot = get_object_or_404(DoctorAvailability, id=edit_id, doctor=doctor_profile)

    if request.method == 'POST':
        form = DoctorAvailabilityForm(request.POST, instance=editing_slot)
        if form.is_valid():
            availability = form.save(commit=False)
            availability.doctor = doctor_profile
            availability.save()
            if editing_slot:
                messages.success(request, "Availability slot updated.")
            else:
                messages.success(request, "Availability slot added.")
            return redirect('doctor_manage_availability')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = DoctorAvailabilityForm(instance=editing_slot)
    availabilities = DoctorAvailability.objects.filter(doctor=doctor_profile)
    return render(request, 'appointments/doctor_availability.html', {
        'form': form,
        'availabilities': availabilities,
        'editing_slot': editing_slot,
    })

@doctor_required
def doctor_delete_availability(request, slot_id):
    """Delete one availability slot owned by the logged-in doctor."""
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('doctor_manage_availability')

    doctor_profile = get_doctor_profile_for_user(request.user)
    if doctor_profile is None:
        messages.error(request, "Doctor profile not found.")
        return redirect('dashboard_redirect')
    slot = get_object_or_404(DoctorAvailability, id=slot_id, doctor=doctor_profile)
    slot.delete()
    messages.success(request, "Availability slot deleted.")
    return redirect('doctor_manage_availability')

# ==========================================
# PATIENT VIEWS
# ==========================================

@patient_required
def patient_dashboard(request):
    """
    Dashboard for patients to view summary statistics and recent activity.
    """
    patient_profile = get_patient_profile_for_user(request.user)
    if patient_profile is None:
        messages.error(request, "Patient profile not found.")
        return redirect('dashboard_redirect')
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
    patient_profile = get_patient_profile_for_user(request.user)
    if patient_profile is None:
        messages.error(request, "Patient profile not found.")
        return redirect('dashboard_redirect')
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
    patient_profile = get_patient_profile_for_user(request.user)
    if patient_profile is None:
        messages.error(request, "Patient profile not found.")
        return redirect('dashboard_redirect')
    appointments = Appointment.objects.filter(patient=patient_profile).select_related('doctor__user').order_by('-scheduled_datetime')
    return render(request, 'appointments/appointment_history.html', {'appointments': appointments})

@patient_required
def cancel_appointment(request, appointment_id):
    """
    Allows a patient to cancel an appointment if it is Pending or Approved.
    """
    patient_profile = get_patient_profile_for_user(request.user)
    if patient_profile is None:
        messages.error(request, "Patient profile not found.")
        return redirect('dashboard_redirect')
    appointment = get_object_or_404(Appointment, id=appointment_id, patient=patient_profile)
    if appointment.status in ['Pending', 'Approved']:
        appointment.status = 'Cancelled'
        appointment.save()
        messages.success(request, "Your appointment has been successfully cancelled.")
    else:
        messages.error(request, "Completed or already Cancelled appointments cannot be cancelled.")
    return redirect('appointment_history')

# ==========================================
# NEW FEATURES: Hospital & Department Views
# ==========================================

def hospital_list(request):
    hospitals = Hospital.objects.all()
    return render(request, 'appointments/hospital_list.html', {'hospitals': hospitals})

def hospital_detail(request, hospital_id):
    hospital = get_object_or_404(Hospital, id=hospital_id)
    doctors = hospital.doctors.select_related('user', 'department')
    return render(request, 'appointments/hospital_detail.html', {'hospital': hospital, 'doctors': doctors})

def doctor_discovery(request):
    # Prevent doctors from accessing the public discovery page; redirect them to their dashboard
    if request.user.is_authenticated and getattr(request.user, 'role', None) == 'doctor':
        return redirect('doctor_dashboard')
    department_id = request.GET.get('department')
    hospitals = Hospital.objects.filter(doctors__isnull=False).distinct()
    departments = Department.objects.all()
    doctors = DoctorProfile.objects.select_related('user', 'hospital', 'department')
    if department_id:
        doctors = doctors.filter(department_id=department_id)
    return render(request, 'appointments/doctor_discovery.html', {
        'doctors': doctors,
        'departments': departments,
        'selected_department': int(department_id) if department_id else None,
        'hospitals': hospitals,
    })

# Nearest Doctor Finder – API endpoint returning JSON
@patient_required
def nearest_doctors_api(request):
    try:
        lat = float(request.GET.get('lat'))
        lon = float(request.GET.get('lon'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid coordinates'}, status=400)
    # Simple Haversine formula for distance calculation
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371  # km
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.asin(math.sqrt(a))
    doctors = DoctorProfile.objects.select_related('hospital', 'user')
    results = []
    for doc in doctors:
        if doc.hospital and doc.hospital.latitude and doc.hospital.longitude:
            dist = haversine(lat, lon, float(doc.hospital.latitude), float(doc.hospital.longitude))
            results.append({
                'id': doc.id,
                'name': f"Dr. {doc.user.first_name} {doc.user.last_name}",
                'specialization': doc.specialization,
                'hospital': doc.hospital.hospital_name,
                'distance_km': round(dist, 2),
                'lat': float(doc.hospital.latitude),
                'lon': float(doc.hospital.longitude),
            })
    results.sort(key=lambda x: x['distance_km'])
    return JsonResponse({'doctors': results[:10]})

def nearest_doctor_finder(request):
    """Page that loads Google Maps and calls nearest_doctors_api via JS."""
    context = {
        'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
    }
    return render(request, 'appointments/nearest_doctor_finder.html', context)

# Emergency Fast Booking – list emergency doctors and immediate booking
@patient_required
def emergency_fast_booking(request):
    emergency_doctors = DoctorProfile.objects.filter(hospital__emergency_available=True).select_related('user', 'hospital')
    if request.method == 'POST':
        doctor_id = request.POST.get('doctor_id')
        doctor = get_object_or_404(DoctorProfile, id=doctor_id)
        patient_profile = request.user.patient_profile
        # Immediate appointment creation with status Approved
        Appointment.objects.create(
            patient=patient_profile,
            doctor=doctor,
            hospital=doctor.hospital,
            appointment_type='Emergency',
            consultation_mode='in_person',
            scheduled_datetime=timezone.now(),
            reason='Emergency fast booking',
            status='Approved'
        )
        messages.success(request, "Emergency appointment booked successfully.")
        return redirect('appointment_history')
    return render(request, 'appointments/emergency_fast_booking.html', {'doctors': emergency_doctors})

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
            update_session_auth_hash(request, user)
            messages.success(request, "Your password has been successfully updated!")
            return redirect('dashboard_redirect')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PasswordChangeForm(request.user)
    for field in form.fields.values():
        field.widget.attrs.update({'class': 'form-control'})
    return render(request, 'appointments/password_change.html', {'form': form})


@admin_required
def admin_hospital_list(request):
    """
    List all hospitals for administrative management.
    """
    from django.core.paginator import Paginator
    query = request.GET.get('q', '').strip()
    hospitals = Hospital.objects.all().order_by('hospital_name')
    if query:
        hospitals = hospitals.filter(
            Q(hospital_name__icontains=query) |
            Q(city__icontains=query) |
            Q(state__icontains=query)
        )
    paginator = Paginator(hospitals, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'appointments/admin_hospital_list.html', {
        'page_obj': page_obj,
        'query': query
    })


@admin_required
def admin_add_hospital(request):
    """
    Add a new hospital.
    """
    if request.method == 'POST':
        form = HospitalForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Hospital added successfully.")
            return redirect('admin_hospital_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = HospitalForm()
    return render(request, 'appointments/admin_hospital_form.html', {
        'form': form,
        'action': 'Add New'
    })


@admin_required
def admin_edit_hospital(request, hospital_id):
    """
    Edit an existing hospital.
    """
    hospital = get_object_or_404(Hospital, id=hospital_id)
    if request.method == 'POST':
        form = HospitalForm(request.POST, request.FILES, instance=hospital)
        if form.is_valid():
            form.save()
            messages.success(request, f"Hospital '{hospital.hospital_name}' updated successfully.")
            return redirect('admin_hospital_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = HospitalForm(instance=hospital)
    return render(request, 'appointments/admin_hospital_form.html', {
        'form': form,
        'action': 'Edit',
        'hospital': hospital
    })


@admin_required
def admin_delete_hospital(request, hospital_id):
    """
    Delete a hospital.
    """
    hospital = get_object_or_404(Hospital, id=hospital_id)
    hospital_name = hospital.hospital_name
    hospital.delete()
    messages.success(request, f"Hospital '{hospital_name}' has been successfully deleted.")
    return redirect('admin_hospital_list')

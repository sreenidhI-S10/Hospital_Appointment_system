from django.contrib import admin
from .models import Hospital, Department, DoctorProfile, DoctorAvailability, Appointment, PatientProfile

@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ('hospital_name', 'city', 'state', 'contact_number', 'emergency_available')
    search_fields = ('hospital_name', 'city', 'state')
    list_filter = ('emergency_available',)

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'hospital', 'department', 'specialization', 'experience', 'consultation_fees')
    search_fields = ('user__username', 'specialization')
    list_filter = ('hospital', 'department')

@admin.register(DoctorAvailability)
class DoctorAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'day_of_week', 'start_time', 'end_time', 'consultation_mode')
    list_filter = ('day_of_week', 'consultation_mode')
    search_fields = ('doctor__user__username',)

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('token_number', 'patient', 'doctor', 'hospital', 'scheduled_datetime', 'appointment_type', 'status')
    list_filter = ('status', 'appointment_type', 'hospital')
    search_fields = ('patient__user__username', 'doctor__user__username', 'token_number')

@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'age', 'gender')
    search_fields = ('user__username',)

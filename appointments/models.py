from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

class User(AbstractUser):
    """Custom User model supporting Admin, Doctor, and Patient roles."""
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('doctor', 'Doctor'),
        ('patient', 'Patient'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='patient')

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Hospital(models.Model):
    """Model representing a hospital."""
    hospital_name = models.CharField(max_length=255, unique=True)
    hospital_image = models.ImageField(upload_to='hospital_images/', blank=True, null=True)
    location = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20)
    contact_number = models.CharField(max_length=20)
    emergency_available = models.BooleanField(default=False)
    hospital_description = models.TextField(blank=True)
    # Geographic coordinates for nearest‑doctor calculations
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return self.hospital_name

class Department(models.Model):
    """Medical department such as Cardiology, Neurology, etc."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class DoctorProfile(models.Model):
    """Profile for Doctors with specialized medical information, linked to Hospital and Department."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, limit_choices_to={'role': 'doctor'}, related_name='doctor_profile')
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='doctors', null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='doctors')
    specialization = models.CharField(max_length=100)
    experience = models.PositiveIntegerField(help_text="Years of experience")
    phone = models.CharField(max_length=15)
    consultation_fees = models.DecimalField(max_digits=8, decimal_places=2, default=50.00)
    profile_image = models.ImageField(upload_to='doctor_profiles/', blank=True, null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)

    def __str__(self):
        return f"Dr. {self.user.first_name} {self.user.last_name} ({self.specialization})"

class DoctorAvailability(models.Model):
    """Availability slots for doctors."""
    CONSULTATION_MODE_CHOICES = (
        ('in_person', 'In-person'),
        ('video', 'Video consultation'),
    )
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='availabilities')
    day_of_week = models.IntegerField(choices=[(i, f"Day {i}") for i in range(0, 7)], help_text="0=Monday, 6=Sunday")
    start_time = models.TimeField()
    end_time = models.TimeField()
    consultation_mode = models.CharField(max_length=20, choices=CONSULTATION_MODE_CHOICES, default='in_person')

    class Meta:
        unique_together = ('doctor', 'day_of_week', 'start_time', 'end_time')
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.doctor} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time} ({self.get_consultation_mode_display()})"

class PatientProfile(models.Model):
    """Profile for Patients containing basic demographic and contact information."""
    GENDER_CHOICES = (
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, limit_choices_to={'role': 'patient'}, related_name='patient_profile')
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    # fields for nearest doctor feature
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

class Appointment(models.Model):
    """Appointment details linking patients to doctors with token and extended fields."""
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    )
    APPOINTMENT_TYPE_CHOICES = (
        ('General', 'General'),
        ('Emergency', 'Emergency'),
    )
    CONSULTATION_MODE_CHOICES = (
        ('in_person', 'In-person'),
        ('video', 'Video consultation'),
    )
    token_number = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='appointments')
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='appointments', null=True, blank=True)
    appointment_type = models.CharField(max_length=20, choices=APPOINTMENT_TYPE_CHOICES, default='General')
    consultation_mode = models.CharField(max_length=20, choices=CONSULTATION_MODE_CHOICES, default='in_person')
    scheduled_datetime = models.DateTimeField(null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_datetime']

    def __str__(self):
        return f"Appt {self.token_number} on {self.scheduled_datetime} - Patient: {self.patient} | Doctor: {self.doctor}"

import re

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.utils import timezone
from .models import User, DoctorProfile, PatientProfile, Appointment, Hospital, Department, DoctorAvailability

class BootstrapFormMixin:
    """
    Mixin to automatically add Bootstrap classes to form fields.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            css_classes = field.widget.attrs.get('class', '')
            if isinstance(field.widget, forms.CheckboxInput):
                css_classes = f"{css_classes} form-check-input".strip()
            elif isinstance(field.widget, forms.FileInput):
                css_classes = f"{css_classes} form-control".strip()
            else:
                css_classes = f"{css_classes} form-control".strip()

            if self.is_bound:
                if field_name in self.errors:
                    css_classes = f"{css_classes} is-invalid".strip()
                elif self.data.get(field_name) or self.files.get(field_name):
                    css_classes = f"{css_classes} is-valid".strip()

            field.widget.attrs.update({'class': css_classes})


class LoginForm(forms.Form):
    """
    Custom login form for role-based authentication.
    """
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise forms.ValidationError("Invalid username or password.")
            if not user.is_active:
                raise forms.ValidationError("This account is inactive.")
            cleaned_data['user'] = user
        return cleaned_data


class PatientRegistrationForm(BootstrapFormMixin, forms.ModelForm):
    """
    Form to register a new Patient user and their demographic profile.
    """
    password = forms.CharField(widget=forms.PasswordInput(), min_length=6)
    confirm_password = forms.CharField(widget=forms.PasswordInput(), label="Confirm Password")
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)

    # PatientProfile fields
    age = forms.IntegerField(min_value=1)
    gender = forms.ChoiceField(choices=PatientProfile.GENDER_CHOICES)
    phone = forms.CharField(max_length=15)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username is already taken.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.role = 'patient'
        if commit:
            with transaction.atomic():
                user.save()
                PatientProfile.objects.create(
                    user=user,
                    age=self.cleaned_data['age'],
                    gender=self.cleaned_data['gender'],
                    phone=self.cleaned_data['phone'],
                    address=self.cleaned_data['address']
                )
        return user


class DoctorRegistrationForm(BootstrapFormMixin, forms.ModelForm):
    """
    Form to register a Doctor (used by Doctors registering or by Admin adding a Doctor).
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=False,
        help_text="Minimum 8 characters with uppercase, lowercase, number, and special character."
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        label="Confirm Password",
        required=False
    )
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)

    # DoctorProfile fields
    hospital = forms.ModelChoiceField(queryset=Hospital.objects.all(), required=True)
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=False)
    specialization = forms.CharField(max_length=100, required=True)
    experience = forms.IntegerField(label="Experience (Years)")
    phone = forms.CharField()
    consultation_fees = forms.DecimalField(max_digits=8, decimal_places=2, initial=50.00, label="Consultation Fees ($)")
    profile_image = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']

    def __init__(self, *args, **kwargs):
        self.is_edit = kwargs.pop('is_edit', False)
        super().__init__(*args, **kwargs)
        if self.is_edit and self.instance and hasattr(self.instance, 'doctor_profile'):
            profile = self.instance.doctor_profile
            self.fields['hospital'].initial = profile.hospital
            self.fields['department'].initial = profile.department
            self.fields['consultation_fees'].initial = profile.consultation_fees
        if self.is_edit:
            self.fields['password'].required = False
            self.fields['confirm_password'].required = False
        else:
            self.fields['password'].required = True
            self.fields['confirm_password'].required = True
        self.fields['username'].required = True
        self.fields['username'].min_length = 4
        self.fields['username'].widget.attrs.update({
            'pattern': r'[A-Za-z0-9_]{4,}',
            'autocomplete': 'username',
        })
        self.fields['email'].widget.attrs.update({'autocomplete': 'email'})
        self.fields['experience'].widget.attrs.update({'min': 0, 'max': 50, 'inputmode': 'numeric'})
        self.fields['phone'].widget.attrs.update({'maxlength': 10, 'inputmode': 'numeric'})
        self.fields['profile_image'].widget.attrs.update({'accept': '.jpg,.jpeg,.png,image/jpeg,image/png'})

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            raise forms.ValidationError("Staff username is required.")
        if len(username) < 4:
            raise forms.ValidationError("Staff username must be at least 4 characters.")
        if not re.fullmatch(r'[A-Za-z0-9_]+', username):
            raise forms.ValidationError("Staff username can contain only letters, numbers, and underscores.")

        existing_users = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            existing_users = existing_users.exclude(pk=self.instance.pk)
        if existing_users.exists():
            raise forms.ValidationError("Username already exists. Please choose another username.")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            raise forms.ValidationError("Email address is required.")

        existing_users = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            existing_users = existing_users.exclude(pk=self.instance.pk)
        if existing_users.exists():
            raise forms.ValidationError("Email address already exists. Please use another email.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password') or ''
        if self.is_edit and not password:
            return password
        if not password:
            raise forms.ValidationError("Password is required.")
        if len(password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters.")
        if not re.search(r'[A-Z]', password):
            raise forms.ValidationError("Password must contain at least 1 uppercase letter.")
        if not re.search(r'[a-z]', password):
            raise forms.ValidationError("Password must contain at least 1 lowercase letter.")
        if not re.search(r'\d', password):
            raise forms.ValidationError("Password must contain at least 1 number.")
        if not re.search(r'[^A-Za-z0-9]', password):
            raise forms.ValidationError("Password must contain at least 1 special character.")
        return password

    def clean_first_name(self):
        first_name = (self.cleaned_data.get('first_name') or '').strip()
        if len(first_name) < 2:
            raise forms.ValidationError("First name must be at least 2 characters.")
        if not first_name.isalpha():
            raise forms.ValidationError("First name must contain alphabets only.")
        return first_name

    def clean_last_name(self):
        last_name = (self.cleaned_data.get('last_name') or '').strip()
        if len(last_name) < 2:
            raise forms.ValidationError("Last name must be at least 2 characters.")
        if not last_name.isalpha():
            raise forms.ValidationError("Last name must contain alphabets only.")
        return last_name

    def clean_specialization(self):
        specialization = (self.cleaned_data.get('specialization') or '').strip()
        if not specialization:
            raise forms.ValidationError("Specialization area is required.")
        if specialization.isdigit():
            raise forms.ValidationError("Specialization cannot contain numbers only.")
        return specialization

    def clean_experience(self):
        experience = self.cleaned_data.get('experience')
        if experience is None:
            raise forms.ValidationError("Years of experience is required.")
        if experience < 0 or experience > 50:
            raise forms.ValidationError("Years of experience must be between 0 and 50.")
        return experience

    def clean_phone(self):
        phone = (self.cleaned_data.get('phone') or '').strip()
        if not phone:
            raise forms.ValidationError("Direct phone number is required.")
        if not phone.isdigit():
            raise forms.ValidationError("Direct phone number must contain digits only.")
        if len(phone) != 10:
            raise forms.ValidationError("Direct phone number must be exactly 10 digits.")
        return phone

    def clean_profile_image(self):
        profile_image = self.cleaned_data.get('profile_image')
        if not profile_image:
            return profile_image

        allowed_extensions = {'jpg', 'jpeg', 'png'}
        extension = profile_image.name.rsplit('.', 1)[-1].lower() if '.' in profile_image.name else ''
        if extension not in allowed_extensions:
            raise forms.ValidationError("Profile image must be a JPG, JPEG, or PNG file.")
        if profile_image.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Profile image size must not exceed 2MB.")
        return profile_image

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if not self.is_edit or password:
            if not confirm_password:
                self.add_error('confirm_password', "Please confirm your password.")
            elif password and password != confirm_password:
                self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'doctor'
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            with transaction.atomic():
                user.save()
                profile_defaults = {
                    'hospital': self.cleaned_data['hospital'],
                    'department': self.cleaned_data.get('department'),
                    'specialization': self.cleaned_data['specialization'],
                    'experience': self.cleaned_data['experience'],
                    'phone': self.cleaned_data['phone'],
                    'consultation_fees': self.cleaned_data['consultation_fees'],
                }
                if self.cleaned_data.get('profile_image'):
                    profile_defaults['profile_image'] = self.cleaned_data['profile_image']

                profile, created = DoctorProfile.objects.get_or_create(
                    user=user,
                    defaults=profile_defaults,
                )
                if not created:
                    profile.hospital = self.cleaned_data['hospital']
                    profile.department = self.cleaned_data.get('department')
                    profile.specialization = self.cleaned_data['specialization']
                    profile.experience = self.cleaned_data['experience']
                    profile.phone = self.cleaned_data['phone']
                    profile.consultation_fees = self.cleaned_data['consultation_fees']
                    if self.cleaned_data.get('profile_image'):
                        profile.profile_image = self.cleaned_data['profile_image']
                    profile.save()
        return user


class PatientProfileForm(BootstrapFormMixin, forms.ModelForm):
    """
    Form to update patient profile data.
    """
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)

    age = forms.IntegerField(min_value=1)
    gender = forms.ChoiceField(choices=PatientProfile.GENDER_CHOICES)
    phone = forms.CharField(max_length=15)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))
    latitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False)
    longitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        # We pass user instance, then pull initial profile data
        user = kwargs.get('instance')
        if user and hasattr(user, 'patient_profile'):
            profile = user.patient_profile
            initial = kwargs.get('initial', {})
            initial.update({
                'age': profile.age,
                'gender': profile.gender,
                'phone': profile.phone,
                'address': profile.address,
                'latitude': profile.latitude,
                'longitude': profile.longitude,
            })
            kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            profile = user.patient_profile
            profile.age = self.cleaned_data['age']
            profile.gender = self.cleaned_data['gender']
            profile.phone = self.cleaned_data['phone']
            profile.address = self.cleaned_data['address']
            profile.latitude = self.cleaned_data.get('latitude')
            profile.longitude = self.cleaned_data.get('longitude')
            profile.save()
        return user


class DoctorProfileForm(BootstrapFormMixin, forms.ModelForm):
    """
    Form to update doctor profile data.
    """
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)

    specialization = forms.CharField(max_length=100)
    experience = forms.IntegerField(min_value=0)
    phone = forms.CharField(max_length=15)
    profile_image = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        user = kwargs.get('instance')
        if user and hasattr(user, 'doctor_profile'):
            profile = user.doctor_profile
            initial = kwargs.get('initial', {})
            initial.update({
                'specialization': profile.specialization,
                'experience': profile.experience,
                'phone': profile.phone,
            })
            kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            profile = user.doctor_profile
            profile.specialization = self.cleaned_data['specialization']
            profile.experience = self.cleaned_data['experience']
            profile.phone = self.cleaned_data['phone']
            if self.cleaned_data.get('profile_image'):
                profile.profile_image = self.cleaned_data['profile_image']
            profile.save()
        return user


class AppointmentForm(BootstrapFormMixin, forms.ModelForm):
    """Form for Patients to book an appointment with extended fields."""
    appointment_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    appointment_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    appointment_type = forms.ChoiceField(choices=Appointment.APPOINTMENT_TYPE_CHOICES, initial='General')
    consultation_mode = forms.ChoiceField(choices=Appointment.CONSULTATION_MODE_CHOICES, initial='in_person')
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Please state the reason for this visit...'}))

    class Meta:
        model = Appointment
        fields = ['doctor', 'appointment_date', 'appointment_time', 'appointment_type', 'consultation_mode', 'reason']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['doctor'].queryset = DoctorProfile.objects.all().select_related('user')
        self.fields['doctor'].label_from_instance = lambda obj: f"Dr. {obj.user.first_name} {obj.user.last_name} ({obj.specialization})"
        self.fields['appointment_date'].widget.attrs['min'] = timezone.localdate().isoformat()

    def clean_appointment_date(self):
        appointment_date = self.cleaned_data.get('appointment_date')
        if appointment_date and appointment_date < timezone.localdate():
            raise forms.ValidationError('Appointments can only be booked for today or a future date.')
        return appointment_date

    def clean(self):
        cleaned_data = super().clean()
        doctor = cleaned_data.get('doctor')
        date = cleaned_data.get('appointment_date')
        time = cleaned_data.get('appointment_time')
        if doctor and date and time:
            from datetime import datetime, timedelta
            scheduled_dt = datetime.combine(date, time)
            overlap = Appointment.objects.filter(
                doctor=doctor,
                scheduled_datetime__range=(scheduled_dt - timedelta(minutes=30), scheduled_dt + timedelta(minutes=30))
            ).exclude(status='Cancelled')
            if overlap.exists():
                raise forms.ValidationError('The selected doctor already has an appointment around this time. Please choose a different slot.')
        return cleaned_data

    def save(self, commit=True):
        appointment = super().save(commit=False)
        date = self.cleaned_data.get('appointment_date')
        time = self.cleaned_data.get('appointment_time')
        if date and time:
            from datetime import datetime
            appointment.scheduled_datetime = datetime.combine(date, time)
        if appointment.doctor:
            appointment.hospital = appointment.doctor.hospital
        if commit:
            appointment.save()
        return appointment


class DoctorAvailabilityForm(BootstrapFormMixin, forms.ModelForm):
    """Form for doctors to set their weekly availability slots."""
    class Meta:
        model = DoctorAvailability
        fields = ['day_of_week', 'start_time', 'end_time', 'consultation_mode']
        widgets = {
            'day_of_week': forms.Select(choices=[(i, f'Day {i}') for i in range(0,7)]),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        if start and end and start >= end:
            raise forms.ValidationError('Start time must be before end time.')
        return cleaned_data


class HospitalForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Hospital
        fields = [
            'hospital_name', 'hospital_image', 'hospital_description', 
            'location', 'city', 'state', 'pincode', 'contact_number', 
            'emergency_available', 'latitude', 'longitude'
        ]
        widgets = {
            'hospital_description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Provide a brief summary of the clinic facilities, specialties, and support hours...'}),
            'location': forms.TextInput(attrs={'placeholder': 'Street address, e.g. 123 Main St'}),
            'city': forms.TextInput(attrs={'placeholder': 'e.g. Chennai'}),
            'state': forms.TextInput(attrs={'placeholder': 'e.g. Tamil Nadu'}),
            'pincode': forms.TextInput(attrs={'placeholder': 'e.g. 600001'}),
            'contact_number': forms.TextInput(attrs={'placeholder': 'e.g. 1234567890'}),
            'latitude': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 13.0827'}),
            'longitude': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 80.2707'}),
        }

    def clean_hospital_name(self):
        name = (self.cleaned_data.get('hospital_name') or '').strip()
        if not name:
            raise forms.ValidationError("Hospital name is required.")
        qs = Hospital.objects.filter(hospital_name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A hospital with this name already exists.")
        return name

    def clean_contact_number(self):
        contact = (self.cleaned_data.get('contact_number') or '').strip()
        if not contact:
            raise forms.ValidationError("Contact number is required.")
        # Strip common formatting characters
        clean_contact = re.sub(r'\s+|-|\(|\)', '', contact)
        if not clean_contact.isdigit():
            raise forms.ValidationError("Contact number must contain only digits.")
        if len(clean_contact) < 7 or len(clean_contact) > 15:
            raise forms.ValidationError("Contact number must be between 7 and 15 digits.")
        return contact

    def clean_latitude(self):
        lat = self.cleaned_data.get('latitude')
        if lat is not None:
            if lat < -90 or lat > 90:
                raise forms.ValidationError("Latitude must be between -90 and 90.")
        return lat

    def clean_longitude(self):
        lon = self.cleaned_data.get('longitude')
        if lon is not None:
            if lon < -180 or lon > 180:
                raise forms.ValidationError("Longitude must be between -180 and 180.")
        return lon

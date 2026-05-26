from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from .models import User, DoctorProfile, PatientProfile, Appointment

class BootstrapFormMixin:
    """
    Mixin to automatically add Bootstrap classes to form fields.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs.update({'class': 'form-control'})
            else:
                field.widget.attrs.update({'class': 'form-control'})


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
    password = forms.CharField(widget=forms.PasswordInput(), min_length=6, required=False, help_text="Leave blank if not modifying password (for edits)")
    confirm_password = forms.CharField(widget=forms.PasswordInput(), label="Confirm Password", required=False)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)

    # DoctorProfile fields
    specialization = forms.CharField(max_length=100)
    experience = forms.IntegerField(min_value=0, label="Experience (Years)")
    phone = forms.CharField(max_length=15)
    profile_image = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']

    def __init__(self, *args, **kwargs):
        self.is_edit = kwargs.pop('is_edit', False)
        super().__init__(*args, **kwargs)
        if self.is_edit:
            self.fields['password'].required = False
            self.fields['confirm_password'].required = False
        else:
            self.fields['password'].required = True
            self.fields['confirm_password'].required = True

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not self.is_edit and User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username is already taken.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if not self.is_edit or password:
            if password and confirm_password and password != confirm_password:
                self.add_error('confirm_password', "Passwords do not match.")
            elif not password and not self.is_edit:
                self.add_error('password', "Password is required for registration.")
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
                    'specialization': self.cleaned_data['specialization'],
                    'experience': self.cleaned_data['experience'],
                    'phone': self.cleaned_data['phone'],
                }
                if self.cleaned_data.get('profile_image'):
                    profile_defaults['profile_image'] = self.cleaned_data['profile_image']

                profile, created = DoctorProfile.objects.get_or_create(
                    user=user,
                    defaults=profile_defaults,
                )
                if not created:
                    profile.specialization = self.cleaned_data['specialization']
                    profile.experience = self.cleaned_data['experience']
                    profile.phone = self.cleaned_data['phone']
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
    """
    Form for Patients to book an appointment.
    """
    appointment_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    appointment_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Please state the reason for this visit...'}))

    class Meta:
        model = Appointment
        fields = ['doctor', 'appointment_date', 'appointment_time', 'reason']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Custom display names for doctors in the choice list
        self.fields['doctor'].queryset = DoctorProfile.objects.all().select_related('user')
        self.fields['doctor'].label_from_instance = lambda obj: f"Dr. {obj.user.first_name} {obj.user.last_name} ({obj.specialization})"

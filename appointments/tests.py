from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from appointments.models import Appointment, Department, DoctorProfile, Hospital, PatientProfile
from appointments.forms import HospitalForm

User = get_user_model()

class HospitalFormTest(TestCase):
    def setUp(self):
        # Create a base hospital to test duplicates
        self.existing_hospital = Hospital.objects.create(
            hospital_name="HopeLife General Hospital",
            location="123 Main St",
            city="Chennai",
            state="Tamil Nadu",
            pincode="600001",
            contact_number="1234567890",
            emergency_available=True,
            latitude=13.0827,
            longitude=80.2707
        )

    def test_valid_hospital_form(self):
        form_data = {
            'hospital_name': 'City Wellness Center',
            'location': '456 Oak Rd',
            'city': 'Bangalore',
            'state': 'Karnataka',
            'pincode': '560001',
            'contact_number': '9876543210',
            'emergency_available': False,
            'latitude': 12.9716,
            'longitude': 77.5946
        }
        form = HospitalForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_duplicate_hospital_name_invalid(self):
        form_data = {
            'hospital_name': 'hopelife general hospital',  # case-insensitive check
            'location': '123 Main St',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'pincode': '600001',
            'contact_number': '1234567890',
            'emergency_available': True,
            'latitude': 13.0827,
            'longitude': 80.2707
        }
        form = HospitalForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('hospital_name', form.errors)
        self.assertEqual(form.errors['hospital_name'][0], "A hospital with this name already exists.")

    def test_contact_number_validations(self):
        # Invalid phone (letters)
        form_data = {
            'hospital_name': 'New Hospital',
            'location': '123 Main St',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'pincode': '600001',
            'contact_number': '123-abc-7890',
            'emergency_available': True,
            'latitude': 13.0827,
            'longitude': 80.2707
        }
        form = HospitalForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('contact_number', form.errors)

        # Invalid phone (too short)
        form_data['contact_number'] = '12345'
        form = HospitalForm(data=form_data)
        self.assertFalse(form.is_valid())

        # Invalid phone (too long)
        form_data['contact_number'] = '12345678901234567'
        form = HospitalForm(data=form_data)
        self.assertFalse(form.is_valid())

        # Valid formatted phone (e.g. space, dashes, brackets)
        form_data['contact_number'] = '(123) 456-7890'
        form = HospitalForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_coordinate_boundaries(self):
        form_data = {
            'hospital_name': 'Boundary Clinic',
            'location': '123 Main St',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'pincode': '600001',
            'contact_number': '1234567890',
            'emergency_available': True,
            'latitude': 95.0,  # Invalid
            'longitude': 80.2707
        }
        form = HospitalForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('latitude', form.errors)

        form_data['latitude'] = 13.0827
        form_data['longitude'] = -190.0  # Invalid
        form = HospitalForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('longitude', form.errors)


class HospitalCrudViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create user accounts for testing permissions
        self.admin_user = User.objects.create_superuser(
            username='adminuser',
            password='adminpassword123',
            email='admin@hopelife.com',
            role='admin'
        )
        self.patient_user = User.objects.create_user(
            username='patientuser',
            password='patientpassword123',
            email='patient@hopelife.com',
            role='patient'
        )
        
        self.hospital = Hospital.objects.create(
            hospital_name="HopeLife General Hospital",
            location="123 Main St",
            city="Chennai",
            state="Tamil Nadu",
            pincode="600001",
            contact_number="1234567890",
            emergency_available=True,
            latitude=13.0827,
            longitude=80.2707
        )

    def test_unauthorized_users_redirected(self):
        # Patient user tries to access admin hospital list
        self.client.login(username='patientuser', password='patientpassword123')
        response = self.client.get(reverse('admin_hospital_list'))
        self.assertEqual(response.status_code, 302)  # Should redirect (access denied)

    def test_admin_view_hospital_list(self):
        self.client.login(username='adminuser', password='adminpassword123')
        response = self.client.get(reverse('admin_hospital_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HopeLife General Hospital")

    def test_admin_add_hospital_view(self):
        self.client.login(username='adminuser', password='adminpassword123')
        
        # Test GET page
        response = self.client.get(reverse('admin_add_hospital'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add New Hospital")

        # Test POST creation
        post_data = {
            'hospital_name': 'New Central Clinic',
            'location': '789 Pine Ave',
            'city': 'Coimbatore',
            'state': 'Tamil Nadu',
            'pincode': '641001',
            'contact_number': '9443322110',
            'emergency_available': True,
            'latitude': 11.0168,
            'longitude': 76.9558
        }
        response = self.client.post(reverse('admin_add_hospital'), data=post_data)
        self.assertRedirects(response, reverse('admin_hospital_list'))
        self.assertTrue(Hospital.objects.filter(hospital_name='New Central Clinic').exists())

    def test_admin_edit_hospital_view(self):
        self.client.login(username='adminuser', password='adminpassword123')
        
        # Test GET page
        response = self.client.get(reverse('admin_edit_hospital', args=[self.hospital.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HopeLife General Hospital")

        # Test POST update
        post_data = {
            'hospital_name': 'Updated HopeLife Hospital',
            'location': '123 Main St Suite B',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'pincode': '600001',
            'contact_number': '1234567890',
            'emergency_available': False,
            'latitude': 13.0827,
            'longitude': 80.2707
        }
        response = self.client.post(reverse('admin_edit_hospital', args=[self.hospital.id]), data=post_data)
        self.assertRedirects(response, reverse('admin_hospital_list'))
        
        self.hospital.refresh_from_db()
        self.assertEqual(self.hospital.hospital_name, 'Updated HopeLife Hospital')
        self.assertFalse(self.hospital.emergency_available)

    def test_admin_delete_hospital_view(self):
        self.client.login(username='adminuser', password='adminpassword123')
        response = self.client.post(reverse('admin_delete_hospital', args=[self.hospital.id]))
        self.assertEqual(response.status_code, 302)  # Should redirect after deletion
        self.assertFalse(Hospital.objects.filter(id=self.hospital.id).exists())


class AppointmentVisibilityTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.hospital = Hospital.objects.create(
            hospital_name="HopeLife General Hospital",
            location="123 Main St",
            city="Chennai",
            state="Tamil Nadu",
            pincode="600001",
            contact_number="1234567890",
        )
        self.department = Department.objects.create(name="Cardiology")

        self.admin_user = User.objects.create_superuser(
            username='adminvisibility',
            password='adminpassword123',
            email='adminvisibility@hopelife.com',
            role='admin',
        )
        self.doctor_user = User.objects.create_user(
            username='doctorone',
            password='doctorpassword123',
            email='doctorone@hopelife.com',
            first_name='John',
            last_name='Doe',
            role='doctor',
        )
        self.other_doctor_user = User.objects.create_user(
            username='doctortwo',
            password='doctorpassword123',
            email='doctortwo@hopelife.com',
            first_name='Nive',
            last_name='V',
            role='doctor',
        )
        self.patient_user = User.objects.create_user(
            username='patientone',
            password='patientpassword123',
            email='patientone@hopelife.com',
            first_name='Patient',
            last_name='One',
            role='patient',
        )
        self.other_patient_user = User.objects.create_user(
            username='patienttwo',
            password='patientpassword123',
            email='patienttwo@hopelife.com',
            first_name='Patient',
            last_name='Two',
            role='patient',
        )

        self.doctor = DoctorProfile.objects.create(
            user=self.doctor_user,
            hospital=self.hospital,
            department=self.department,
            specialization='Cardiology',
            experience=10,
            phone='1111111111',
        )
        self.other_doctor = DoctorProfile.objects.create(
            user=self.other_doctor_user,
            hospital=self.hospital,
            department=self.department,
            specialization='Neurology',
            experience=12,
            phone='2222222222',
        )
        self.patient = PatientProfile.objects.create(
            user=self.patient_user,
            age=30,
            gender='Male',
            phone='3333333333',
            address='Address one',
        )
        self.other_patient = PatientProfile.objects.create(
            user=self.other_patient_user,
            age=32,
            gender='Female',
            phone='4444444444',
            address='Address two',
        )

        scheduled_time = timezone.now() + timezone.timedelta(days=1)
        self.own_appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            hospital=self.hospital,
            scheduled_datetime=scheduled_time,
            reason='Own doctor appointment',
        )
        self.other_appointment = Appointment.objects.create(
            patient=self.other_patient,
            doctor=self.other_doctor,
            hospital=self.hospital,
            scheduled_datetime=scheduled_time,
            reason='Other doctor appointment',
        )

    def test_doctor_dashboard_shows_only_own_appointments(self):
        self.client.login(username='doctorone', password='doctorpassword123')
        response = self.client.get(reverse('doctor_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Own doctor appointment')
        self.assertNotContains(response, 'Other doctor appointment')

    def test_doctor_cannot_view_patient_from_other_doctor_appointment(self):
        self.client.login(username='doctorone', password='doctorpassword123')
        response = self.client.get(reverse('doctor_view_patient', args=[self.other_patient.id]))

        self.assertEqual(response.status_code, 403)

    def test_admin_dashboard_shows_all_appointments(self):
        self.client.login(username='adminvisibility', password='adminpassword123')
        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Own doctor appointment')
        self.assertContains(response, 'Other doctor appointment')

    def test_doctor_cannot_update_other_doctor_appointment_status(self):
        self.client.login(username='doctorone', password='doctorpassword123')
        response = self.client.post(
            reverse('doctor_update_status', args=[self.other_appointment.id]),
            {'status': 'Completed'},
        )

        self.assertEqual(response.status_code, 403)
        self.other_appointment.refresh_from_db()
        self.assertEqual(self.other_appointment.status, 'Pending')

    def test_admin_can_update_any_appointment_status(self):
        self.client.login(username='adminvisibility', password='adminpassword123')
        response = self.client.post(
            reverse('admin_update_appointment_status', args=[self.other_appointment.id]),
            {'status': 'Completed'},
        )

        self.assertRedirects(response, reverse('admin_dashboard'))
        self.other_appointment.refresh_from_db()
        self.assertEqual(self.other_appointment.status, 'Completed')

    def test_patient_sees_only_their_own_appointments(self):
        self.client.login(username='patientone', password='patientpassword123')
        response = self.client.get(reverse('patient_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Own doctor appointment')
        self.assertNotContains(response, 'Other doctor appointment')

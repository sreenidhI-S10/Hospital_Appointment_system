from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from appointments.models import Hospital
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

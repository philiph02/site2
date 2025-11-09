from django import forms
from .models import Order

# --- 1. Order Form (Already Exists) ---
class OrderCreateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['first_name', 'last_name', 'email', 'address', 'postal_code', 'city']
        
        # Labels for the form fields
        labels = {
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'email': 'Email Address',
            'address': 'Address (Street, No.)',
            'postal_code': 'Postal Code',
            'city': 'City',
        }

# --- 2. Registration Form (NEW) ---
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="Required. A valid email address.")

    class Meta:
        model = User
        fields = ("username", "email") # Ask for username and email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
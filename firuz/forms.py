from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Profile


class RegisterForm(UserCreationForm):
    email = forms.EmailField(label='Email')
    role = forms.ChoiceField(label='Роль', choices=Profile.ROLE_CHOICES[:2])

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ['username', 'email', 'role']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Этот email уже зарегистрирован.')
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['phone', 'bio']


class UserForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name']
        labels = {'first_name': 'Имя', 'last_name': 'Фамилия'}

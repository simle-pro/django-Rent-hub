from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Profile, PropertyReport, Review


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


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'text']
        widgets = {
            'rating': forms.Select(choices=[(value, value) for value in range(1, 6)]),
            'text': forms.Textarea(attrs={'rows': 4}),
        }


class ReportForm(forms.ModelForm):
    class Meta:
        model = PropertyReport
        fields = ['reason', 'text']
        widgets = {'text': forms.Textarea(attrs={'rows': 4})}


class RejectForm(forms.Form):
    reason = forms.CharField(label='Причина отклонения', max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))


class ResolutionForm(forms.Form):
    resolution = forms.CharField(label='Решение по жалобе', max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))
    hide_property = forms.BooleanField(label='Скрыть опубликованное объявление', required=False)

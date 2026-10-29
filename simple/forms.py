from django import forms
from django.utils import timezone
from smuhammad.models import PropertyCategory

from .models import Booking

SORT_CHOICES = [
    ('', 'По умолчанию'),
    ('price_asc', 'Цена: по возрастанию'),
    ('price_desc', 'Цена: по убыванию'),
    ('newest', 'Сначала новые'),
]

SORT_DIRECTIONS = {
    'price_asc': 'price',
    'price_desc': '-price',
    'newest': '-created_at',
}


class SearchForm(forms.Form):
    q = forms.CharField(required=False, label='Название или местоположение')
    min_price = forms.DecimalField(required=False, min_value=0, label='Цена от')
    max_price = forms.DecimalField(required=False, min_value=0, label='Цена до')
    category = forms.IntegerField(required=False, min_value=1, label='Тип')
    sort = forms.ChoiceField(required=False, choices=SORT_CHOICES, label='Сортировка')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].widget = forms.Select(choices=[('', 'Любой тип жилья')] + list(PropertyCategory.objects.values_list('pk', 'name')))
        self.amenity_ids = []
        getlist = getattr(self.data, 'getlist', None)
        if getlist:
            for raw in getlist('amenities'):
                try:
                    value = int(raw)
                except (TypeError, ValueError):
                    continue
                if value > 0 and value not in self.amenity_ids:
                    self.amenity_ids.append(value)

    def clean(self):
        cleaned = super().clean()
        min_price = cleaned.get('min_price')
        max_price = cleaned.get('max_price')
        if min_price is not None and max_price is not None and min_price > max_price:
            raise forms.ValidationError('Цена «от» не может быть больше цены «до».')
        return cleaned


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, property_obj=None, **kwargs):
        self.property_obj = property_obj
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get('start_date')
        end_date = cleaned.get('end_date')
        if start_date is not None and end_date is not None:
            if start_date >= end_date:
                raise forms.ValidationError('Дата начала должна быть раньше даты окончания.')
            if start_date < timezone.localdate():
                raise forms.ValidationError('Дата начала не может быть в прошлом.')
            if self.property_obj is not None and Booking.has_approved_overlap(self.property_obj, start_date, end_date):
                raise forms.ValidationError('На выбранные даты уже есть подтверждённая заявка.')
        return cleaned

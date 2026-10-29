from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import Property, Location

MAX_IMAGES_PER_PROPERTY = 10
MAX_IMAGE_SIZE = 5 * 1024 * 1024


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['city', 'address', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}


class PropertyForm(forms.ModelForm):
    """Форма объявления: owner, status и moderation_reason в неё не входят."""

    price = forms.DecimalField(
        label='Цена за сутки',
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        error_messages={
            'required': 'Укажите цену за сутки.',
            'invalid': 'Цена должна быть числом.',
            'min_value': 'Цена за сутки должна быть больше нуля.',
        },
    )

    class Meta:
        model = Property
        fields = ('title', 'description', 'price', 'category', 'location', 'amenities')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6}),
            'amenities': forms.CheckboxSelectMultiple(),
            'title': forms.TextInput(attrs={'placeholder': 'Сдам 2-к квартиру у парка'}),
        }

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if not title:
            raise ValidationError('Введите заголовок объявления.')
        return title


class MultipleImageInput(forms.ClearableFileInput):
    """Разрешает выбрать несколько файлов в одном поле."""

    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """Поле из документации Django: принимает список файлов и проверяет каждый."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleImageInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        files = data if isinstance(data, (list, tuple)) else [data]
        return [single_file_clean(item, initial) for item in files if item]


class PropertyImagesForm(forms.Form):
    """Загрузка нескольких фотографий одного объявления."""

    images = MultipleImageField(label='Фотографии', required=False)

    def clean_images(self):
        images = self.cleaned_data['images']
        if not images:
            raise ValidationError('Выберите хотя бы одну фотографию.')
        if len(images) > MAX_IMAGES_PER_PROPERTY:
            raise ValidationError(
                f'За раз можно загрузить не больше {MAX_IMAGES_PER_PROPERTY} фотографий.'
            )
        for image in images:
            if image.size > MAX_IMAGE_SIZE:
                raise ValidationError(f'Файл «{image.name}» больше 5 МБ.')
        return images

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('firuz', '0002_existing_profiles'),
        ('smuhammad', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PropertyReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(choices=[('fraud', 'Мошенничество'), ('incorrect', 'Неверные сведения'), ('other', 'Другое')], max_length=20, verbose_name='Причина')),
                ('text', models.TextField(max_length=2000, verbose_name='Описание')),
                ('status', models.CharField(choices=[('pending', 'На рассмотрении'), ('resolved', 'Рассмотрена')], default='pending', max_length=10, verbose_name='Статус')),
                ('resolution', models.TextField(blank=True, max_length=2000, verbose_name='Решение')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='smuhammad.property')),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_property_reports', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='property_reports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at', '-pk'],
                'constraints': [models.UniqueConstraint(condition=models.Q(('status', 'pending')), fields=('user', 'property'), name='firuz_unique_pending_report')],
            },
        ),
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='Оценка')),
                ('text', models.TextField(max_length=2000, verbose_name='Отзыв')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='smuhammad.property')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='property_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at', '-pk'],
                'constraints': [models.UniqueConstraint(fields=('user', 'property'), name='firuz_unique_property_review'), models.CheckConstraint(condition=models.Q(('rating__gte', 1), ('rating__lte', 5)), name='firuz_review_rating_range')],
            },
        ),
    ]

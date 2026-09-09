
from django.contrib import admin
from .models import Doctor, Specialty

from django.contrib import admin
from .models import Doctor

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'speciality', 'available_day')
    list_filter = ('speciality',)
    search_fields = ('speciality',)
    ordering = ('speciality',)

@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

# Register your models here.

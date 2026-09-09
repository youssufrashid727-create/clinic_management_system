from functools import wraps
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.core.exceptions import ObjectDoesNotExist
from .models import Person
 
 
def login_required_custom(view_func):
    """Allows any logged-in Person through. Attaches the Person to
    request.person."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        person_id = request.session.get('person_id')
        if not person_id:
            return redirect('login')
        try:
            request.person = Person.objects.get(pk=person_id)
        except Person.DoesNotExist:
            request.session.flush()
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper
 
 
def admin_required(view_func):
    """Only lets Persons with role == 'Admin' through."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        person_id = request.session.get('person_id')
        if not person_id:
            return redirect('login')
        try:
            person = Person.objects.get(pk=person_id)
        except Person.DoesNotExist:
            request.session.flush()
            return redirect('login')
        if person.role != 'Admin':
            return HttpResponseForbidden("Admins only.")
        request.person = person
        return view_func(request, *args, **kwargs)
    return wrapper
 
 
def doctor_required(view_func):
    """Only lets Persons with role == 'Doctor' through, and attaches the
    linked Doctor record to request.doctor."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        person_id = request.session.get('person_id')
        if not person_id:
            return redirect('login')
        try:
            person = Person.objects.get(pk=person_id)
        except Person.DoesNotExist:
            request.session.flush()
            return redirect('login')
        if person.role != 'Doctor':
            return HttpResponseForbidden("Doctors only.")
        try:
            request.doctor = person.employee_profile.doctor_profile
        except ObjectDoesNotExist:
            return HttpResponseForbidden("No doctor profile is linked to this account.")
        request.person = person
        return view_func(request, *args, **kwargs)
    return wrapper
 
 
def patient_required(view_func):
    """Only lets Persons with role == 'Patient' through, and attaches the
    linked Patient record to request.patient."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        person_id = request.session.get('person_id')
        if not person_id:
            return redirect('login')
        try:
            person = Person.objects.get(pk=person_id)
        except Person.DoesNotExist:
            request.session.flush()
            return redirect('login')
        if person.role != 'Patient':
            return HttpResponseForbidden("Patients only.")
        try:
            request.patient = person.patient_profile
        except ObjectDoesNotExist:
            return HttpResponseForbidden("No patient profile is linked to this account.")
        request.person = person
        return view_func(request, *args, **kwargs)
    return wrapper

def nurse_required(view_func):
    """Only lets Persons with role == 'Nurse' through, and attaches the
    linked Nurse record to request.nurse."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        person_id = request.session.get('person_id')
        if not person_id:
            return redirect('login')
        try:
            person = Person.objects.get(pk=person_id)
        except Person.DoesNotExist:
            request.session.flush()
            return redirect('login')
        if person.role != 'Nurse':
            return HttpResponseForbidden("Nurses only.")
        try:
            request.nurse = person.employee_profile.nurse_profile
        except ObjectDoesNotExist:
            return HttpResponseForbidden("No nurse profile is linked to this account.")
        request.person = person
        return view_func(request, *args, **kwargs)
    return wrapper
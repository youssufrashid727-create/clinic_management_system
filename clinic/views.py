from django.contrib.auth.hashers import make_password, check_password
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden
from django.core.exceptions import ObjectDoesNotExist
from .models import Person, Employee, Doctor, Nurse, Patient, MedicalRecord, Appointment, Department, Billing, MedicalImage, Vaccination, Referral, SickLeave, TreatmentPlan
from .decorators import login_required_custom, admin_required, doctor_required, nurse_required
from django.db.models.functions import TruncMonth
from django.db.models import Count
import json
from django.utils import timezone
from django.db.models import Q, Count


def login_view(request):
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')

        try:
            person = Person.objects.get(username=username)
        except Person.DoesNotExist:
            person = None

        if person and check_password(password, person.password):
            request.session['person_id'] = person.pk
            return redirect('dashboard')
        else:
            error = 'Invalid username or password.'

    return render(request, 'clinic/login.html', {'error': error})


def logout_view(request):
    request.session.flush()
    return redirect('login')

@login_required_custom
def toggle_checkin(request):
    """Doctors/Nurses can check themselves in or out."""
    person = request.person
    if person.role not in ('Doctor', 'Nurse'):
        return HttpResponseForbidden("Only doctors and nurses can check in.")

    try:
        employee = person.employee_profile
    except ObjectDoesNotExist:
        return HttpResponseForbidden("No employee profile linked to this account.")

    if request.method == 'POST':
        employee.is_checked_in = not employee.is_checked_in
        if employee.is_checked_in:
            employee.checked_in_at = timezone.now()
            employee.checked_out_at = None
        else:
            employee.checked_out_at = timezone.now()
        employee.save()

    return redirect('dashboard')


def create_person_with_password(raw_password, **person_fields):
    person = Person(**person_fields)
    person.password = make_password(raw_password)
    person.save()
    return person


@login_required_custom

def dashboard_view(request):
    """Single entry point after login. Content shown depends on role."""
    person = request.person

    if person.role == 'Doctor':
        return _doctor_dashboard(request, person)
    elif person.role == 'Patient':
        return _patient_dashboard(request, person)
    elif person.role == 'Admin':
        today = timezone.localdate()
        todays_appointments = Appointment.objects.filter(
            scheduled_time__date=today
        ).select_related(
            'doctor__doctor__employee', 'patient__patient'
        ).order_by('scheduled_time')

        return render(request, 'clinic/admin_dashboard.html', {
            'person': person,
            'todays_appointments': todays_appointments,
            'doctor_count': Doctor.objects.count(),
            'nurse_count': Nurse.objects.count(),
            'patient_count': Patient.objects.count(),
            'todays_appointment_count': todays_appointments.count(),
        })
    elif person.role == 'Nurse':
        return _nurse_dashboard(request, person)

    return HttpResponse(f"Logged in as {person.username} (role: {person.role})")


def _doctor_dashboard(request, person):
    try:
        doctor = person.employee_profile.doctor_profile
    except ObjectDoesNotExist:
        return HttpResponseForbidden("No doctor profile is linked to this account.")

    appointments = Appointment.objects.filter(doctor=doctor).order_by('scheduled_time')

    today = timezone.localdate()
    todays_appointments = appointments.filter(scheduled_time__date=today)

    patients = Patient.objects.all()
    error = None

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'update_status':
            appointment_id = request.POST.get('appointment_id')
            new_status = request.POST.get('status')
            new_note = request.POST.get('note', '')
            appointment = get_object_or_404(Appointment, pk=appointment_id, doctor=doctor)
            appointment.status = new_status
            appointment.note = new_note
            appointment.save()
            return redirect('dashboard')

        elif form_type == 'schedule_new':
            patient_id = request.POST.get('patient_id')
            scheduled_time = request.POST.get('scheduled_time')
            reason = request.POST.get('reason', '')

            try:
                patient = Patient.objects.get(pk=patient_id)
            except Patient.DoesNotExist:
                patient = None

            if patient and scheduled_time:
                Appointment.objects.create(
                    doctor=doctor,
                    patient=patient,
                    department=doctor.doctor.department,
                    scheduled_time=scheduled_time,
                    status='scheduled',
                    reason=reason,
                )
                return redirect('dashboard')
            else:
                error = 'Please choose a patient and set a date/time.'

    return render(request, 'clinic/doctor_appointments.html', {
    'appointments': appointments,
    'todays_appointments': todays_appointments,
    'patients': patients,
    'doctor': doctor,
    'error': error,
    })

def _nurse_dashboard(request, person):
    try:
        nurse = person.employee_profile.nurse_profile
    except ObjectDoesNotExist:
        return HttpResponseForbidden("No nurse profile is linked to this account.")

    return render(request, 'clinic/nurse_dashboard.html', {'nurse': nurse})


def _patient_dashboard(request, person):
    try:
        patient = person.patient_profile
    except ObjectDoesNotExist:
        return HttpResponseForbidden("No patient profile is linked to this account.")

    appointments = Appointment.objects.filter(patient=patient).order_by('scheduled_time')
    records = MedicalRecord.objects.filter(patient=patient).order_by('-visit_date')

    return render(request, 'clinic/patient_dashboard.html', {
        'patient': patient,
        'appointments': appointments,
        'records': records,
    })

@admin_required
def create_account(request):
    error = None

    if request.method == 'POST':
        role = request.POST.get('role')

        try:
            person = create_person_with_password(
                request.POST.get('password'),
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                age=request.POST.get('age'),
                address=request.POST.get('address'),
                phone_number=request.POST.get('phone_number'),
                sex=request.POST.get('sex'),
                role=role,
                username=request.POST.get('username'),
                email=request.POST.get('email'),
            )

            if role in ('Doctor', 'Nurse'):
                department_id = request.POST.get('department') or None
                employee = Employee.objects.create(
                    employee=person,
                    department_id=department_id,
                    salary=request.POST.get('salary') or None,
                    employment_day=request.POST.get('employment_day'),
                )
                if role == 'Doctor':
                    Doctor.objects.create(
                        doctor=employee,
                        speciality=request.POST.get('speciality', ''),
                        available_day=request.POST.get('available_day'),
                    )
                else:
                    Nurse.objects.create(
                        nurse=employee,
                        license_num=request.POST.get('license_num', ''),
                        shift=request.POST.get('shift', ''),
                    )

            elif role == 'Patient':
                Patient.objects.create(
                    patient=person,
                    blood_type=request.POST.get('blood_type', ''),
                )

            return redirect('create_account')

        except Exception as e:
            error = f"Could not create account: {e}"

    departments = Department.objects.all().order_by('department_name')
    return render(request, 'clinic/create_account.html', {'error': error, 'departments': departments})


@doctor_required
def doctor_patient_detail(request, patient_id):
    """View + edit a patient's basic info, and view/add their medical
    records. Restricted to patients this doctor actually has an
    appointment or existing record with."""
    patient = get_object_or_404(Patient, pk=patient_id)

    has_relationship = (
        Appointment.objects.filter(doctor=request.doctor, patient=patient).exists()
        or MedicalRecord.objects.filter(doctor=request.doctor, patient=patient).exists()
    )
    if not has_relationship:
        return HttpResponseForbidden("You don't have an appointment or record with this patient.")

    records = MedicalRecord.objects.filter(patient=patient).order_by('-visit_date')

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'edit_patient':
            patient.blood_type = request.POST.get('blood_type', patient.blood_type)
            patient.save()

        elif form_type == 'add_record':
            record = MedicalRecord.objects.create(
                doctor=request.doctor,
                patient=patient,
                allergies=request.POST.get('allergies', ''),
                visit_date=request.POST.get('visit_date') or None,
                prescription=request.POST.get('prescription', ''),
                hereditary_diseases=request.POST.get('hereditary_diseases', ''),
                diagnosis=request.POST.get('diagnosis', ''),
                dosage=request.POST.get('dosage', ''),
            )
            for f in request.FILES.getlist('images'):
                MedicalImage.objects.create(record=record, image=f)

        elif form_type == 'add_image':
            record_id = request.POST.get('record_id')
            record = get_object_or_404(MedicalRecord, pk=record_id, patient=patient)
            for f in request.FILES.getlist('images'):
                MedicalImage.objects.create(record=record, image=f)

        return redirect('doctor_patient_detail', patient_id=patient.pk)

    return render(request, 'clinic/patient_detail.html', {
        'patient': patient,
        'records': records,
    })


@admin_required
def admin_doctor_list(request):
    """Admin-only: view all doctors, optionally filtered by speciality."""
    speciality = request.GET.get('speciality', '')

    doctors = Doctor.objects.select_related('doctor__employee').all()
    if speciality:
        doctors = doctors.filter(speciality=speciality)

    all_specialities = Doctor.objects.values_list('speciality', flat=True).distinct().order_by('speciality')

    return render(request, 'clinic/admin_doctor_list.html', {
        'doctors': doctors,
        'all_specialities': all_specialities,
        'selected_speciality': speciality,
    })

@admin_required
def edit_doctor(request, doctor_id):
    doctor = get_object_or_404(Doctor, pk=doctor_id)
    employee = doctor.doctor
    person = employee.employee
    error = None

    if request.method == 'POST':
        person.first_name = request.POST.get('first_name', person.first_name)
        person.last_name = request.POST.get('last_name', person.last_name)
        person.age = request.POST.get('age', person.age)
        person.address = request.POST.get('address', person.address)
        person.phone_number = request.POST.get('phone_number', person.phone_number)
        person.sex = request.POST.get('sex', person.sex)
        person.username = request.POST.get('username', person.username)
        person.email = request.POST.get('email', person.email)

        employee.salary = request.POST.get('salary') or employee.salary
        employee.employment_day = request.POST.get('employment_day') or employee.employment_day

        doctor.speciality = request.POST.get('speciality', doctor.speciality)
        doctor.available_day = request.POST.get('available_day') or doctor.available_day

        try:
            person.save()
            employee.save()
            doctor.save()
            return redirect('admin_doctor_list')
        except Exception as e:
            error = f"Could not save changes: {e}"

    return render(request, 'clinic/edit_doctor.html', {
        'doctor': doctor,
        'employee': employee,
        'person': person,
        'error': error,
    })


@admin_required
def delete_doctor(request, doctor_id):
    doctor = get_object_or_404(Doctor, pk=doctor_id)
    person = doctor.doctor.employee

    if request.method == 'POST':
        person.delete()  # cascades to Employee and Doctor automatically
        return redirect('admin_doctor_list')

    return render(request, 'clinic/delete_doctor_confirm.html', {'doctor': doctor})

@admin_required
def admin_nurse_list(request):
    """Admin-only: view all nurses, optionally filtered by department and/or shift."""
    department_id = request.GET.get('department', '')
    shift = request.GET.get('shift', '')

    nurses = Nurse.objects.select_related('nurse__employee', 'nurse__department').all()
    if department_id:
        nurses = nurses.filter(nurse__department_id=department_id)
    if shift:
        nurses = nurses.filter(shift=shift)

    all_departments = Department.objects.all().order_by('department_name')
    all_shifts = Nurse.objects.values_list('shift', flat=True).distinct().order_by('shift')

    return render(request, 'clinic/admin_nurse_list.html', {
        'nurses': nurses,
        'all_departments': all_departments,
        'all_shifts': all_shifts,
        'selected_department': department_id,
        'selected_shift': shift,
    })
@admin_required
def edit_nurse(request, nurse_id):
    nurse = get_object_or_404(Nurse, pk=nurse_id)
    employee = nurse.nurse
    person = employee.employee
    error = None

    if request.method == 'POST':
        person.first_name = request.POST.get('first_name', person.first_name)
        person.last_name = request.POST.get('last_name', person.last_name)
        person.age = request.POST.get('age', person.age)
        person.address = request.POST.get('address', person.address)
        person.phone_number = request.POST.get('phone_number', person.phone_number)
        person.sex = request.POST.get('sex', person.sex)
        person.username = request.POST.get('username', person.username)
        person.email = request.POST.get('email', person.email)

        employee.salary = request.POST.get('salary') or employee.salary
        employee.employment_day = request.POST.get('employment_day') or employee.employment_day
        employee.department_id = request.POST.get('department') or None

        nurse.license_num = request.POST.get('license_num', nurse.license_num)
        nurse.shift = request.POST.get('shift', nurse.shift)

        try:
            person.save()
            employee.save()
            nurse.save()
            return redirect('admin_nurse_list')
        except Exception as e:
            error = f"Could not save changes: {e}"

    departments = Department.objects.all().order_by('department_name')
    return render(request, 'clinic/edit_nurse.html', {
        'nurse': nurse,
        'employee': employee,
        'person': person,
        'departments': departments,
        'error': error,
    })


@admin_required
def delete_nurse(request, nurse_id):
    nurse = get_object_or_404(Nurse, pk=nurse_id)
    person = nurse.nurse.employee

    if request.method == 'POST':
        person.delete()  # cascades to Employee and Nurse automatically
        return redirect('admin_nurse_list')

    return render(request, 'clinic/delete_nurse_confirm.html', {'nurse': nurse})

@admin_required
def admin_department_list(request):
    departments = Department.objects.all().order_by('department_name')
    error = None

    if request.method == 'POST' and request.POST.get('form_type') == 'create_department':
        name = request.POST.get('department_name', '').strip()
        if name:
            Department.objects.create(department_name=name)
            return redirect('admin_department_list')
        else:
            error = 'Department name is required.'

    return render(request, 'clinic/admin_department_list.html', {
        'departments': departments,
        'error': error,
    })


@admin_required
def department_detail(request, department_id):
    department = get_object_or_404(Department, pk=department_id)
    doctors = Doctor.objects.filter(doctor__department=department).select_related('doctor__employee')
    nurses = Nurse.objects.filter(nurse__department=department).select_related('nurse__employee')
    checked_in_doctors = doctors.filter(doctor__is_checked_in=True)
    checked_in_nurses = nurses.filter(nurse__is_checked_in=True)
    checked_out_doctors = doctors.filter(doctor__is_checked_in=False, doctor__checked_out_at__isnull=False)
    checked_out_nurses = nurses.filter(nurse__is_checked_in=False, nurse__checked_out_at__isnull=False)
    error = None

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'edit_department':
            new_name = request.POST.get('department_name', '').strip()
            if new_name:
                department.department_name = new_name
                department.save()
                return redirect('department_detail', department_id=department.pk)
            else:
                error = 'Department name is required.'

        elif form_type == 'add_member':
            employee_id = request.POST.get('employee_id')
            try:
                employee = Employee.objects.get(pk=employee_id)
                employee.department = department
                employee.save()
            except Employee.DoesNotExist:
                error = 'Employee not found.'
            return redirect('department_detail', department_id=department.pk)

    available_employees = Employee.objects.exclude(department=department).select_related('employee')

    return render(request, 'clinic/department_detail.html', {
        'department': department,
        'doctors': doctors,
        'nurses': nurses,
        'checked_in_doctors': checked_in_doctors,
        'checked_in_nurses': checked_in_nurses,
        'checked_out_doctors': checked_out_doctors,
        'checked_out_nurses': checked_out_nurses,
        'available_employees': available_employees,
        'error': error,
    })

@admin_required
def remove_department_member(request, department_id, employee_id):
    department = get_object_or_404(Department, pk=department_id)
    employee = get_object_or_404(Employee, pk=employee_id, department=department)

    if request.method == 'POST':
        employee.department = None
        employee.save()

    return redirect('department_detail', department_id=department.pk)

@admin_required
def department_visit_stats(request):
    appointments = (
        Appointment.objects
        .exclude(scheduled_time__isnull=True)
        .exclude(department__isnull=True)
        .annotate(month=TruncMonth('scheduled_time'))
        .values('month', 'department__department_name')
        .annotate(count=Count('appointment_id'))
        .order_by('month')
    )

    months = sorted({a['month'] for a in appointments})
    departments = sorted({a['department__department_name'] for a in appointments})

    data = {dept: {m: 0 for m in months} for dept in departments}
    for a in appointments:
        data[a['department__department_name']][a['month']] = a['count']

    month_labels = [m.strftime('%b %Y') for m in months]
    datasets = [
        {'label': dept, 'data': [data[dept][m] for m in months]}
        for dept in departments
    ]

    return render(request, 'clinic/department_visit_stats.html', {
        'month_labels': json.dumps(month_labels),
        'datasets': json.dumps(datasets),
        'has_data': bool(months),
    })
@admin_required
def admin_appointment_list(request):
    appointments = Appointment.objects.select_related(
        'doctor__doctor__employee', 'patient__patient'
    ).order_by('-scheduled_time')

    return render(request, 'clinic/admin_appointment_list.html', {
        'appointments': appointments,
    })


@admin_required
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related(
            'doctor__doctor__employee', 'patient__patient', 'department'
        ),
        pk=appointment_id
    )

    medical_records = MedicalRecord.objects.filter(
        patient=appointment.patient, doctor=appointment.doctor
    ).order_by('-visit_date')

    billing = Billing.objects.filter(appointment=appointment).first()

    return render(request, 'clinic/appointment_detail.html', {
        'appointment': appointment,
        'medical_records': medical_records,
        'billing': billing,
    })

@admin_required
def admin_medical_record_list(request):
    """Admin-only: view all medical records, optionally filtered by doctor."""
    doctor_id = request.GET.get('doctor', '')

    records = MedicalRecord.objects.select_related(
        'doctor__doctor__employee', 'patient__patient'
    ).order_by('-visit_date')

    if doctor_id:
        records = records.filter(doctor_id=doctor_id)

    all_doctors = Doctor.objects.select_related('doctor__employee').all()

    return render(request, 'clinic/admin_medical_record_list.html', {
        'records': records,
        'all_doctors': all_doctors,
        'selected_doctor': doctor_id,
    })


@admin_required
def admin_medical_record_detail(request, record_id):
    """Admin-only: view and edit a single medical record."""
    record = get_object_or_404(
        MedicalRecord.objects.select_related('doctor__doctor__employee', 'patient__patient'),
        pk=record_id
    )
    error = None

    if request.method == 'POST':
        record.visit_date = request.POST.get('visit_date') or record.visit_date
        record.diagnosis = request.POST.get('diagnosis', record.diagnosis)
        record.prescription = request.POST.get('prescription', record.prescription)
        record.dosage = request.POST.get('dosage', record.dosage)
        record.allergies = request.POST.get('allergies', record.allergies)
        record.hereditary_diseases = request.POST.get('hereditary_diseases', record.hereditary_diseases)

        try:
            record.save()
            return redirect('admin_medical_record_detail', record_id=record.pk)
        except Exception as e:
            error = f"Could not save changes: {e}"

    return render(request, 'clinic/admin_medical_record_detail.html', {
        'record': record,
        'error': error,
    })

@admin_required
def admin_billing_list(request):
    """Admin-only: view all billing records, filtered by appointment status and/or patient name."""
    status = request.GET.get('status', '')
    patient_name = request.GET.get('patient_name', '').strip()
    error = None

    # Pre-fill values when arriving from an appointment's "Create Bill" link
    prefill_patient_id = request.GET.get('patient_id', '')
    prefill_appointment_id = request.GET.get('appointment_id', '')
    prefill_doctor_name = ''
    if prefill_appointment_id:
        try:
            appt = Appointment.objects.select_related('doctor__doctor__employee').get(pk=prefill_appointment_id)
            prefill_doctor_name = f"Dr. {appt.doctor.doctor.employee.first_name} {appt.doctor.doctor.employee.last_name}"
        except Appointment.DoesNotExist:
            pass

    if request.method == 'POST' and request.POST.get('form_type') == 'create_billing':
        patient_id = request.POST.get('patient_id')
        appointment_id = request.POST.get('appointment_id') or None
        total_amount = request.POST.get('total_amount')
        payment_status = request.POST.get('payment_status', 'pending')

        try:
            patient = Patient.objects.get(pk=patient_id)
            Billing.objects.create(
                receiver=patient,
                appointment_id=appointment_id,
                total_amount=total_amount,
                payment_status=payment_status,
            )
            return redirect('admin_billing_list')
        except Exception as e:
            error = f"Could not create bill: {e}"

    billings = Billing.objects.select_related(
        'receiver__patient', 'appointment'
    ).order_by('-bill_id')

    if status:
        billings = billings.filter(appointment__status=status)

    if patient_name:
        billings = billings.filter(
            Q(receiver__patient__first_name__icontains=patient_name) |
            Q(receiver__patient__last_name__icontains=patient_name)
        )

    all_patients = Patient.objects.select_related('patient').all()

    return render(request, 'clinic/admin_billing_list.html', {
        'billings': billings,
        'selected_status': status,
        'patient_name': patient_name,
        'all_patients': all_patients,
        'error': error,
        'prefill_patient_id': prefill_patient_id,
        'prefill_appointment_id': prefill_appointment_id,
        'prefill_doctor_name': prefill_doctor_name,
    })

@admin_required
def admin_employee_list(request):
    """Admin-only: view all employees (doctors + nurses), filterable by role, speciality, and salary."""
    role = request.GET.get('role', '')
    speciality = request.GET.get('speciality', '')
    min_salary = request.GET.get('min_salary', '')

    employees = Employee.objects.select_related('employee', 'department').all()

    if role == 'Doctor':
        employees = employees.filter(doctor_profile__isnull=False)
        if speciality:
            employees = employees.filter(doctor_profile__speciality=speciality)
    elif role == 'Nurse':
        employees = employees.filter(nurse_profile__isnull=False)

    if min_salary:
        try:
            employees = employees.filter(salary__gte=int(min_salary))
        except ValueError:
            pass

    employees = employees.order_by('employee__last_name')

    all_specialities = Doctor.objects.values_list('speciality', flat=True).distinct().order_by('speciality')

    return render(request, 'clinic/admin_employee_list.html', {
        'employees': employees,
        'selected_role': role,
        'selected_speciality': speciality,
        'min_salary': min_salary,
        'all_specialities': all_specialities,
    })

@nurse_required
def nurse_patient_list(request):
    """Nurse-only: view all patients."""
    patients = Patient.objects.select_related('patient').order_by('patient__last_name')

    return render(request, 'clinic/nurse_patient_list.html', {
        'patients': patients,
    })


@nurse_required
def nurse_patient_detail(request, patient_id):
    """Nurse-only: edit a patient's basic info and assign them to a doctor."""
    patient = get_object_or_404(Patient, pk=patient_id)
    doctors = Doctor.objects.select_related('doctor__employee').all()
    error = None

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'edit_patient':
            patient.blood_type = request.POST.get('blood_type', patient.blood_type)
            patient.save()

        elif form_type == 'assign_doctor':
            doctor_id = request.POST.get('doctor_id')
            scheduled_time = request.POST.get('scheduled_time')
            reason = request.POST.get('reason', '')

            try:
                doctor = Doctor.objects.get(pk=doctor_id)
            except Doctor.DoesNotExist:
                doctor = None

            if doctor and scheduled_time:
                Appointment.objects.create(
                    doctor=doctor,
                    patient=patient,
                    department=doctor.doctor.department,
                    scheduled_time=scheduled_time,
                    status='scheduled',
                    reason=reason,
                )
            else:
                error = 'Please choose a doctor and set a date/time.'

        return redirect('nurse_patient_detail', patient_id=patient.pk)

    appointments = Appointment.objects.filter(patient=patient).select_related(
        'doctor__doctor__employee'
    ).order_by('-scheduled_time')

    return render(request, 'clinic/nurse_patient_detail.html', {
        'patient': patient,
        'doctors': doctors,
        'appointments': appointments,
        'error': error,
    })

@nurse_required
def nurse_add_patient(request):
    """Nurse-only: create a new Patient account, optionally assigning them to a doctor right away."""
    error = None
    doctors = Doctor.objects.select_related('doctor__employee').all()

    if request.method == 'POST':
        try:
            person = create_person_with_password(
                request.POST.get('password'),
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                age=request.POST.get('age'),
                address=request.POST.get('address'),
                phone_number=request.POST.get('phone_number'),
                sex=request.POST.get('sex'),
                role='Patient',
                username=request.POST.get('username'),
                email=request.POST.get('email'),
            )
            patient = Patient.objects.create(
                patient=person,
                blood_type=request.POST.get('blood_type', ''),
            )

            doctor_id = request.POST.get('doctor_id')
            scheduled_time = request.POST.get('scheduled_time')
            if doctor_id and scheduled_time:
                doctor = Doctor.objects.get(pk=doctor_id)
                Appointment.objects.create(
                    doctor=doctor,
                    patient=patient,
                    department=doctor.doctor.department,
                    scheduled_time=scheduled_time,
                    status='scheduled',
                    reason=request.POST.get('reason', ''),
                )

            return redirect('nurse_patient_detail', patient_id=patient.pk)
        except Exception as e:
            error = f"Could not create patient: {e}"

    return render(request, 'clinic/nurse_add_patient.html', {'error': error, 'doctors': doctors})

@admin_required
def admin_sick_leave_list(request):
    """Admin-only: view and approve/reject sick leave requests."""
    status = request.GET.get('status', 'pending')

    leaves = SickLeave.objects.select_related('employee__employee').order_by('-requested_at')
    if status:
        leaves = leaves.filter(status=status)

    if request.method == 'POST':
        leave_id = request.POST.get('leave_id')
        action = request.POST.get('action')
        leave = get_object_or_404(SickLeave, pk=leave_id)
        if action in ('approved', 'rejected'):
            leave.status = action
            leave.reviewed_by = request.person
            leave.save()
        return redirect('admin_sick_leave_list')

    return render(request, 'clinic/admin_sick_leave_list.html', {
        'leaves': leaves,
        'selected_status': status,
    })

@login_required_custom
def request_sick_leave(request):
    """Doctors and Nurses can request sick leave; view their own request history."""
    person = request.person
    if person.role not in ('Doctor', 'Nurse'):
        return HttpResponseForbidden("Only doctors and nurses can request sick leave.")

    try:
        employee = person.employee_profile
    except ObjectDoesNotExist:
        return HttpResponseForbidden("No employee profile linked to this account.")

    error = None

    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason', '')

        if start_date and end_date:
            SickLeave.objects.create(
                employee=employee,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
            )
            return redirect('request_sick_leave')
        else:
            error = 'Please provide both a start and end date.'

    my_leaves = SickLeave.objects.filter(employee=employee).order_by('-requested_at')

    return render(request, 'clinic/request_sick_leave.html', {
        'my_leaves': my_leaves,
        'error': error,
    })

@doctor_required
def doctor_patient_vaccinations(request, patient_id):
    """Doctor-only: view and record a patient's vaccination history."""
    patient = get_object_or_404(Patient, pk=patient_id)

    has_relationship = (
        Appointment.objects.filter(doctor=request.doctor, patient=patient).exists()
        or MedicalRecord.objects.filter(doctor=request.doctor, patient=patient).exists()
    )
    if not has_relationship:
        return HttpResponseForbidden("You don't have an appointment or record with this patient.")

    if request.method == 'POST':
        Vaccination.objects.create(
            patient=patient,
            administered_by=request.doctor.doctor,
            vaccine_name=request.POST.get('vaccine_name', ''),
            dose_number=request.POST.get('dose_number') or None,
            date_administered=request.POST.get('date_administered') or None,
            next_due_date=request.POST.get('next_due_date') or None,
            notes=request.POST.get('notes', ''),
        )
        return redirect('doctor_patient_vaccinations', patient_id=patient.pk)

    vaccinations = Vaccination.objects.filter(patient=patient).order_by('-date_administered')

    return render(request, 'clinic/doctor_patient_vaccinations.html', {
        'patient': patient,
        'vaccinations': vaccinations,
    })

@doctor_required
def doctor_patient_referrals(request, patient_id):
    """Doctor-only: view and create referrals for a patient, internal or external."""
    patient = get_object_or_404(Patient, pk=patient_id)

    has_relationship = (
        Appointment.objects.filter(doctor=request.doctor, patient=patient).exists()
        or MedicalRecord.objects.filter(doctor=request.doctor, patient=patient).exists()
    )
    if not has_relationship:
        return HttpResponseForbidden("You don't have an appointment or record with this patient.")

    other_doctors = Doctor.objects.select_related('doctor__employee').exclude(pk=request.doctor.pk)
    error = None

    if request.method == 'POST':
        referral_type = request.POST.get('referral_type')

        if referral_type == 'internal':
            referred_to_id = request.POST.get('referred_to_doctor')
            if referred_to_id:
                Referral.objects.create(
                    patient=patient,
                    referring_doctor=request.doctor,
                    referred_to_doctor_id=referred_to_id,
                    reason=request.POST.get('reason', ''),
                )
            else:
                error = 'Please choose a doctor to refer to.'
        else:
            external_name = request.POST.get('external_doctor_name', '').strip()
            if external_name:
                Referral.objects.create(
                    patient=patient,
                    referring_doctor=request.doctor,
                    external_doctor_name=external_name,
                    external_facility=request.POST.get('external_facility', ''),
                    reason=request.POST.get('reason', ''),
                )
            else:
                error = 'Please enter the external doctor\'s name.'

        if not error:
            return redirect('doctor_patient_referrals', patient_id=patient.pk)

    referrals = Referral.objects.filter(patient=patient).select_related(
        'referring_doctor__doctor__employee', 'referred_to_doctor__doctor__employee'
    ).order_by('-referral_date')

    return render(request, 'clinic/doctor_patient_referrals.html', {
        'patient': patient,
        'referrals': referrals,
        'other_doctors': other_doctors,
        'error': error,
    })

@doctor_required
def doctor_patient_treatment_plans(request, patient_id):
    """Doctor-only: view and create treatment plans for a patient."""
    patient = get_object_or_404(Patient, pk=patient_id)

    has_relationship = (
        Appointment.objects.filter(doctor=request.doctor, patient=patient).exists()
        or MedicalRecord.objects.filter(doctor=request.doctor, patient=patient).exists()
    )
    if not has_relationship:
        return HttpResponseForbidden("You don't have an appointment or record with this patient.")

    error = None

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'add_plan':
            start_date = request.POST.get('start_date')
            if start_date:
                TreatmentPlan.objects.create(
                    patient=patient,
                    doctor=request.doctor,
                    diagnosis=request.POST.get('diagnosis', ''),
                    plan_details=request.POST.get('plan_details', ''),
                    start_date=start_date,
                    end_date=request.POST.get('end_date') or None,
                    status='active',
                )
            else:
                error = 'Start date is required.'

        elif form_type == 'update_status':
            plan_id = request.POST.get('plan_id')
            new_status = request.POST.get('status')
            plan = get_object_or_404(TreatmentPlan, pk=plan_id, patient=patient)
            plan.status = new_status
            plan.save()

        if not error:
            return redirect('doctor_patient_treatment_plans', patient_id=patient.pk)

    plans = TreatmentPlan.objects.filter(patient=patient).order_by('-created_at')

    return render(request, 'clinic/doctor_patient_treatment_plans.html', {
        'patient': patient,
        'plans': plans,
        'error': error,
    })
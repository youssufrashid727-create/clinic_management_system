from django.db import models


class Person(models.Model):
    SEX_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]

    user_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    age = models.IntegerField()
    address = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=11)
    sex = models.CharField(max_length=1, choices=SEX_CHOICES)
    role = models.CharField(max_length=55, null=True, blank=True)

    # --- login fields ---
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128) 

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Employee(models.Model):
    """An Employee IS a Person (employee_id links to Person.user_id)."""
    employee = models.OneToOneField(
        Person, on_delete=models.CASCADE, primary_key=True,
        db_column='EmployeeID', related_name='employee_profile'
    )
    department = models.ForeignKey(
        'Department', on_delete=models.SET_NULL, null=True, blank=True,
        db_column='DepartmentID'
    )
    salary = models.IntegerField(null=True, blank=True)
    employment_day = models.DateField()
    is_checked_in = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.employee.first_name} {self.employee.last_name}"

    
class Department(models.Model):
    department_id = models.AutoField(primary_key=True)
    department_name = models.CharField(max_length=55)
    head_doctor = models.ForeignKey(
        'Doctor', on_delete=models.SET_NULL, null=True, blank=True,
        db_column='HeadDoctor', related_name='departments_headed'
    )

    def __str__(self):
        return self.department_name


class Doctor(models.Model):
    doctor = models.OneToOneField(
        Employee, on_delete=models.CASCADE, primary_key=True,
        db_column='DoctorID', related_name='doctor_profile'
    )
    speciality = models.CharField(max_length=50)
    available_day = models.DateTimeField()

    def __str__(self):
        return f"Dr. {self.doctor.employee.last_name} ({self.speciality})"


class Nurse(models.Model):
    nurse = models.OneToOneField(
        Employee, on_delete=models.CASCADE, primary_key=True,
        db_column='NurseID', related_name='nurse_profile'
    )
    license_num = models.CharField(max_length=50)
    shift = models.CharField(max_length=50)

    def __str__(self):
        return f"Nurse {self.nurse.employee.last_name} ({self.shift})"


class Patient(models.Model):
    patient = models.OneToOneField(
        Person, on_delete=models.CASCADE, primary_key=True,
        db_column='PatientID', related_name='patient_profile'
    )
    blood_type = models.CharField(max_length=3)
    guardian = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dependents'
    )
    def __str__(self):
        return f"Patient {self.patient.first_name} {self.patient.last_name}"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('complete', 'Complete'),
        ('canceled', 'Canceled'),
    ]

    appointment_id = models.AutoField(primary_key=True)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, null=True, blank=True)
    reason = models.CharField(max_length=255, null=True, blank=True)
    note = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Appointment {self.appointment_id} ({self.status})"


class MedicalRecord(models.Model):
    record_id = models.AutoField(primary_key=True)
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True)
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True)
    allergies = models.CharField(max_length=50, null=True, blank=True)
    visit_date = models.DateField(null=True, blank=True)
    prescription = models.CharField(max_length=50, null=True, blank=True)
    hereditary_diseases = models.CharField(max_length=50, null=True, blank=True)
    diagnosis = models.CharField(max_length=50, null=True, blank=True)
    dosage = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Record {self.record_id} for Patient {self.patient_id}"


class Billing(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('pending', 'Pending'),
    ]

    bill_id = models.AutoField(primary_key=True)
    receiver = models.ForeignKey(Patient, on_delete=models.CASCADE)
    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, null=True, blank=True)

    def __str__(self):
        return f"Bill {self.bill_id} - {self.payment_status}"

class Specialty(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class MedicalImage(models.Model):
    record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='medical_images/')
    caption = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for Record {self.record_id}"

class Vaccination(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='vaccinations')
    administered_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    vaccine_name = models.CharField(max_length=100)
    dose_number = models.PositiveIntegerField(null=True, blank=True)
    date_administered = models.DateField()
    next_due_date = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.vaccine_name} - {self.patient}"


class Referral(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='referrals')
    referring_doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals_made')

    # Internal referral (to a doctor in this system)
    referred_to_doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals_received')

    # External referral (outside the hospital) — used when referred_to_doctor is empty
    external_doctor_name = models.CharField(max_length=100, blank=True)
    external_facility = models.CharField(max_length=150, blank=True)

    reason = models.CharField(max_length=255, blank=True)
    referral_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        target = self.referred_to_doctor or self.external_doctor_name or "Unknown"
        return f"Referral for {self.patient} to {target}"


class SickLeave(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='sick_leaves')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name='sick_leaves_reviewed')

    def __str__(self):
        return f"Sick leave: {self.employee} ({self.status})"


class TreatmentPlan(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('discontinued', 'Discontinued'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='treatment_plans')
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True)
    diagnosis = models.CharField(max_length=150, blank=True)
    plan_details = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Treatment plan for {self.patient} ({self.status})"
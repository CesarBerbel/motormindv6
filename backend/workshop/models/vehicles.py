from .common import *

class Vehicle(TimeStampedModel):
    class SteeringType(models.TextChoices):
        MANUAL = "manual", "Mecânica"
        HYDRAULIC = "hydraulic", "Hidráulica"
        ELECTRIC = "electric", "Elétrica"
        ELECTRO_HYDRAULIC = "electro_hydraulic", "Eletro-hidráulica"

    class TransmissionType(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTOMATIC = "automatic", "Automático"
        AUTOMATED = "automated", "Automatizado"
        CVT = "cvt", "CVT"
        DUAL_CLUTCH = "dual_clutch", "Dupla embreagem"

    customer = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="vehicles")
    plate = models.CharField(max_length=20, unique=True)
    make = models.CharField(max_length=80)
    model = models.CharField(max_length=120)
    version = models.CharField(max_length=120, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    color = models.CharField(max_length=50, blank=True)
    vin = models.CharField(max_length=40, blank=True)
    odometer_km = models.PositiveIntegerField(default=0)
    steering_type = models.CharField(max_length=30, choices=SteeringType.choices, blank=True)
    has_air_conditioning = models.BooleanField(default=False)
    door_count = models.PositiveSmallIntegerField(null=True, blank=True)
    transmission_type = models.CharField(max_length=30, choices=TransmissionType.choices, blank=True)
    is_modified = models.BooleanField(default=False)
    fipe_brand_code = models.CharField(max_length=30, blank=True, db_index=True)
    fipe_model_code = models.CharField(max_length=30, blank=True, db_index=True)
    fipe_year_code = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_vehicles")

    class Meta:
        ordering = ["plate"]

    @property
    def has_fipe_link(self):
        return bool(self.fipe_brand_code and self.fipe_model_code)

    @property
    def display_name(self):
        year = f" {self.year}" if self.year else ""
        return f"{self.plate} - {self.make} {self.model}{year}".strip()

    @property
    def steering_type_label(self):
        return self.get_steering_type_display() if self.steering_type else ""

    @property
    def transmission_type_label(self):
        return self.get_transmission_type_display() if self.transmission_type else ""

    def __str__(self):
        return self.display_name



from .common import *


class VehicleViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleSerializer
    permission_classes = [HasViewPermission]
    permission_code_map = {"read": "vehicles.view", "write": "vehicles.manage"}
    queryset = Vehicle.objects.select_related("customer").all()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        customer_id = self.request.query_params.get("customer")
        active = self.request.query_params.get("active")
        if search:
            search_digits = "".join(ch for ch in search if ch.isdigit())
            query = (
                Q(plate__icontains=search)
                | Q(make__icontains=search)
                | Q(model__icontains=search)
                | Q(version__icontains=search)
                | Q(color__icontains=search)
                | Q(vin__icontains=search)
                | Q(steering_type__icontains=search)
                | Q(transmission_type__icontains=search)
                | Q(fipe_brand_code__icontains=search)
                | Q(fipe_model_code__icontains=search)
                | Q(fipe_year_code__icontains=search)
                | Q(customer__first_name__icontains=search)
                | Q(customer__last_name__icontains=search)
                | Q(customer__trade_name__icontains=search)
                | Q(customer__document_number__icontains=search)
                | Q(customer__email__icontains=search)
                | Q(customer__phone_e164__icontains=search)
                | Q(customer__secondary_phone_e164__icontains=search)
                | Q(customer__zip_code__icontains=search)
                | Q(customer__address_line__icontains=search)
                | Q(customer__address_number__icontains=search)
                | Q(customer__address_complement__icontains=search)
                | Q(customer__district__icontains=search)
                | Q(customer__city__icontains=search)
                | Q(customer__state__icontains=search)
            )
            if search_digits:
                query |= Q(plate__icontains=search_digits) | Q(customer__document_number__icontains=search_digits) | Q(customer__phone_e164__icontains=search_digits) | Q(customer__secondary_phone_e164__icontains=search_digits)
                try:
                    numeric_search = int(search_digits)
                    query |= Q(year=numeric_search) | Q(odometer_km=numeric_search) | Q(door_count=numeric_search)
                except ValueError:
                    pass
            qs = qs.filter(query)
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if active in {"true", "false"}:
            qs = qs.filter(is_active=(active == "true"))
        return qs

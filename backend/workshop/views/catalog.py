from .common import *


class GeneralCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = GeneralCategorySerializer
    permission_classes = [HasViewPermission]
    permission_code_map = {"read": "categories.view", "write": "categories.manage"}
    queryset = GeneralCategory.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        category_type = self.request.query_params.get("type")
        active = self.request.query_params.get("active")
        if search:
            qs = qs.filter(Q(code__icontains=search) | Q(name__icontains=search) | Q(description__icontains=search))
        if category_type:
            qs = qs.filter(type=category_type)
        if active in {"true", "false"}:
            qs = qs.filter(is_active=(active == "true"))
        return qs

class PartBrandViewSet(viewsets.ModelViewSet):
    serializer_class = PartBrandSerializer
    permission_classes = [HasViewPermission]
    permission_code_map = {"read": "parts.view", "write": "parts.manage"}
    queryset = PartBrand.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        active = self.request.query_params.get("active")
        if search:
            normalized_search = normalize_lookup_name(search)
            qs = qs.filter(Q(name__icontains=search) | Q(normalized_name__icontains=normalized_search))
        if active in {"true", "false"}:
            qs = qs.filter(is_active=(active == "true"))
        return qs.distinct()

class FipeLookupView(APIView):
    permission_classes = [HasViewPermission]
    permission_code = "vehicles.manage"
    base_url = "https://parallelum.com.br/fipe/api/v1"
    valid_vehicle_types = {"carros", "motos", "caminhoes"}

    def _get_json(self, path):
        try:
            response = requests.get(f"{self.base_url}/{path.lstrip('/')}", timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            return Response({"detail": "Falha ao consultar a API FIPE da Parallelum.", "error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(response.json())

    def get(self, request, resource):
        vehicle_type = request.query_params.get("vehicle_type", "carros")
        if vehicle_type not in self.valid_vehicle_types:
            raise ValidationError({"vehicle_type": "Use carros, motos ou caminhoes."})
        brand_code = request.query_params.get("brand_code")
        model_code = request.query_params.get("model_code")
        year_code = request.query_params.get("year_code")

        if resource == "brands":
            return self._get_json(f"{vehicle_type}/marcas")
        if resource == "models":
            if not brand_code:
                raise ValidationError({"brand_code": "Informe a marca."})
            return self._get_json(f"{vehicle_type}/marcas/{brand_code}/modelos")
        if resource == "years":
            if not brand_code or not model_code:
                raise ValidationError({"brand_code": "Informe a marca.", "model_code": "Informe o modelo."})
            return self._get_json(f"{vehicle_type}/marcas/{brand_code}/modelos/{model_code}/anos")
        if resource == "detail":
            if not brand_code or not model_code or not year_code:
                raise ValidationError({"brand_code": "Informe a marca.", "model_code": "Informe o modelo.", "year_code": "Informe o ano."})
            return self._get_json(f"{vehicle_type}/marcas/{brand_code}/modelos/{model_code}/anos/{year_code}")
        raise ValidationError({"resource": "Use brands, models, years ou detail."})


class CepLookupView(APIView):
    permission_classes = [HasViewPermission]
    permission_code = ["contacts.manage", "suppliers.manage", "settings.manage", "users.manage"]

    def get(self, request):
        cep = request.query_params.get("cep", "")
        digits = "".join(ch for ch in cep if ch.isdigit())
        if len(digits) != 8:
            raise ValidationError({"cep": "Informe um CEP com 8 dígitos."})
        try:
            response = requests.get(f"https://viacep.com.br/ws/{digits}/json/", timeout=8)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            return Response({"detail": "Falha ao consultar o CEP na base ViaCEP.", "error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError:
            return Response({"detail": "Resposta inválida recebida da base ViaCEP."}, status=status.HTTP_502_BAD_GATEWAY)
        if data.get("erro"):
            raise ValidationError({"cep": "CEP não encontrado na base ViaCEP."})
        formatted = data.get("cep") or f"{digits[:5]}-{digits[5:]}"
        return Response({
            "zip_code": formatted,
            "address_line": data.get("logradouro") or "",
            "district": data.get("bairro") or "",
            "city": data.get("localidade") or "",
            "state": data.get("uf") or "",
            "country": "Brasil",
        })


class WorkshopServiceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkshopServiceSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    permission_classes = [HasViewPermission]
    permission_code_map = {"read": "services.view", "write": "services.manage"}
    queryset = WorkshopService.objects.select_related("category").all()

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        category_id = self.request.query_params.get("category")
        active = self.request.query_params.get("active")
        ordering = self.request.query_params.get("ordering")
        qs = qs.annotate(usage_count=Count("work_order_lines", distinct=True))
        if search:
            qs = qs.filter(
                Q(code__icontains=search)
                | Q(name__icontains=search)
                | Q(category__code__icontains=search)
                | Q(category__name__icontains=search)
                | Q(legacy_category_name__icontains=search)
                | Q(description__icontains=search)
                | Q(default_unit_price__icontains=search)
                | Q(estimated_hours__icontains=search)
            )
        if category_id:
            qs = qs.filter(category_id=category_id)
        if active in {"true", "false"}:
            qs = qs.filter(is_active=(active == "true"))
        if ordering == "most_used":
            return qs.order_by("-is_featured", "-usage_count", "category__name", "name")
        return qs

    @action(detail=False, methods=["get"], url_path="next-code")
    def next_code(self, request):
        return Response({"code": WorkshopService.generate_code()})

class ServicePackageViewSet(viewsets.ModelViewSet):
    serializer_class = ServicePackageSerializer
    permission_classes = [HasViewPermission]
    permission_code_map = {"read": "service_packages.view", "write": "service_packages.manage"}
    queryset = ServicePackage.objects.prefetch_related("items__service").all()

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        active = self.request.query_params.get("active")
        if search:
            qs = qs.filter(
                Q(code__icontains=search)
                | Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(items__description__icontains=search)
                | Q(items__service__code__icontains=search)
                | Q(items__service__name__icontains=search)
                | Q(items__service__category__name__icontains=search)
                | Q(items__service__legacy_category_name__icontains=search)
                | Q(items__quantity__icontains=search)
                | Q(items__unit_price__icontains=search)
                | Q(discount_amount__icontains=search)
            )
        if active in {"true", "false"}:
            qs = qs.filter(is_active=(active == "true"))
        return qs.distinct()

    @action(detail=False, methods=["get"], url_path="next-code")
    def next_code(self, request):
        return Response({"code": ServicePackage.generate_code()})

class PartViewSet(viewsets.ModelViewSet):
    serializer_class = PartSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    permission_classes = [HasViewPermission]
    permission_code_map = {"read": "parts.view", "write": "parts.manage", "adjust_stock": "stock.adjust"}
    queryset = Part.objects.select_related("category").all()

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        category_id = self.request.query_params.get("category")
        low_stock = self.request.query_params.get("low_stock")
        active = self.request.query_params.get("active")
        ordering = self.request.query_params.get("ordering")
        qs = qs.annotate(usage_count=Count("work_order_lines", distinct=True))
        if search:
            qs = qs.filter(Q(sku__icontains=search) | Q(name__icontains=search) | Q(brand__icontains=search) | Q(category__name__icontains=search))
        if category_id:
            qs = qs.filter(category_id=category_id)
        if low_stock == "true":
            qs = qs.filter(stock_quantity__lte=F("minimum_stock"))
        if active in {"true", "false"}:
            qs = qs.filter(is_active=(active == "true"))
        if ordering == "most_used":
            return qs.order_by("-is_featured", "-usage_count", "category__name", "name", "sku")
        return qs

    @action(detail=True, methods=["post"])
    def adjust_stock(self, request, pk=None):
        part = self.get_object()
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        movement = adjust_part_stock(part, quantity=data["quantity"], movement_type=data["movement_type"], actor=request.user, notes=data.get("notes", ""), unit_cost=data.get("unit_cost"))
        part.refresh_from_db()
        return Response({"part": PartSerializer(part).data, "movement": PartStockMovementSerializer(movement).data})

class PartStockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PartStockMovementSerializer
    permission_classes = [HasViewPermission]
    permission_code = "stock.view"
    queryset = PartStockMovement.objects.select_related("part", "work_order", "actor").all()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("part"):
            qs = qs.filter(part_id=self.request.query_params["part"])
        if self.request.query_params.get("work_order"):
            qs = qs.filter(work_order_id=self.request.query_params["work_order"])
        return qs


class ServiceDefaultPartViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceDefaultPartSerializer
    permission_classes = [HasViewPermission]
    permission_code_map = {"read": "services.view", "write": "services.manage"}
    queryset = ServiceDefaultPart.objects.select_related("service", "part").all()

    def get_queryset(self):
        qs = super().get_queryset()
        service_id = self.request.query_params.get("service")
        active = self.request.query_params.get("active")
        if service_id:
            qs = qs.filter(service_id=service_id)
        if active in {"true", "false"}:
            qs = qs.filter(is_active=(active == "true"))
        return qs


class WorkshopServiceChecklistTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = WorkshopServiceChecklistTemplateSerializer
    permission_classes = [HasViewPermission]
    permission_code_map = {"read": "services.view", "write": "services.manage"}
    queryset = WorkshopServiceChecklistTemplate.objects.select_related("service").all()

    def get_queryset(self):
        qs = super().get_queryset()
        service_id = self.request.query_params.get("service")
        active = self.request.query_params.get("active")
        if service_id:
            qs = qs.filter(service_id=service_id)
        if active in {"true", "false"}:
            qs = qs.filter(is_active=(active == "true"))
        return qs.order_by("service_id", "sort_order", "id")

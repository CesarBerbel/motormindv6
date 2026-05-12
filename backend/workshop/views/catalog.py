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
        except requests.RequestException:
            return Response({"detail": "Não foi possível consultar o CEP agora. Verifique sua conexão e tente novamente."}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError:
            return Response({"detail": "A consulta de CEP retornou uma resposta inválida. Tente novamente."}, status=status.HTTP_502_BAD_GATEWAY)
        if data.get("erro"):
            return Response({"detail": "Não encontrei esse CEP. Confira os 8 dígitos ou preencha o endereço manualmente."}, status=status.HTTP_404_NOT_FOUND)
        formatted = data.get("cep") or f"{digits[:5]}-{digits[5:]}"
        return Response({
            "zip_code": formatted,
            "address_line": data.get("logradouro") or "",
            "district": data.get("bairro") or "",
            "city": data.get("localidade") or "",
            "state": data.get("uf") or "",
            "country": "Brasil",
        })


class CnpjLookupView(APIView):
    permission_classes = [HasViewPermission]
    permission_code = ["contacts.manage", "suppliers.manage"]

    def get(self, request):
        cnpj = request.query_params.get("cnpj", "")
        digits = "".join(ch for ch in cnpj if ch.isdigit())
        if len(digits) != 14:
            raise ValidationError({"cnpj": "Informe um CNPJ com 14 dígitos."})
        try:
            response = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{digits}", timeout=10)
        except requests.RequestException:
            return Response({"detail": "Não foi possível consultar o CNPJ na BrasilAPI agora. Tente novamente ou preencha os dados manualmente."}, status=status.HTTP_502_BAD_GATEWAY)
        if response.status_code == 404:
            return Response({"detail": "Não encontrei esse CNPJ na BrasilAPI. Confira os 14 dígitos ou preencha os dados manualmente."}, status=status.HTTP_404_NOT_FOUND)
        if response.status_code == 400:
            return Response({"detail": "CNPJ inválido ou mal formatado para consulta na BrasilAPI."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            return Response({"detail": "A BrasilAPI não respondeu como esperado. Tente novamente em instantes."}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError:
            return Response({"detail": "A consulta de CNPJ retornou uma resposta inválida. Tente novamente."}, status=status.HTTP_502_BAD_GATEWAY)

        cep = "".join(ch for ch in str(data.get("cep") or "") if ch.isdigit())
        formatted_cep = f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cep
        phone_digits = "".join(ch for ch in str(data.get("ddd_telefone_1") or "") if ch.isdigit())
        phone = f"+55{phone_digits}" if len(phone_digits) in (10, 11) else ""
        return Response({
            "document": f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}",
            "name": data.get("razao_social") or "",
            "trade_name": data.get("nome_fantasia") or "",
            "birth_date": data.get("data_inicio_atividade") or None,
            "email": (data.get("email") or "").strip().lower(),
            "phone": phone,
            "zip_code": formatted_cep,
            "address_line": data.get("logradouro") or "",
            "address_number": data.get("numero") or "",
            "address_complement": data.get("complemento") or "",
            "district": data.get("bairro") or "",
            "city": data.get("municipio") or "",
            "state": data.get("uf") or "",
            "country": "Brasil",
            "registration_status": data.get("descricao_situacao_cadastral") or "",
            "main_activity": data.get("cnae_fiscal_descricao") or "",
            "legal_nature": data.get("natureza_juridica") or "",
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

    @action(detail=False, methods=["get"], url_path="next-sku")
    def next_sku(self, request):
        return Response({"sku": Part.generate_sku()})

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

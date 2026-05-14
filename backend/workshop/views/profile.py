from .common import *


class WorkshopProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        profile = WorkshopProfile.get_solo()
        return Response(WorkshopProfileSerializer(profile, context={"request": request}).data)

    def put(self, request):
        if not user_has_permission(request.user, "settings.manage"):
            raise PermissionDenied("Você não tem permissão para alterar o cadastro da oficina.")
        profile = WorkshopProfile.get_solo()
        data = request.data.copy()
        if data.get("remove_logo") in {"true", "1", "yes"}:
            profile.logo.delete(save=False)
            data.pop("logo", None)
        data.pop("remove_logo", None)
        serializer = WorkshopProfileSerializer(profile, data=data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request):
        return self.put(request)

class BottomNavigationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = BottomNavigationItem.objects.filter(is_active=True).order_by("position", "label")
        visible_items = []
        for item in items:
            permission_codes = item.permission_codes
            if not permission_codes or any(user_has_permission(request.user, code) for code in permission_codes):
                visible_items.append(item)
        serializer = BottomNavigationItemSerializer(visible_items, many=True, context={"request": request})
        return Response(serializer.data)


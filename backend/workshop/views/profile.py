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

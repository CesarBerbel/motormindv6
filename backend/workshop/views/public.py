from .common import *


class PublicLandingView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "public_landing"

    def get(self, request):
        profile = WorkshopProfile.get_solo()
        data = PublicLandingSerializer(profile, context={"request": request}).data
        if not profile.landing_enabled:
            data["landing_enabled"] = False
        return Response(data)

class CustomerApprovalPublicView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "public_approval"

    def get_object(self, token):
        return WorkOrderCustomerApproval.objects.select_related("work_order__customer", "work_order__vehicle", "requested_by").prefetch_related("work_order__services", "work_order__parts__part", "work_order__payments").get(token=token, is_active=True)

    def get(self, request, token):
        try:
            approval = self.get_object(token)
        except WorkOrderCustomerApproval.DoesNotExist:
            return Response({"detail": "Link de aprovação não encontrado ou indisponível."}, status=status.HTTP_404_NOT_FOUND)
        return Response(WorkOrderCustomerApprovalPublicSerializer(approval).data)

    def post(self, request, token):
        try:
            approval = self.get_object(token)
        except WorkOrderCustomerApproval.DoesNotExist:
            return Response({"detail": "Link de aprovação não encontrado ou indisponível."}, status=status.HTTP_404_NOT_FOUND)
        serializer = WorkOrderCustomerApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            approval.mark_decision(
                serializer.validated_data["decision"],
                name=serializer.validated_data.get("name", ""),
                document=serializer.validated_data.get("document", ""),
                notes=serializer.validated_data.get("notes", ""),
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except DjangoValidationError as exc:
            raise drf_validation_from_django(exc) from exc
        event_type = WorkOrderEvent.EventType.UPDATED
        decision_label = "aprovou" if approval.status == WorkOrderCustomerApproval.Status.APPROVED else "recusou"
        record_event(
            approval.work_order,
            event_type,
            description=f"Cliente {decision_label} digitalmente o documento {approval.document_type_label}.",
            data={"approval_id": approval.id, "token": str(approval.token), "decision": approval.status, "decision_name": approval.decision_name},
        )
        target_status = WorkOrder.Status.OPEN if approval.status == WorkOrderCustomerApproval.Status.APPROVED else WorkOrder.Status.COMPLETED
        try:
            change_work_order_status(
                approval.work_order,
                target_status,
                actor=None,
                note=serializer.validated_data.get("notes", ""),
                send_notifications=True,
                source=SOURCE_SYSTEM,
            )
        except DjangoValidationError as exc:
            raise drf_validation_from_django(exc) from exc
        approval.refresh_from_db()
        approval.work_order.refresh_from_db()
        return Response(WorkOrderCustomerApprovalPublicSerializer(approval).data)

class CustomerApprovalPdfView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "public_approval"

    def get(self, request, token):
        try:
            approval = WorkOrderCustomerApproval.objects.select_related("work_order__customer", "work_order__vehicle").prefetch_related("work_order__services", "work_order__parts__part", "work_order__payments").get(token=token, is_active=True)
        except WorkOrderCustomerApproval.DoesNotExist:
            return Response({"detail": "Link de aprovação não encontrado ou indisponível."}, status=status.HTTP_404_NOT_FOUND)
        return pdf_response(approval.work_order, approval.document_type)

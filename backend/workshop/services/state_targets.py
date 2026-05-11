from ..models import WorkOrder


TECHNICAL_START_TARGETS = {
    WorkOrder.Status.OPEN: WorkOrder.Status.IN_PROGRESS,
    WorkOrder.Status.WAITING_PARTS: WorkOrder.Status.IN_PROGRESS,
}

TECHNICAL_COMPLETE_TARGETS = {
    WorkOrder.Status.IN_PROGRESS: WorkOrder.Status.COMPLETED,
    WorkOrder.Status.WAITING_PARTS: WorkOrder.Status.COMPLETED,
}

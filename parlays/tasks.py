from celery import shared_task

from .models import OCRUpload
from .services.ocr import OCRService
from .utils import clear_expired_host_codes


@shared_task
def clear_expired_host_codes_task():
    return {"cleared": clear_expired_host_codes()}


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def process_ocr_upload(self, upload_id: str):
    try:
        upload = OCRUpload.objects.get(pk=upload_id)
    except OCRUpload.DoesNotExist:
        return {"error": "upload not found"}

    parsed = OCRService.process_upload(upload)
    return {
        "upload_id": str(upload.id),
        "status": upload.status,
        "parsed": parsed,
    }

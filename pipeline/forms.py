from pathlib import PurePosixPath
from uuid import UUID

from django import forms
from django.conf import settings


class MessageUploadForm(forms.Form):
    delivery_id = forms.UUIDField(widget=forms.HiddenInput)
    message = forms.FileField(label="Письмо EML/MSG")

    def clean_message(self):
        upload = self.cleaned_data["message"]
        if PurePosixPath(upload.name).suffix.lower() not in {".eml", ".msg"}:
            raise forms.ValidationError("Разрешены только EML и MSG.")
        if not 0 < upload.size <= settings.MICE_MAX_MESSAGE_BYTES:
            raise forms.ValidationError("Превышен размер письма или файл пуст.")
        return upload

    def source_key(self, user_id):
        # Retries of the same browser submission retain delivery identity;
        # another explicit upload creates a distinct delivery event.
        delivery_id = UUID(str(self.cleaned_data["delivery_id"]))
        return f"upload:{user_id}:{delivery_id}"
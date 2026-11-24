from pathlib import PurePosixPath
from uuid import UUID

from django import forms
from django.conf import settings


class MultipleMailInput(forms.FileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        if not hasattr(files, "getlist"):
            return files.get(name)
        return super().value_from_datadict(data, files, name)


class MailFilesField(forms.FileField):
    widget = MultipleMailInput(attrs={"accept": ".eml,.msg,.zip"})

    def clean(self, data, initial=None):
        uploads = data if isinstance(data, (tuple, list)) else [data] if data else []
        if not uploads:
            raise forms.ValidationError("Выберите хотя бы один файл.")
        if len(uploads) > min(settings.DATA_UPLOAD_MAX_NUMBER_FILES or 100, settings.MICE_IMPORT_MAX_OBJECTS):
            raise forms.ValidationError("Слишком много файлов в одном запросе.")
        if sum(item.size for item in uploads) > settings.MICE_MAX_MESSAGE_BYTES:
            raise forms.ValidationError("Суммарный размер файлов превышает лимит загрузки.")
        results = []
        for upload in uploads:
            try:
                super().clean(upload)
                if PurePosixPath(upload.name).suffix.lower() not in {".eml", ".msg", ".zip"}:
                    raise forms.ValidationError("Разрешены только EML, MSG и ZIP.")
                if not 0 < upload.size <= settings.MICE_MAX_MESSAGE_BYTES:
                    raise forms.ValidationError("Файл пуст или превышает лимит размера.")
            except forms.ValidationError as error:
                results.append((upload, " ".join(error.messages)))
            else:
                results.append((upload, ""))
        if all(error for _, error in results):
            raise forms.ValidationError([f"{file.name}: {error}" for file, error in results])
        return results


class MessageUploadForm(forms.Form):
    delivery_id = forms.UUIDField(widget=forms.HiddenInput)
    message = MailFilesField(label="Письма EML/MSG и ZIP с письмами")

    def source_key(self, user_id, index=None):
        delivery_id = UUID(str(self.cleaned_data["delivery_id"]))
        key = f"upload:{user_id}:{delivery_id}"
        return key if index is None else f"{key}:{index}"

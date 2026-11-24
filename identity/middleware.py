from django.contrib.auth import logout


class AccessVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and request.session.get("mice_access_version") != request.user.access_version
        ):
            logout(request)
        return self.get_response(request)

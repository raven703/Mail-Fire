class PrivateResponseMiddleware:
    """Authenticated pages and evidence must not survive in shared/browser caches."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(getattr(request, "user", None), "is_authenticated", False):
            response["Cache-Control"] = "no-store, private"
            response["Pragma"] = "no-cache"
        return response
class PrivateResponseMiddleware:
    """Authenticated pages and evidence must not survive in shared/browser caches."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.headers.get("HX-Request") == "true" and response.status_code == 302:
            # Login/logout redirects must replace the whole shell, not just its
            # content (which would retain stale authenticated navigation).
            location = response.get("Location", "")
            if location in {"/", "/logout/"}:
                response.status_code = 200
                response["HX-Redirect"] = location
        if getattr(getattr(request, "user", None), "is_authenticated", False):
            response["Cache-Control"] = "no-store, private"
            response["Pragma"] = "no-cache"
        return response
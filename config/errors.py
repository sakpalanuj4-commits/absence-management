from django.shortcuts import render


def permission_denied(request, exception=None):
    return render(
        request,
        "errors/error.html",
        {
            "code": 403,
            "title": "Access denied",
            "message": str(exception) or "You do not have access to this page.",
        },
        status=403,
    )


def page_not_found(request, exception=None):
    return render(
        request,
        "errors/error.html",
        {
            "code": 404,
            "title": "Page not found",
            "message": "The page you asked for does not exist.",
        },
        status=404,
    )

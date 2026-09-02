import re
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.views import View
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok", "service": "earn-study-api"})


# --- Frontend --------------------------------------------------------------
# ``next build`` writes one HTML document per route. A dynamic route gets a
# single shell (see web/src/app/study/[publicId]/page.tsx), so every
# participant URL maps onto the same document and the client reads the real
# public_id from window.location. The React Server Component payloads (.txt)
# are deliberately left to 404 so Next falls back to a normal page load.
SPA_DYNAMIC_ROUTES = (
    (re.compile(r"^study/(?!.*\.txt$)[^/]+$"), "study/_.html"),
)


class FrontendAppView(View):
    """Serve the exported Next.js documents for every non-API route."""

    def get(self, request, path=""):
        root = Path(settings.FRONTEND_DIST)
        document = self._resolve(root, path.strip("/"))
        status = 200 if document else 404
        document = document or root / "404.html"
        if not document.is_file():
            raise Http404
        response = FileResponse(
            document.open("rb"), content_type="text/html", status=status
        )
        # The documents are rewritten on every deploy; only the hashed assets
        # under /_next/static/ are safe to cache (see WHITENOISE_* settings).
        response["Cache-Control"] = "no-cache"
        return response

    @staticmethod
    def _resolve(root: Path, path: str) -> Path | None:
        if not path:
            return root / "index.html"
        if not (root / path).resolve().is_relative_to(root.resolve()):
            return None  # path traversal
        for option in (root / f"{path}.html", root / path / "index.html"):
            if option.is_file():
                return option
        for pattern, shell in SPA_DYNAMIC_ROUTES:
            if pattern.match(path):
                return root / shell
        return None

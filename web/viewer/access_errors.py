"""HTML access failures for moderator pages; API errors remain JSON."""
from fastapi import HTTPException
from fastapi.routing import APIRoute
from web.shared.common import templates


class AccessPageRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def handle(request):
            try:
                return await original(request)
            except HTTPException as error:
                if (request.method == 'GET' and request.url.path.startswith('/me/mod/')
                        and '/api/' not in request.url.path and error.status_code in (401, 403)):
                    return templates.TemplateResponse(request=request, name='viewer/unauthorized.html',
                        context={}, status_code=error.status_code, headers={'Cache-Control': 'no-store'})
                raise
        return handle

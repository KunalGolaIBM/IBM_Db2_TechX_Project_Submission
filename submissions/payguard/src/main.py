"""ASGI entry point. Legacy imports stay available for existing integrations."""
from api.app import app as app
from services.container import Services as Services, get_services as get_services
from api.models import ScreenIn as ScreenIn, PlatformCheckIn as PlatformCheckIn

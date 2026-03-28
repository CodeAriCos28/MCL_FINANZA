import requests
from decimal import Decimal
from datetime import date
from django.core.management.base import BaseCommand
from django.conf import settings
from finanzas.models import ExchangeRate


class Command(BaseCommand):
    help = "Actualiza la tasa USD -> DOP desde la API"

    def handle(self, *args, **kwargs):
        url = "https://api.exchangerate.host/live"

        params = {
            "access_key": settings.EXCHANGE_API_KEY,
            "currencies": "DOP",
            "source": "USD"
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if not data.get("success"):
                self.stdout.write(self.style.ERROR(f"❌ Error API: {data}"))
                return

            rate = Decimal(str(data["quotes"]["USDDOP"]))

            obj, created = ExchangeRate.objects.update_or_create(
                base="USD",
                target="DOP",
                date=date.today(),
                defaults={"rate": rate}
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"✅ Nueva tasa guardada: {rate}"))
            else:
                self.stdout.write(self.style.WARNING(f"♻️ Tasa actualizada: {rate}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"🔥 Error general: {str(e)}"))
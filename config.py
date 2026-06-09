import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/ecmwf"

HOURLY_VARIABLES = [
    "temperature_2m",
    "precipitation_probability",
    "rain",
    "showers",
    "wind_speed_10m"
]

DAILY_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "wind_speed_10m_max",
    "rain_sum",
    "showers_sum"
]
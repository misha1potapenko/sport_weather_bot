from datetime import datetime


async def safe_send(message, text: str):
    """
    Отправляет текст, разбивая на части, если длина превышает 4096 символов.
    Можно использовать как для Message, так и для Bot (для рассылок).
    """
    if len(text) > 4096:
        for x in range(0, len(text), 4096):
            await message.answer(text[x:x + 4096])
    else:
        await message.answer(text)



async def send_long_message(bot, chat_id: int, text: str):
    """Отправляет длинное сообщение через бота, разбивая на части."""
    if len(text) > 4096:
        for x in range(0, len(text), 4096):
            await bot.send_message(chat_id, text[x:x+4096])
    else:
        await bot.send_message(chat_id, text)


def format_hourly_forecast(data: dict, day_label: str) -> str:
    """
    Почасовой прогноз с интервалом 3 часа.
    day_label: 'сегодня' или 'завтра'.
    """
    city = data["city_info"]["name"]
    hourly = data["hourly"]
    times = hourly["time"]
    result = f"🌍 🌡️ Прогноз погоды для {city} ({day_label})\n"
    result += "Модель ECMWF IFS HRES (9 км)\nИнтервалы по 3 часа\n\n"

    for start_hour in range(0, 24, 3):
        end_hour = start_hour + 3
        temps, winds, probs, total_precip, count = [], [], [], 0.0, 0
        for i, time in enumerate(times):
            dt = datetime.fromisoformat(time)
            hour = dt.hour
            if start_hour <= hour < end_hour:
                temps.append(hourly["temperature_2m"][i])
                winds.append(hourly["wind_speed_10m"][i])
                probs.append(hourly["precipitation_probability"][i])
                rain = hourly.get("rain", [0])[i] if i < len(hourly.get("rain", [])) else 0
                showers = hourly.get("showers", [0])[i] if i < len(hourly.get("showers", [])) else 0
                total_precip += rain + showers
                count += 1
        if count == 0:
            continue
        avg_temp = sum(temps) / count
        avg_wind = sum(winds) / count
        max_prob = max(probs)
        rain_emoji = "☔ " if total_precip > 0.1 else ""
        result += f"{start_hour:02d}:00-{end_hour:02d}:00  🌡️{avg_temp:.1f}°C  💨{avg_wind:.1f} км/ч\n"
        result += f"{rain_emoji}Осадки: {total_precip:.1f} мм (вероятность {max_prob:.0f}%)\n"
        result += "------------------------\n"
    return result


def format_weekly_forecast(data: dict) -> str:
    """
    Прогноз на неделю с указанием интервалов дождя (по часам).
    """
    city = data["city_info"]["name"]
    daily = data["daily"]
    hourly = data.get("hourly", {})
    daily_times = daily["time"]

    hourly_times = hourly.get("time", [])
    hourly_rain = hourly.get("rain", [])
    hourly_showers = hourly.get("showers", [])
    hourly_prob = hourly.get("precipitation_probability", [])

    result = f"🌍 🌡️ Прогноз погоды для {city} на неделю\n"
    result += "Модель ECMWF IFS HRES\n\n"

    for i, day_time in enumerate(daily_times):
        day_date = datetime.fromisoformat(day_time)
        day_name = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][day_date.weekday()]
        temp_max = daily["temperature_2m_max"][i]
        temp_min = daily["temperature_2m_min"][i]
        wind_max = daily["wind_speed_10m_max"][i]
        rain_sum = daily.get("rain_sum", [0])[i] or 0
        showers_sum = daily.get("showers_sum", [0])[i] or 0
        total_precip_day = rain_sum + showers_sum

        # Собираем часы с осадками для этого дня
        rain_hours = []
        for j, hour_time in enumerate(hourly_times):
            if hour_time.startswith(day_time.split("T")[0]):
                rain_val = hourly_rain[j] if j < len(hourly_rain) else 0
                showers_val = hourly_showers[j] if j < len(hourly_showers) else 0
                prob_val = hourly_prob[j] if j < len(hourly_prob) else 0
                total_precip_hour = rain_val + showers_val
                if total_precip_hour > 0.1 or prob_val > 30:
                    hour_str = hour_time.split("T")[1][:5]
                    rain_hours.append((j, hour_str))

        # Группируем часы в интервалы
        intervals = []
        if rain_hours:
            current = [rain_hours[0][1]]
            for k in range(1, len(rain_hours)):
                if rain_hours[k][0] == rain_hours[k - 1][0] + 1:
                    current.append(rain_hours[k][1])
                else:
                    intervals.append(current)
                    current = [rain_hours[k][1]]
            intervals.append(current)

        if total_precip_day > 0:
            rain_emoji = "☔ "
            if intervals:
                parts = []
                for interval in intervals:
                    start = interval[0]
                    end = interval[-1]
                    if start == end:
                        parts.append(start)
                    else:
                        parts.append(f"{start}-{end}")
                rain_desc = "Дождь: " + ", ".join(parts)
            else:
                rain_desc = f"Дождь: {total_precip_day:.1f} мм (время неизвестно)"
        else:
            rain_emoji = "🌤️ "
            rain_desc = "Осадков не ожидается"

        result += f"{day_name} {day_time}\n"
        result += f"🌡️ макс: {temp_max:.1f}°C, мин: {temp_min:.1f}°C\n"
        result += f"💨 ветер макс: {wind_max:.1f} км/ч\n"
        result += f"{rain_emoji}{rain_desc}\n"
        result += "--------------------\n"

    return result
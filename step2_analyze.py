import os
import json
import time
import random
import re
from openai import OpenAI
from dotenv import load_dotenv

# Загрузка переменных окружения из .env (если есть)
load_dotenv()

CONFIG_FILE = 'config.json'
INPUT_FILE = 'filtered_profiles.json' # Или active_female_profiles.json
OUTPUT_FILE = 'analyzed_profiles.json'
TEMP_FILE = 'analyzed_profiles_temp.json'

# Лимиты
MAX_PROFILES_TO_ANALYZE = 1000  # Сколько анализировать за один прогон (безопасный лимит)
DELAY_MIN = 1  # Минимальная пауза между запросами (сек)
DELAY_MAX = 2  # Максимальная пауза

def load_config():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения конфига: {e}")
        return {}

def is_moscow_profile(profile):
    """Проверяет, является ли город профилем Москва (регистронезависимо)"""
    city_data = profile.get('city')

    if not city_data:
        return False

    city_name = ""
    if isinstance(city_data, dict):
        city_name = city_data.get('title', '')
    elif isinstance(city_data, str):
        city_name = city_data

    if not city_name:
        return False

    clean_city = city_name.lower().strip()

    # Варианты написания Москвы
    moscow_variants = ['москва', 'moscow', 'mow', 'мсk', 'г. москва', 'город москва']

    return any(variant in clean_city for variant in moscow_variants)

def get_client(config):
    """Инициализация клиента OpenAI совместимого API"""
    hf_token = os.getenv("HF_TOKEN") or config.get('hf_token')

    if not hf_token:
        raise ValueError("❌ Токен HF_TOKEN не найден ни в .env, ни в config.json")

    # Используем роутер Hugging Face
    client = OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=hf_token,
    )
    return client

def prepare_profile_text(profile):
    """Формирует текстовое описание профиля для LLM"""
    p = profile

    # Собираем интересы в одну строку
    interests = []
    if p.get('interests'): interests.append(f"Интересы: {p['interests']}")
    if p.get('activities'): interests.append(f"Деятельность: {p['activities']}")
    if p.get('music'): interests.append(f"Музыка: {p['music']}")
    if p.get('books'): interests.append(f"Книги: {p['books']}")
    if p.get('movies'): interests.append(f"Фильмы: {p['movies']}")
    if p.get('tv'): interests.append(f"ТВ: {p['tv']}")
    if p.get('quotes'): interests.append(f"Цитаты: {p['quotes']}")
    if p.get('about'): interests.append(f"О себе: {p['about']}")

    # Подписки (топ 10)
    subs = p.get('subscriptions', [])
    if isinstance(subs, list) and len(subs) > 0:
        interests.append(f"Подписки (топ): {', '.join(subs[:10])}")

    info_text = "\n".join(interests) if interests else "Информация отсутствует"

    status = p.get('status', '')
    bdate = p.get('bdate', 'не указан')

    prompt = f"""
Анализируй анкету девушки из ВКонтакте. Твоя задача — провести психометрический анализ личности на основе доступных данных (интересы, подписки, статус, цитаты).
Оцени по шкале от 1 до 10 следующие параметры:
1. Big Five: Экстраверсия, Доброжелательность, Добросовестность, Невротизм, Открытость опыту.
2. Тип юмора (самоирония, интеллект, сарказм и т.д.).
3. Потенциальная совместимость (на основе интересов).
4. Краткий вердикт: стоит ли знакомиться и почему.

ВАЖНО: Ответ должен быть ТОЛЬКО в формате валидного JSON без лишнего текста и markdown-разметки.
Структура JSON:
{{
    "scores": {{
        "extraversion": int,
        "agreeableness": int,
        "conscientiousness": int,
        "neuroticism": int,
        "openness": int
    }},
    "humor_type": "string",
    "compatibility_score": int,
    "verdict": "string (кратко, 1-2 предложения)",
    "tags": ["tag1", "tag2"]
}}

ДАННЫЕ ПРОФИЛЯ:
Имя: {p.get('first_name')} {p.get('last_name')}
Дата рождения: {bdate}
Статус: {status}
Город: {p.get('city', {}).get('title') if isinstance(p.get('city'), dict) else p.get('city')}
---
{info_text}
---
Начинай ответ сразу с {{.
"""
    return prompt

def analyze_profile(client, profile):
    """Отправляет запрос к LLM и парсит ответ"""
    prompt = prepare_profile_text(profile)

    try:
        completion = client.chat.completions.create(
            model="Qwen/Qwen2.5-Coder-32B-Instruct", # Более надежная модель для JSON
            messages=[
                {"role": "system", "content": "Ты профессиональный психолог и аналитик данных. Твоя задача — выдавать строго валидный JSON объект."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )

        raw_response = completion.choices[0].message.content

        # Очистка от markdown разметки, если она есть
        cleaned_response = raw_response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()

        # Попытка парсинга JSON
        try:
            result_json = json.loads(cleaned_response)
            return True, result_json
        except json.JSONDecodeError as je:
            print(f"   ⚠️ ОШИБКА ПАРСИНГА JSON:")
            print(f"   --- Сырой ответ сервера (первые 1000 символов): ---")
            print(raw_response[:1000])
            print(f"   --- Конец ответа ---")
            print(f"   Детали ошибки JSON: {str(je)}")
            return False, {"error": "JSON parse failed", "raw": raw_response[:500]}

    except Exception as e:
        # Ловим любые ошибки сети или API
        error_type = type(e).__name__
        error_msg = str(e)

        print(f"   ❌ КРИТИЧЕСКАЯ ОШИБКА ЗАПРОСА ({error_type}): {error_msg}")

        # Если это объект ошибки с атрибутами (как у openai)
        if hasattr(e, 'response'):
            try:
                resp_text = e.response.text
                print(f"   --- Тело ответа API: ---")
                print(resp_text[:1000])
                print(f"   --- Конец тела ответа ---")
            except:
                pass

        return False, {"error": f"{error_type}: {error_msg}"}

def main():
    print("="*60)
    print("ШАГ 2: Психометрический анализ профилей (Москва)")
    print("="*60)

    config = load_config()

    # Загрузка профилей
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Файл {INPUT_FILE} не найден.")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        all_profiles = json.load(f)

    print(f"Загружено всего профилей: {len(all_profiles)}")

    # Фильтрация по Москве
    moscow_profiles = [p for p in all_profiles if is_moscow_profile(p)]
    print(f"Профилей из Москвы: {len(moscow_profiles)}")

    if not moscow_profiles:
        print("❌ Нет профилей из Москвы для анализа. Проверьте поле 'city' в исходном файле.")
        return

    # Загрузка уже проанализированных (чтобы не дублировать)
    analyzed_ids = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                analyzed_ids = {item['id'] for item in existing_data}
                print(f"Найдено ранее проанализированных: {len(existing_data)}")
        except:
            pass

    # Отбор новых для анализа
    to_analyze = [p for p in moscow_profiles if p['id'] not in analyzed_ids]

    if not to_analyze:
        print("✅ Все московские профили уже проанализированы.")
        return

    # Ограничение количества
    to_analyze = to_analyze[:MAX_PROFILES_TO_ANALYZE]
    print(f"Начинаем анализ {len(to_analyze)} новых профилей (лимит на этот запуск)...")

    # Инициализация клиента
    try:
        client = get_client(config)
        print("✅ LLM клиент инициализирован")
    except Exception as e:
        print(f"❌ Ошибка инициализации клиента: {e}")
        return

    results = []

    # Чтение существующих результатов для дозаписи
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                results = json.load(f)
        except:
            results = []

    for i, profile in enumerate(to_analyze):
        name = profile.get('first_name', 'Unknown')
        pid = profile.get('id')

        print(f"\n[{i+1}/{len(to_analyze)}] Анализ профиля {pid} ({name})...")

        success, data = analyze_profile(client, profile)

        if success:
            print(f"   ✅ Успешно")
            entry = {
                "id": pid,
                "first_name": name,
                "last_name": profile.get('last_name', ''),
                "analysis": data,
                "city": profile.get('city')
            }
            results.append(entry)
        else:
            print(f"   ✗ Ошибка анализа (см. лог выше)")
            # Можно сохранить и ошибку, чтобы не пытаться снова, если нужно
            # entry = {"id": pid, "error": data.get('error')}
            # results.append(entry)

        # Сохранение промежуточного результата после каждого профиля
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        # Пауза
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        time.sleep(delay)

    print(f"\n💾 Готово. Результаты сохранены в {OUTPUT_FILE}")
    print(f"Всего проанализировано в этом сеансе: {len(to_analyze)}")

if __name__ == '__main__':
    main()

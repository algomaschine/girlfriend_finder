import vk_api
import json
import os
import time
import random
import re
import subprocess
import sys
from datetime import datetime
from tqdm import tqdm

# --- Конфигурация ---
CONFIG_FILE = 'config.json'
RAW_OUTPUT_FILE = 'raw_profiles_collected.json' # Сырая база всех подходящих
FINAL_OUTPUT_FILE = 'analyzed_profiles_live.json' # База с анализом и сообщениями
MODEL_NAME = "qwen2.5:1.5b" # Модель помощнее для сложного анализа (0.5b может не справиться с нюансами юмора)
OLLAMA_URL = "http://localhost:11434"

# Лимиты
MIN_BIRTH_YEAR = 1985
MAX_PROFILES_PER_RUN = 0 # 0 = без лимита, обрабатывать все новые

def load_config():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения конфига: {e}")
        sys.exit(1)

def init_vk(token):
    vk = vk_api.VkApi(token=token)
    try:
        vk.method('users.get', {'user_ids': 'me'})
        return vk
    except Exception as e:
        print(f"❌ Ошибка авторизации VK: {e}")
        sys.exit(1)

def check_ollama():
    """Проверка и запуск Ollama + модели"""
    print("🔍 Проверка Ollama...")
    try:
        import requests
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        if r.status_code == 200:
            models = [m['name'] for m in r.json().get('models', [])]
            if not any(MODEL_NAME in m for m in models):
                print(f"⬇️ Скачивание модели {MODEL_NAME} (это нужно один раз)...")
                subprocess.run(["ollama", "pull", MODEL_NAME], check=True)
                print("✅ Модель готова.")
            else:
                print(f"✅ Модель {MODEL_NAME} найдена.")
        else:
            raise Exception("Server error")
    except Exception:
        print("⚙️ Запуск сервера Ollama...")
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4)
        print("✅ Сервер запущен.")

def parse_bdate(bdate_str):
    """Извлекает год из даты рождения (форматы: DD.MM.YYYY или DD.MM)"""
    if not bdate_str:
        return None
    try:
        parts = bdate_str.split('.')
        if len(parts) == 3:
            return int(parts[2])
        elif len(parts) == 2:
            # Если года нет, считаем что человек молодой (или пропускаем, если критично)
            # Но по ТЗ нужен год >= 1985. Если года нет, мы не можем проверить.
            # Обычно ВК скрывает год, если настройки приватности.
            # Пропустим такие профили, так как не можем подтвердить возраст.
            return None
    except:
        return None
    return None

def is_moscow(city_data):
    if not city_data:
        return False
    if isinstance(city_data, dict):
        title = city_data.get('title', '')
    else:
        title = str(city_data)
    return title.lower() in ['москва', 'moscow', 'msk', 'мск']

def get_profile_subscriptions(vk, user_id):
    """Получает подписки (группы) для анализа интересов"""
    try:
        subs = vk.method('groups.get', {'user_id': user_id, 'count': 50, 'extended': 0})
        return [g['name'] for g in subs.get('items', [])]
    except vk_api.exceptions.ApiError as e:
        if e.code == 6: # Too many requests
            time.sleep(1)
            return get_profile_subscriptions(vk, user_id)
        return [] # Приватный профиль или ошибки
    except:
        return []

# --- ПРОМПТЫ ДЛЯ АНАЛИЗА (Scientific Approach) ---

SYSTEM_PROMPT = """Ты — эксперт-психолог, специализирующийся на совместимости отношений и модели "Большой пятерки" (Big Five).
Твоя задача: проанализировать анкету девушки и оценить её соответствие запросу мужчины с "веселым нравом", который ценит прямолинейность, юмор и активность.

НАУЧНЫЕ КРИТЕРИИ ОЦЕНКИ:
1. Big Five (Оценивать по шкале 0-100):
   - Extraversion (Экстраверсия): Должна быть ВЫСОКОЙ (>70). Ищем общительность, энергию, жизнерадостность.
   - Neuroticism (Нейротизм): Должен быть НИЗКИМ (<40). Ищем эмоциональную стабильность, отсутствие тревожности/драмы.
   - Conscientiousness (Добросовестность): Средняя или Высокая. Надежность.
   - Openness (Открытость): Высокая. Готовность к новому, творчеству.
   - Agreeableness (Доброжелательность): Средняя или Высокая.

2. Стиль Юмора (Критически важно):
   - Affiliative (Аффилиативный): Юмор для сближения, шуток в компании. (ПЛЮС)
   - Self-enhancing (Самоирония/Поддерживающий): Умение посмеяться над собой. (ПЛЮС)
   - Aggressive (Агрессивный): Сарказм, насмешки, злой юмор. (МИНУС/RED FLAG)
   - Self-defeating (Самоуничижительный): Чрезмерная жертвенность ради шутки. (НЕЙТРАЛЬНО/МИНУС)

3. Совместимость (Compatibility Score 0-100):
   - Высокий балл только при сочетании: Высокая Экстраверсия + Низкий Нейротизм + Адаптивный юмор.
   - Снижать балл за признаки агрессии, пассивности, депрессивности или излишней серьезности.

ФОРМАТ ОТВЕТА (СТРОГО JSON):
{
  "big_five": {
    "extraversion": int,
    "neuroticism": int,
    "conscientiousness": int,
    "openness": int,
    "agreeableness": int
  },
  "humor_analysis": {
    "dominant_style": "string (Affiliative/Self-enhancing/Aggressive/Mixed/Unknown)",
    "evidence": "string (кратко, какие подписки/текст указывают на это)"
  },
  "compatibility_score": int (0-100),
  "verdict": "string (одна фраза: стоит ли знакомиться)",
  "red_flags": ["list of strings or empty"],
  "personality_summary": "string (краткий портрет живым языком, 1 предложение)"
}
"""

USER_PROMPT_TEMPLATE = """
АНКЕТА ПОЛЬЗОВАТЕЛЯ VK:
Имя: {first_name}
Возраст: {age} (или дата рождения: {bdate})
Город: {city}
Статус: {status}
О себе: {about}
Интересы/Деятельность: {activities}
Любимая музыка/фильмы: {music_movies}
Подписки (топ-20): {subscriptions}

ЗАДАЧА:
Проведи анализ согласно системной инструкции. Особое внимание удели поиску признаков "веселого нрава" через подписки на комедийные клубы, мероприятия, юмористические паблики, активный отдых.
Если данных мало, делай осторожные выводы, но не выдумывай.
"""

def call_llm(prompt_text):
    import requests
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt_text,
        "system": SYSTEM_PROMPT,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.4} # Чуть выше температура для креативности, но строго JSON
    }
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json().get('response', '')
    except Exception as e:
        return None

def generate_message(name, analysis, profile_data):
    """Генерирует уникальное сообщение на основе анализа"""

    # Данные для контекста
    humor = analysis.get('humor_analysis', {}).get('dominant_style', '')
    score = analysis.get('compatibility_score', 0)
    interests = profile_data.get('interests', '') or profile_data.get('activities', '')

    msg_prompt = f"""
Ты — мужчина с веселым нравом, прямолинейный, харизматичный, без лишней "воды".
Твоя задача: написать короткое (2-3 предложения), цепляющее сообщение девушке {name} в VK.

Контекст о ней (из анализа ИИ):
- Психотип: {analysis.get('personality_summary', 'неизвестно')}
- Стиль юмора: {humor}
- Интересы: {interests}
- Оценка совместимости: {score}/100

ТРЕБОВАНИЯ К СООБЩЕНИЮ:
1. Начни с приветствия по имени.
2. Используй инсайт из её профиля (подписка, интерес, статус), чтобы показать внимание.
3. Тон должен соответствовать её стилю юмора:
   - Если у неё Self-enhancing/Affiliative: будь легким, немного ироничным, предложи приключение.
   - Если она серьезная, но с высоким Openness: будь искренним, предложи что-то необычное.
   - ИЗБЕГАЙ шаблонных фраз типа "как дела", "ты красивая".
   - ИЗБЕГАЙ стиля робота или ИИ. Пиши как живой человек, с эмоцией.
4. Закончи вопросом или призывом к действию, но ненавязчиво.
5. Язык: Русский.

Пример хорошего тона: "Привет, {name}! Увидел, что ты фанат [интерес]. Решил, что нам точно есть о чем поговорить, кроме погоды. Как смотришь на то, чтобы проверить, совпадает ли наше чувство юмора вживую?"

Напиши ТОЛЬКО текст сообщения, без кавычек и пояснений.
"""

    import requests
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": MODEL_NAME,
        "prompt": msg_prompt,
        "system": "Ты мастер пикапа и общения. Пишешь кратко, ёмко, с юмором и харизмой.",
        "stream": False,
        "options": {"temperature": 0.7} # Больше креатива для сообщения
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
        text = resp.json().get('response', '').strip()
        # Чистка от мусора
        text = re.sub(r'^["\']|["\']$', '', text)
        text = re.sub(r'^```|```$', '', text)
        return text
    except:
        return f"Привет, {name}! Твой профиль меня заинтриговал. Давай знакомиться!"

def analyze_single_profile(vk, profile):
    uid = profile['id']
    name = profile.get('first_name', '')
    bdate = profile.get('bdate', '')
    year = parse_bdate(bdate)

    # 1. Фильтр по году
    if year and year < MIN_BIRTH_YEAR:
        return None, f"Отклонено: год рождения {year} < {MIN_BIRTH_YEAR}"
    if not year:
        # Если года нет, можно либо пропустить, либо оставить на усмотрение.
        # По ТЗ строгий фильтр, значит пропускаем, если не можем подтвердить >= 1985.
        # Но иногда ВК скрывает год у молодых. Оставим решение: если года нет вообще - пропускаем.
        return None, "Отклонено: год рождения скрыт или не указан"

    # 2. Фильтр по городу (уже отфильтровано на этапе сбора, но перепроверим)
    if not is_moscow(profile.get('city')):
        return None, "Отклонено: не Москва"

    # 3. Сбор доп. данных (подписки)
    # Если в профиле уже есть subscriptions, используем их, иначе грузим
    subs = profile.get('subscriptions', [])
    if not subs:
        subs = get_profile_subscriptions(vk, uid)
        profile['subscriptions'] = subs # Сохраняем в профиль

    # Формирование контекста
    context = {
        'first_name': name,
        'age': profile.get('bdate', 'Н/Д'),
        'bdate': bdate,
        'city': profile.get('city', ''),
        'status': profile.get('status', ''),
        'about': profile.get('about', ''),
        'activities': profile.get('activities', ''),
        'music_movies': f"{profile.get('music', '')} {profile.get('movies', '')}",
        'subscriptions': ", ".join(subs[:20]) if subs else "Нет данных"
    }

    user_prompt = USER_PROMPT_TEMPLATE.format(**context)

    # 4. Запрос к LLM (Анализ)
    raw_json = call_llm(user_prompt)
    if not raw_json:
        return None, "Ошибка LLM: нет ответа"

    # Парсинг JSON анализа
    try:
        # Очистка от markdown
        clean_json = re.sub(r'```json\s*|\s*```', '', raw_json).strip()
        analysis = json.loads(clean_json)
    except json.JSONDecodeError:
        return None, f"Ошибка парсинга JSON анализа: {raw_json[:100]}"

    # 5. Генерация сообщения (если анализ успешен и скор высокий)
    score = analysis.get('compatibility_score', 0)
    message = ""

    # Генерируем сообщение даже для средних кандидатов, но помечаем
    if score > 40:
        message = generate_message(name, analysis, context)
    else:
        message = "Профиль проанализирован, но совместимость низкая. Сообщение не генерировалось."

    result = {
        'profile': profile,
        'analysis': analysis,
        'generated_message': message,
        'processed_at': datetime.now().isoformat()
    }

    return result, None

def main():
    print("="*60)
    print("ШАГ 1+2: Сбор -> Фильтрация -> Глубокий Анализ (Big Five + Юмор)")
    print("="*60)

    config = load_config()
    vk = init_vk(config['vk_token'])
    check_ollama()

    group_id = config.get('group_id')
    if not group_id:
        print("❌ Укажите group_id в config.json")
        sys.exit(1)

    # Загрузка уже обработанных результатов
    existing_data = []
    if os.path.exists(FINAL_OUTPUT_FILE):
        try:
            with open(FINAL_OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            print(f"📂 Найдено {len(existing_data)} уже обработанных профилей.")
        except:
            pass

    existing_ids = {item['profile']['id'] for item in existing_data}

    # Сбор новых профилей (пагинация)
    print(f"🕸️ Начало сбора участников группы {group_id}...")
    new_candidates = []
    offset = 0
    count = 100

    # Собираем пачками, сразу фильтруя по полу и городу (базово)
    while True:
        try:
            resp = vk.method('groups.getMembers', {
                'group_id': group_id,
                'offset': offset,
                'count': count,
                'fields': 'sex,city,bdate,status'
            })
            items = resp.get('items', [])
            if not items:
                break

            for p in items:
                if p['id'] in existing_ids:
                    continue
                if p.get('sex') != 1: # Только женщины
                    continue
                if not is_moscow(p.get('city')):
                    continue

                new_candidates.append(p)

            offset += count
            print(f"   ...проверено {offset} участников, найдено подходящих: {len(new_candidates)}")
            time.sleep(0.2)

        except Exception as e:
            print(f"Ошибка сбора: {e}")
            break

    if not new_candidates:
        print("✅ Нет новых кандидатов для обработки.")
        return

    print(f"🚀 Найдено {len(new_candidates)} новых кандидатов. Начинаем глубокий анализ...")

    # Обработка
    results = existing_data.copy()

    # Используем tqdm для прогресс-бара
    for p in tqdm(new_candidates, desc="Анализ профилей", unit="prof"):
        res, err = analyze_single_profile(vk, p)

        if res:
            results.append(res)
            # Автосохранение после каждого успешного
            with open(FINAL_OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        else:
            # Можно логировать ошибки, если нужно
            pass

    print("\n" + "="*60)
    print(f"✅ ГОТОВО! Всего в базе: {len(results)} профилей с анализом.")
    print(f"💾 Файл: {FINAL_OUTPUT_FILE}")

    # Вывод топ-3 для примера
    top = sorted([r for r in results if r['analysis'].get('compatibility_score', 0) > 0],
                 key=lambda x: x['analysis'].get('compatibility_score', 0), reverse=True)[:3]
    if top:
        print("\n🏆 ТОП-3 Совпадения:")
        for t in top:
            name = t['profile'].get('first_name')
            score = t['analysis'].get('compatibility_score')
            msg_preview = t['generated_message'][:50].replace('\n', ' ')
            print(f"- {name}: Скор {score}. Сообщение: {msg_preview}...")

if __name__ == '__main__':
    main()

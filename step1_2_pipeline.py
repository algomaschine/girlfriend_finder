import vk_api
import json
import os
import time
import random
import re
import subprocess
import sys
from datetime import datetime, timedelta
from tqdm import tqdm
import plotext as plt

# --- Конфигурация ---
CONFIG_FILE = 'config.json'
RAW_OUTPUT_FILE = 'raw_profiles_collected.json'
FINAL_OUTPUT_FILE = 'analyzed_profiles_live.json'
MODEL_NAME = "qwen2.5:1.5b"
OLLAMA_URL = "http://localhost:11434"

# Лимиты
MIN_BIRTH_YEAR = 1990
MAX_PROFILES_PER_RUN = 0

def load_config():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        if 'group_ids' in config:
            group_ids_str = config['group_ids']
            config['group_ids_list'] = [gid.strip() for gid in group_ids_str.split(',')]
        elif 'group_id' in config:
            config['group_ids_list'] = [str(config['group_id'])]
        else:
            print("❌ Укажите group_ids в config.json")
            sys.exit(1)

        return config
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
    print("🔍 Проверка Ollama...")
    try:
        import requests
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        if r.status_code == 200:
            models = [m['name'] for m in r.json().get('models', [])]
            if not any(MODEL_NAME in m for m in models):
                print(f"⬇️ Скачивание модели {MODEL_NAME}...")
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
    if not bdate_str:
        return None
    try:
        parts = bdate_str.split('.')
        if len(parts) == 3:
            return int(parts[2])
        elif len(parts) == 2:
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
        if isinstance(subs, int):
             subs = vk.method('groups.get', {'user_id': user_id, 'count': 50, 'offset': 0, 'extended': 0})
        
        if isinstance(subs, dict) and 'items' in subs:
            return [g['name'] for g in subs['items']]
        return []
    except vk_api.exceptions.ApiError as e:
        if e.code == 6:
            time.sleep(1)
            return get_profile_subscriptions(vk, user_id)
        return []
    except Exception as e:
        return []

SYSTEM_PROMPT = """Ты — эксперт-психолог, специализирующийся на совместимости отношений и модели "Большая пятерка" (Big Five).
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
        "options": {"temperature": 0.4}
    }
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json().get('response', '')
    except Exception as e:
        return None

def generate_message_llm(name, analysis, profile_data):
    """Stub for LLM message generation (currently disabled)"""
    humor = analysis.get('humor_analysis', {}).get('dominant_style', '')
    score = analysis.get('compatibility_score', 0)
    interests = profile_data.get('interests', '') or profile_data.get('activities', '')

    msg_prompt = f"""
Ты — мужчина с веселым нравом, прямолинейный, харизматичный, без лишней "воды".
Напиши короткое (2-3 предложения), цепляющее сообщение девушке {name}.
Контекст: {analysis.get('personality_summary', 'неизвестно')}, Юмор: {humor}, Интересы: {interests}, Скор: {score}.
Избегай шаблонов. Пиши живо.
"""
    import requests
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": MODEL_NAME,
        "prompt": msg_prompt,
        "system": "Ты мастер пикапа и общения.",
        "stream": False,
        "options": {"temperature": 0.7}
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
        text = resp.json().get('response', '').strip()
        text = re.sub(r'^["\']|["\']$', '', text)
        text = re.sub(r'^```|```$', '', text)
        return text
    except:
        return f"Привет, {name}! Твой профиль меня заинтриговал."

def analyze_single_profile(vk, profile):
    uid = profile['id']

    # === ПРОВЕРКА 0: Получение полной информации (включая can_message) ===
    # На этапе сбора can_message может врать, поэтому проверяем точно здесь
    try:
        full_user = vk.method('users.get', {
            'user_ids': uid, 
            'fields': 'can_message,is_closed,relation,last_seen,photo_100,city,bdate,status,about,activities,music,movies,sex'
        })
        if full_user:
            user_data = full_user[0]
            # Обновляем профиль актуальными данными
            profile.update(user_data)
    except Exception as e:
        return None, f"Ошибка получения данных профиля: {e}"

    # === ПРОВЕРКА 1: Можно ли написать сообщение? (Теперь точно) ===
    if profile.get('can_message') == 0:
        return None, "Нельзя написать сообщение"

    # === ПРОВЕРКА 2: Закрытый профиль ===
    if profile.get('is_closed', False):
        return None, "Профиль закрыт"

    # === ПРОВЕРКА 3: Активность ===
    last_seen = profile.get('last_seen')
    if last_seen and 'time' in last_seen:
        last_active_time = datetime.fromtimestamp(last_seen['time'])
        days_inactive = (datetime.now() - last_active_time).days
        if days_inactive > 90:
            return None, "Профиль неактивен"

    # === ПРОВЕРКА 4: Семейное положение ===
    relation = profile.get('relation', 0)
    busy_statuses = {2: "есть друг", 3: "помолвлена", 4: "замужем", 7: "в гражданском браке", 8: "влюблена"}
    if relation in busy_statuses:
        return None, f"Статус: {busy_statuses[relation]}"

    name = profile.get('first_name', '')
    bdate = profile.get('bdate', '')
    year = parse_bdate(bdate)

    # 1. Фильтр по году
    if year and year < MIN_BIRTH_YEAR:
        return None, f"Год рождения {year} < {MIN_BIRTH_YEAR}"
    if not year:
        return None, "Год рождения скрыт"

    # 2. Фильтр по городу
    if not is_moscow(profile.get('city')):
        return None, "Не Москва"

    # 3. Сбор подписок
    subs = profile.get('subscriptions', [])
    if not subs:
        subs = get_profile_subscriptions(vk, uid)
        profile['subscriptions'] = subs

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
    raw_json = call_llm(user_prompt)
    
    if not raw_json:
        return None, "Ошибка LLM"

    try:
        clean_json = re.sub(r'```json\s*|\s*```', '', raw_json).strip()
        analysis = json.loads(clean_json)
    except json.JSONDecodeError:
        return None, f"Ошибка парсинга JSON"

    # 4. Генерация сообщения (ШАБЛОН если скор >= 90)
    score = analysis.get('compatibility_score', 0)
    message = ""

    if score >= 90:
        message = f"Привет, {name}. 👋 Мои алгоритмы (и немного магии совпадений) выделили твой профиль из сотен других как один из наиболее совместимых с моим весёлым нравом 😄 Если ты не замужем, то предлагаю познакомиться - возможно станем соулмейтами, друзьями и чем-то большим. В этом посте я рассказал немного больше о себе https://vk.com/wall758002654_43   Буду рад ответу!"
        # --- STUB FOR LLM GENERATION (Uncomment to enable) ---
        # message = generate_message_llm(name, analysis, profile)
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
    print("ШАГ 1+2: Сбор -> Фильтрация -> Глубокий Анализ")
    print("="*60)

    config = load_config()
    vk = init_vk(config['vk_token'])
    check_ollama()

    group_ids_list = config.get('group_ids_list', [])
    if not group_ids_list:
        print("❌ Укажите group_ids в config.json")
        sys.exit(1)

    existing_data = []
    if os.path.exists(FINAL_OUTPUT_FILE):
        try:
            with open(FINAL_OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            print(f"📂 Найдено {len(existing_data)} уже обработанных профилей.")
        except:
            pass

    existing_ids = {item['profile']['id'] for item in existing_data}

    print(f"🕸️ Начало сбора участников из групп: {group_ids_list}...")
    new_candidates = []
    count = 100
    
    # Stats tracking
    stats = {
        'total_checked': 0,
        'wrong_sex': 0,
        'not_moscow': 0,
        'closed_profile': 0,
        'busy_relation': 0,
        'already_processed': 0
        # cannot_message убрано отсюда, так как проверка перенесена внутрь analyze_single_profile
    }

    for group_id in group_ids_list:
        print(f"   📋 Обработка группы: {group_id}")
        offset = 0
        while True:
            try:
                # Убрали can_message из полей, так как он тут ненадежен
                resp = vk.method('groups.getMembers', {
                    'group_id': group_id,
                    'offset': offset,
                    'count': count,
                    'fields': 'sex,city,bdate,status,last_seen,relation,is_closed,photo_100'
                })
                items = resp.get('items', [])
                if not items:
                    break

                for p in items:
                    stats['total_checked'] += 1
                    
                    if p['id'] in existing_ids:
                        stats['already_processed'] += 1
                        continue
                    
                    if p.get('sex') != 1:
                        stats['wrong_sex'] += 1
                        continue
                    
                    if not is_moscow(p.get('city')):
                        stats['not_moscow'] += 1
                        continue

                    if p.get('is_closed', False):
                        stats['closed_profile'] += 1
                        continue

                    relation = p.get('relation', 0)
                    if relation in [2, 3, 4, 7, 8]:
                        stats['busy_relation'] += 1
                        continue

                    # Проверка can_message УБРАНА отсюда! Она будет внутри analyze_single_profile
                    new_candidates.append(p)

                offset += count
                
                # Print stats every 100
                if offset % 100 == 0:
                    sorted_stats = sorted([(k, v) for k, v in stats.items() if k != 'total_checked' and k != 'already_processed'], key=lambda x: x[1], reverse=True)
                    top_reasons = ", ".join([f"{k}:{v}" for k, v in sorted_stats[:3]])
                    print(f"      ...проверено {offset} участников, найдено подходящих: {len(new_candidates)}")
                    print(f"         ⚠️ Отсев: {top_reasons}")
                
                time.sleep(0.2)

            except Exception as e:
                print(f"Ошибка сбора: {e}")
                break

    if not new_candidates:
        print("✅ Нет новых кандидатов для обработки.")
        # Все равно выводим статистику перед выходом
        print_rejection_stats(stats, 0, 0)
        return

    print(f"\n🚀 Найдено {len(new_candidates)} новых кандидатов. Начинаем глубокий анализ...")
    
    results = existing_data.copy()
    analyzed_count = 0
    rejected_in_analysis = 0

    for p in tqdm(new_candidates, desc="Анализ профилей", unit="prof"):
        res, err = analyze_single_profile(vk, p)

        if res:
            results.append(res)
            analyzed_count += 1
            with open(FINAL_OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        else:
            rejected_in_analysis += 1
            # Можно добавить логирование причин отказа на этом этапе, если нужно
            # print(f"   ❌ Профиль {p['id']} отклонен на этапе анализа: {err}")

    print("\n" + "="*60)
    print(f"✅ ГОТОВО! Всего в базе: {len(results)} профилей с анализом.")
    print(f"💾 Файл: {FINAL_OUTPUT_FILE}")
    
    # Обновляем статистику для финального отчета
    stats['cannot_message_final'] = rejected_in_analysis # Грубая оценка, т.к. мы не парсим текст ошибки детально в цикле
    
    print_rejection_stats(stats, analyzed_count, len(results))

    top = sorted([r for r in results if r['analysis'].get('compatibility_score', 0) > 0],
                 key=lambda x: x['analysis'].get('compatibility_score', 0), reverse=True)[:3]
    if top:
        print("\n🏆 ТОП-3 Совпадения:")
        for t in top:
            name = t['profile'].get('first_name')
            score = t['analysis'].get('compatibility_score')
            msg_preview = t['generated_message'][:50].replace('\n', ' ')
            print(f"- {name}: Скор {score}. Сообщение: {msg_preview}...")

def print_rejection_stats(stats, analyzed_count, final_count):
    print("\n" + "="*60)
    print("📊 СТАТИСТИКА ОТСЕВА ПРОФИЛЕЙ")
    print("="*60)

    total = stats['total_checked']
    if total == 0:
        print("Нет данных для статистики.")
        return

    print(f"\n📈 Всего проверено профилей: {total}")
    print(f"✅ Прошло на LLM анализ: {analyzed_count}")
    print(f"🎯 Итоговый успех (добавлено в базу): {final_count}")
    
    success_rate = (final_count / total * 100) if total > 0 else 0
    print(f"📉 Общий процент отсева: {100 - success_rate:.1f}%")

    print("\n🔍 Детализация по причинам отсева (этап сбора):")
    print("-" * 50)
    
    # Сортировка причин
    reasons = {k: v for k, v in stats.items() if k not in ['total_checked', 'already_processed']}
    sorted_reasons = sorted(reasons.items(), key=lambda x: x[1], reverse=True)
    
    max_val = max([v for k, v in sorted_reasons]) if sorted_reasons else 1
    
    labels_plot = []
    values_plot = []

    for key, val in sorted_reasons:
        label = key.replace('_', ' ').title()
        bar_len = int((val / max_val) * 40) if max_val > 0 else 0
        bar = "█" * bar_len
        pct = (val / total * 100) if total > 0 else 0
        print(f"{label:<25} |{bar}| {val} ({pct:.1f}%)")
        labels_plot.append(label)
        values_plot.append(val)

    # Plotext Visualization (Fixed: no rotation argument)
    if labels_plot:
        print("\n📉 Визуализация (Plotext):")
        plt.clear_data()
        plt.bar(labels_plot, values_plot)
        plt.title("Причины отсева (Сбор)")
        plt.xlabel("Причина")
        plt.ylabel("Количество")
        # plt.xticks(rotation=45) <- УДАЛЕНО, так как plotext не поддерживает этот аргумент
        plt.show()
    else:
        print("Нет причин для отображения графика.")

if __name__ == '__main__':
    main()
    # Run report generator
    script_dir = os.path.dirname(os.path.abspath(__file__))
    report_script = os.path.join(script_dir, "step3_generate_report.py")
    if os.path.exists(report_script):
        subprocess.run(["python", report_script], check=True)
    else:
        print("⚠️ step3_generate_report.py not found, skipping report generation.")

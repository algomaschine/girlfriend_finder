import vk_api
import json
import os
import time
import re
import subprocess
import sys
from datetime import datetime
from tqdm import tqdm
import plotext as plt

# --- КОНФИГУРАЦИЯ ---
CONFIG_FILE = 'config.json'
FINAL_OUTPUT_FILE = 'analyzed_profiles_live.json'
STATS_FILE = 'funnel_stats.txt'
MODEL_NAME = "qwen2.5:1.5b"
OLLAMA_URL = "http://localhost:11434"

MIN_BIRTH_YEAR = 1990

def load_config():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        if 'group_ids' in config:
            config['group_ids_list'] = [gid.strip() for gid in config['group_ids'].split(',')]
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
            print(f"✅ Модель {MODEL_NAME} готова.")
        else:
            raise Exception("Server error")
    except Exception:
        print("⚙️ Запуск сервера Ollama...")
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4)
        print("✅ Сервер запущен.")

def parse_bdate(bdate_str):
    if not bdate_str: return None
    try:
        parts = bdate_str.split('.')
        if len(parts) == 3: return int(parts[2])
    except: pass
    return None

def is_moscow(city_data):
    if not city_data: return False
    title = city_data.get('title', '') if isinstance(city_data, dict) else str(city_data)
    return title.lower() in ['москва', 'moscow', 'msk', 'мск']

def get_profile_subscriptions(vk, user_id):
    try:
        subs = vk.method('groups.get', {'user_id': user_id, 'count': 50, 'extended': 0})
        if isinstance(subs, dict) and 'items' in subs:
            return [g['name'] for g in subs['items']]
        return []
    except Exception:
        return []

# --- ПРОМПТЫ ---
SYSTEM_PROMPT = """Ты — эксперт-психолог (Big Five). Оцени совместимость девушки с веселым мужчиной.
Критерии: Высокая экстраверсия (>70), Низкий нейротизм (<40), Адаптивный юмор.
ВАЖНО: compatibility_score должен быть строго целым числом от 0 до 100. Не выходи за эти пределы.
Формат ответа: СТРОГО JSON без маркдауна.
{
  "big_five": {"extraversion": int, "neuroticism": int, "conscientiousness": int, "openness": int, "agreeableness": int},
  "humor_analysis": {"dominant_style": "string", "evidence": "string"},
  "compatibility_score": int (0-100),
  "verdict": "string",
  "red_flags": [],
  "personality_summary": "string"
}"""

USER_PROMPT_TEMPLATE = """
АНКЕТА:
Имя: {first_name}
Возраст: {bdate}
Город: {city}
Статус: {status}
О себе: {about}
Интересы: {activities}
Подписки: {subscriptions}

ЗАДАЧА: Проанализируй и верни JSON.
"""

def call_llm(prompt_text):
    import requests
    try:
        resp = requests.post(f"{OLLAMA_URL}/api/generate", json={
            "model": MODEL_NAME,
            "prompt": prompt_text,
            "system": SYSTEM_PROMPT,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.4}
        }, timeout=120)
        resp.raise_for_status()
        return resp.json().get('response', '')
    except Exception:
        return None

def analyze_single_profile(vk, profile):
    uid = profile['id']

    # Базовые проверки (дублирование для безопасности)
    if profile.get('is_closed', False): return None, "Закрыт"

    last_seen = profile.get('last_seen')
    if last_seen and 'time' in last_seen:
        if (datetime.now() - datetime.fromtimestamp(last_seen['time'])).days > 3:
            return None, "Неактивен"

    relation = profile.get('relation', 0)
    if relation in [2, 3, 4, 7, 8]: return None, "Занята"

    bdate = profile.get('bdate', '')
    year = parse_bdate(bdate)
    if not year or year < MIN_BIRTH_YEAR: return None, "Возраст"

    if not is_moscow(profile.get('city')): return None, "Не Москва"

    # Сбор данных
    subs = profile.get('subscriptions', [])
    if not subs:
        subs = get_profile_subscriptions(vk, uid)
        profile['subscriptions'] = subs

    context = {
        'first_name': profile.get('first_name', ''),
        'bdate': bdate,
        'city': profile.get('city', {}).get('title', '') if isinstance(profile.get('city'), dict) else '',
        'status': profile.get('status', ''),
        'about': profile.get('about', ''),
        'activities': profile.get('activities', ''),
        'subscriptions': ", ".join(subs[:20]) if subs else "Нет"
    }

    raw_json = call_llm(USER_PROMPT_TEMPLATE.format(**context))
    if not raw_json: return None, "Ошибка LLM"

    try:
        clean_json = re.sub(r'```json\s*|\s*```', '', raw_json).strip()
        analysis = json.loads(clean_json)

        # !!! ВАЛИДАЦИЯ SCORE (0-100) !!!
        score = analysis.get('compatibility_score', 0)
        if not isinstance(score, (int, float)):
            score = 0
        analysis['compatibility_score'] = max(0, min(100, int(score)))

    except json.JSONDecodeError:
        return None, "Парсинг JSON"

    # Генерация сообщения (ШАБЛОН)
    msg = ""
    if analysis['compatibility_score'] >= 90:
        name = profile.get('first_name', 'Друг')
        msg = f"Привет, {name}. 👋 Мои алгоритмы выделили твой профиль как совместимый с моим весёлым нравом 😄 Если ты не замужем, предлагаю познакомиться. Подробнее о себе: https://vk.com/wall758002654_43 Буду рад ответу!"
    else:
        msg = "Низкая совместимость."

    return {
        'profile': profile,
        'analysis': analysis,
        'generated_message': msg,
        'processed_at': datetime.now().isoformat()
    }, None

def save_stats_file(stats, total, stage1, stage2):
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        f.write("="*60 + "\nОТЧЕТ ПО ВОРОНКЕ ОТБОРА\n" + "="*60 + "\n\n")
        f.write(f"1. ВСЕГО ПРОВЕРЕНО: {total}\n")
        f.write(f"2. ПРОШЛИ ФИЛЬТР (Этап 1): {stage1} ({stage1/total*100:.1f}%)\n")
        f.write(f"3. УСПЕШНЫЙ LLM АНАЛИЗ (Этап 2): {stage2}\n\n")
        f.write("Причины отсева (Этап 1):\n")
        for k, v in stats.items():
            if v > 0: f.write(f" - {k.replace('_', ' ').title()}: {v}\n")
        f.write(f"\nИТОГОВАЯ КОНВЕРСИЯ: {stage2/total*100:.2f}%\n")

def main():
    print("="*60)
    print("ШАГ 1+2: Сбор -> Фильтрация -> Анализ (Big Five)")
    print("="*60)

    config = load_config()
    vk = init_vk(config['vk_token'])
    check_ollama()

    # Загрузка существующих
    existing_data = []
    if os.path.exists(FINAL_OUTPUT_FILE):
        try:
            with open(FINAL_OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            print(f"📂 Найдено {len(existing_data)} обработанных профилей.")
        except: pass

    existing_ids = {item['profile']['id'] for item in existing_data}

    # Статистика
    stats = {
        'wrong_sex': 0, 'not_moscow': 0, 'closed_profile': 0,
        'busy_relation': 0, 'too_old': 0, 'no_birth_year': 0,
        'already_processed': 0
    }
    total_checked = 0
    new_candidates = []

    print(f"🕸️ Сбор из групп: {config['group_ids_list']}")

    for group_id in config['group_ids_list']:
        print(f"   📋 Группа: {group_id}")
        offset = 0
        while True:
            try:
                # БЕЗ can_message!
                resp = vk.method('groups.getMembers', {
                    'group_id': group_id,
                    'offset': offset,
                    'count': 100,
                    'fields': 'sex,city,bdate,status,last_seen,relation,is_closed,photo_100'
                })
                items = resp.get('items', [])
                if not items: break

                for p in items:
                    total_checked += 1

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

                    rel = p.get('relation', 0)
                    if rel in [2, 3, 4, 7, 8]:
                        stats['busy_relation'] += 1
                        continue

                    year = parse_bdate(p.get('bdate', ''))
                    if not year:
                        stats['no_birth_year'] += 1
                        continue
                    if year < MIN_BIRTH_YEAR:
                        stats['too_old'] += 1
                        continue

                    new_candidates.append(p)

                offset += 100
                if offset % 500 == 0:
                    print(f"      ...проверено {offset}, найдено: {len(new_candidates)}")
                time.sleep(0.2)
            except Exception as e:
                print(f"Ошибка: {e}")
                break

    stage1_count = len(new_candidates)
    print(f"\n🚀 Этап 1 завершен. Найдено кандидатов: {stage1_count}")

    if not new_candidates:
        save_stats_file(stats, total_checked, 0, 0)
        print("✅ Нет новых кандидатов. Статистика сохранена.")
        return

    # Этап 2: LLM Анализ
    results = existing_data.copy()
    llm_success = 0

    print(f"🧠 Запуск LLM анализа для {stage1_count} профилей...")

    for p in tqdm(new_candidates, desc="Анализ", unit="prof"):
        res, err = analyze_single_profile(vk, p)
        if res:
            results.append(res)
            llm_success += 1
            # Автосохранение
            with open(FINAL_OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

    stage2_count = llm_success

    # Сохранение статистики
    save_stats_file(stats, total_checked, stage1_count, stage2_count)

    # Графики
    print("\n📊 Построение графиков...")

    # График 1: Причины отсева
    plt.clear_data()
    labels = [k.replace('_', ' ').title() for k, v in stats.items() if v > 0 and k != 'already_processed']
    values = [v for k, v in stats.items() if v > 0 and k != 'already_processed']

    if labels:
        plt.bar(labels, values)
        plt.title(f"Причины отсева (Всего отклонено: {total_checked - stage1_count})")
        plt.xlabel("Причина")
        plt.ylabel("Количество")
        plt.show()

    # График 2: Воронка
    plt.clear_data()
    funnel_labels = ["Всего проверено", "Прошли фильтр", "Успешный LLM"]
    funnel_values = [total_checked, stage1_count, stage2_count]

    plt.bar(funnel_labels, funnel_values)
    plt.title("Воронка конверсии")
    plt.xlabel("Этап")
    plt.ylabel("Профили")
    plt.show()

    print(f"\n✅ ГОТОВО! Итого в базе: {len(results)}")
    print(f"📄 Отчет сохранен в: {STATS_FILE}")

    # Топ-3
    top = sorted([r for r in results if r['analysis'].get('compatibility_score', 0) >= 90],
                 key=lambda x: x['analysis']['compatibility_score'], reverse=True)[:3]
    if top:
        print("\n🏆 ТОП-3 совпадения:")
        for t in top:
            print(f"- {t['profile']['first_name']}: {t['analysis']['compatibility_score']}%")

    # Запуск отчета
    script_dir = os.path.dirname(os.path.abspath(__file__))
    report_script = os.path.join(script_dir, "step3_generate_report.py")
    if os.path.exists(report_script):
        print("\n🔄 Генерация HTML отчета...")
        subprocess.run(["python", report_script])

if __name__ == '__main__':
    main()

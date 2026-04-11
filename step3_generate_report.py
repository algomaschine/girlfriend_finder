import json
import os
import sys
from datetime import datetime

# --- Конфигурация ---
INPUT_FILE = 'analyzed_profiles_live.json'
OUTPUT_FILE = 'result_report.html'
MIN_SCORE_THRESHOLD = 70  # Показывать только профили с совместимостью от этого значения

def load_data():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Файл {INPUT_FILE} не найден. Сначала запустите step1_2_pipeline.py")
        sys.exit(1)
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_big_five_html(scores):
    """Генерирует HTML строки для графиков Big Five"""
    labels = {
        'openness': ('Открытость', '#9b59b6'),
        'conscientiousness': ('Добросовестность', '#3498db'),
        'extraversion': ('Экстраверсия', '#f1c40f'),
        'agreeableness': ('Доброжелательность', '#2ecc71'),
        'neuroticism': ('Нейротизм', '#e74c3c') 
    }
    
    html = ""
    for key, (label, color) in labels.items():
        val = scores.get(key, 0)
        # Для нейротизма визуально показываем инверсию (чем меньше, тем лучше), но шкала остается 0-100
        html += f"""
        <div class="trait-row">
            <div class="trait-label">{label}</div>
            <div class="progress-bg">
                <div class="progress-bar" style="width: {val}%; background-color: {color};"></div>
            </div>
            <div class="trait-value">{val}</div>
        </div>
        """
    return html

def generate_profile_card(profile, index):
    analysis = profile.get('analysis', {})
    big_five = analysis.get('big_five', {})
    score = analysis.get('compatibility_score', 0)
    
    # Данные профиля
    name = f"{profile.get('first_name')} {profile.get('last_name', '')}"
    age = "?"
    if bdate := profile.get('bdate'):
        try:
            year = int(bdate.split('.')[-1])
            age = str(datetime.now().year - year)
        except:
            pass
            
    city = profile.get('city', 'Unknown')
    if isinstance(city, dict): city = city.get('title', 'Unknown')
    
    vk_id = profile.get('id')
    screen_name = profile.get('screen_name', f"id{vk_id}")
    url = f"https://vk.com/{screen_name}"
    
    # Интерпретация результатов
    humor = analysis.get('humor_style', 'Не определен')
    summary = analysis.get('summary', 'Нет описания')
    red_flags = analysis.get('red_flags', [])
    message = analysis.get('generated_message', 'Сообщение не сгенерировано').replace('"', '&quot;')
    
    # Цвет скоринга
    score_color = "#27ae60" if score >= 85 else "#f39c12" if score >= 70 else "#c0392b"
    
    flags_html = ""
    if red_flags:
        flags_html = "<div class='flags-list'>" + "".join([f"<span class='flag-item'>🚩 {flag}</span>" for flag in red_flags]) + "</div>"
    else:
        flags_html = "<div class='flags-clean'>✅ Красных флагов не обнаружено</div>"

    chart_html = generate_big_five_html(big_five)

    return f"""
    <div class="profile-card">
        <div class="card-header">
            <div class="rank-badge">#{index}</div>
            <div class="score-badge" style="border-color: {score_color}; color: {score_color};">
                СОВМЕСТИМОСТЬ: {score}%
            </div>
            <a href="{url}" target="_blank" class="vk-link">Открыть профиль VK ↗</a>
        </div>
        
        <div class="profile-info">
            <h2>{name} <span class="age-badge">{age} лет</span></h2>
            <p class="location">📍 {city}</p>
            <p class="humor-type">🎭 Тип юмора: <strong>{humor}</strong></p>
        </div>

        <div class="analysis-section">
            <h3>🧠 Психологический портрет</h3>
            <p class="summary-text">{summary}</p>
            
            <div class="big-five-container">
                {chart_html}
            </div>
        </div>

        <div class="risk-section">
            <h3>⚠️ Зоны риска</h3>
            {flags_html}
        </div>

        <div class="message-section">
            <h3>💌 Готовое сообщение для знакомства</h3>
            <div class="message-box">
                {message.replace(chr(10), '<br>')}
            </div>
            <button class="copy-btn" onclick="copyMessage(this, '{message.replace(chr(10), '\\n').replace("'", "\\'")}')">
                📋 Скопировать сообщение
            </button>
        </div>
    </div>
    """

def generate_html_header(total, count, threshold):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчет: Поиск партнера (Москва)</title>
    <style>
        :root {{
            --bg-color: #f4f7f6;
            --card-bg: #ffffff;
            --text-main: #2c3e50;
            --text-secondary: #7f8c8d;
            --accent: #3498db;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 40px;
            padding: 20px;
            background: var(--card-bg);
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }}
        h1 {{ margin: 0; color: #2c3e50; }}
        .stats {{ color: var(--text-secondary); margin-top: 10px; }}
        
        .profile-card {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            transition: transform 0.2s;
        }}
        .profile-card:hover {{
            transform: translateY(-2px);
        }}
        
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #eee;
            padding-bottom: 15px;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .rank-badge {{
            background: #ecf0f1;
            padding: 5px 10px;
            border-radius: 6px;
            font-weight: bold;
            color: #7f8c8d;
        }}
        .score-badge {{
            font-size: 1.2em;
            font-weight: bold;
            padding: 5px 15px;
            border: 2px solid;
            border-radius: 8px;
        }}
        .vk-link {{
            color: var(--accent);
            text-decoration: none;
            font-weight: 600;
        }}
        
        .profile-info h2 {{ margin: 0; display: inline; }}
        .age-badge {{ background: #e1f0fa; color: #3498db; padding: 2px 8px; border-radius: 4px; font-size: 0.9em; }}
        .location, .humor-type {{ color: var(--text-secondary); margin: 5px 0; }}
        
        .analysis-section, .risk-section, .message-section {{
            margin-top: 20px;
            background: #fafafa;
            padding: 15px;
            border-radius: 8px;
        }}
        h3 {{ margin-top: 0; font-size: 1.1em; color: #34495e; }}
        
        .big-five-container {{
            margin-top: 15px;
        }}
        .trait-row {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
            font-size: 0.9em;
        }}
        .trait-label {{ width: 130px; font-weight: 600; }}
        .progress-bg {{
            flex-grow: 1;
            height: 10px;
            background: #e0e0e0;
            border-radius: 5px;
            margin: 0 10px;
            overflow: hidden;
        }}
        .progress-bar {{
            height: 100%;
            border-radius: 5px;
            transition: width 0.5s ease;
        }}
        .trait-value {{ width: 30px; text-align: right; font-weight: bold; }}
        
        .flags-list {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .flag-item {{ background: #fadbd8; color: #c0392b; padding: 4px 10px; border-radius: 4px; font-size: 0.9em; }}
        .flags-clean {{ color: #27ae60; font-weight: 600; }}
        
        .message-box {{
            background: #fff;
            border: 1px solid #ddd;
            padding: 15px;
            border-radius: 6px;
            font-style: italic;
            color: #555;
            margin-bottom: 10px;
            white-space: pre-wrap;
        }}
        .copy-btn {{
            background: #2ecc71;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1em;
            font-weight: 600;
            transition: background 0.2s;
        }}
        .copy-btn:hover {{ background: #27ae60; }}
        .copy-btn:active {{ transform: scale(0.98); }}
        .copy-btn.copied {{ background: #34495e; }}
        
        @media (max-width: 600px) {{
            .card-header {{ flex-direction: column; align-items: flex-start; }}
            .trait-label {{ width: 100px; font-size: 0.8em; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>💘 Отчет: Поиск партнера с «Веселым Нравом»</h1>
            <div class="stats">
                📅 {date_str} | Всего профилей: {total} | Подходящих (Скор ≥ {threshold}): <strong>{count}</strong>
            </div>
            <p style="font-size: 0.9em; color: #7f8c8d; max-width: 600px; margin: 10px auto;">
                Критерии: Высокая экстраверсия, низкий нейротизм, адаптивный юмор. 
                Сообщения сгенерированы индивидуально под психотип.
            </p>
        </header>
"""

def generate_html_footer():
    return """
    </div>
    <script>
        function copyMessage(btn, text) {
            // Создаем временный textarea для копирования
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            
            // Визуальный фидбек
            const originalText = btn.innerText;
            btn.innerText = "✅ Скопировано!";
            btn.classList.add('copied');
            
            setTimeout(() => {
                btn.innerText = originalText;
                btn.classList.remove('copied');
            }, 2000);
        }
    </script>
</body>
</html>
"""

def main():
    print("="*60)
    print("ШАГ 3: Генерация HTML-отчета")
    print("="*60)
    
    data = load_data()
    print(f"📂 Загружено профилей: {len(data)}")
    
    # Фильтрация: только те, у кого есть анализ и высокий скор
    valid_profiles = [
        p for p in data 
        if 'analysis' in p and p.get('analysis', {}).get('compatibility_score', 0) >= MIN_SCORE_THRESHOLD
    ]
    
    print(f"✅ Найдено {len(valid_profiles)} подходящих профилей (Скор ≥ {MIN_SCORE_THRESHOLD}).")
    
    if not valid_profiles:
        print("❌ Нет подходящих кандидатов. Попробуйте снизить порог в коде скрипта.")
        return

    # Сортировка по совместимости (убывание)
    valid_profiles.sort(key=lambda x: x['analysis'].get('compatibility_score', 0), reverse=True)
    
    # Генерация HTML
    html_content = generate_html_header(len(data), len(valid_profiles), MIN_SCORE_THRESHOLD)
    
    for i, profile in enumerate(valid_profiles, 1):
        html_content += generate_profile_card(profile, i)
        
    html_content += generate_html_footer()
    
    # Сохранение
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"📄 Отчет успешно сохранен в {OUTPUT_FILE}")
    print(f"🌟 Лучший кандидат: {valid_profiles[0].get('first_name')} (Скор: {valid_profiles[0]['analysis']['compatibility_score']})")
    print(f"🚀 Откройте файл в браузере, чтобы скопировать сообщения одним кликом.")

if __name__ == '__main__':
    main()

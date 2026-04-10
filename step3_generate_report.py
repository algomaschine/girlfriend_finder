#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Шаг 3: Генерация HTML-отчета по результатам анализа.

Этот скрипт:
- Загружает проанализированные профили из analyzed_profiles.json
- Сортирует по совместимости (compatibility_score)
- Генерирует красивый HTML-отчёт с топ-кандидатами (score ≥ 80)
- Сохраняет отчёт в result_report.html

Выходные данные: result_report.html
"""

import json
from datetime import datetime
from typing import List, Dict, Any


def load_config():
    """Загрузка конфигурации из config.json"""
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def load_analyzed_profiles(filename='analyzed_profiles.json'):
    """Загрузка проанализированных профилей"""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)


def sort_by_score(profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Сортировка профилей по score (убывание)"""
    return sorted(
        profiles,
        key=lambda x: x.get('analysis', {}).get('compatibility_score', 0),
        reverse=True
    )


def generate_html_report(profiles: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
    """Генерация HTML-отчёта"""
    # Общая статистика
    total = len(profiles)
    successful = sum(1 for p in profiles if 'error' not in p.get('analysis', {}))

    # Отбираем кандидатов с score >= 80
    high_score_candidates = []
    for p in profiles:
        analysis = p.get('analysis', {})
        if 'error' not in analysis:
            score = analysis.get('compatibility_score', 0)
            if score >= 8:
                high_score_candidates.append(p)

    # Сортируем по убыванию score
    high_score_candidates.sort(
        key=lambda x: x.get('analysis', {}).get('compatibility_score', 0),
        reverse=True
    )

    group_id = config.get('group_id', 'не указана')
    now = datetime.now()
    date_str = now.strftime('%d.%m.%Y %H:%M')

    # Начало HTML
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Отчёт по стратегии «Веселый нрав» – только лучшие кандидаты</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #f0f2f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1, h2 {{ color: #1e3c72; }}
        .candidate {{ background: white; margin-bottom: 30px; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
        .candidate h3 {{ margin-top: 0; color: #0a4b6e; border-left: 5px solid #27ae60; padding-left: 12px; }}
        .score {{ font-size: 1.4em; font-weight: bold; color: #27ae60; }}
        .big-five {{ display: flex; gap: 15px; flex-wrap: wrap; margin: 15px 0; }}
        .big-five span {{ background: #eef2f7; padding: 6px 12px; border-radius: 25px; font-size: 0.9em; }}
        .humor {{ background: #fff4e6; padding: 10px; border-left: 5px solid #f39c12; margin: 10px 0; }}
        .reason {{ background: #e8f8f5; padding: 10px; border-left: 5px solid #1abc9c; margin: 10px 0; }}
        .link {{ word-break: break-all; font-size: 0.9em; color: #2980b9; }}
        hr {{ margin: 20px 0; }}
        .badge {{ display: inline-block; background: #27ae60; color: white; border-radius: 20px; padding: 2px 10px; font-size: 0.8em; margin-left: 10px; }}
    </style>
</head>
<body>
<div class="container">
    <h1>📊 Отчёт по стратегии «Веселый нрав»</h1>
    <p><strong>Дата анализа:</strong> {date_str}</p>
    <p><strong>Источник:</strong> VK-сообщество (группа {group_id})</p>
    <p><strong>Всего обработано профилей:</strong> {total}</p>
    <p><strong>Кандидатов с высоким соответствием (score ≥ 80):</strong> {len(high_score_candidates)}</p>
    <hr>
"""

    # Если нет кандидатов
    if not high_score_candidates:
        html += "<p>⚠️ Кандидатов с высоким скором не найдено.</p>"
    else:
        # Для каждого кандидата создаём блок
        for profile in high_score_candidates:
            first_name = profile.get('first_name', '')
            last_name = profile.get('last_name', '')
            user_id = profile.get('id', '')
            screen_name = profile.get('screen_name', f'id{user_id}')
            # Ссылка: если screen_name числовой или пустой, используем id, иначе screen_name
            if screen_name and not screen_name.isdigit():
                link = f"https://vk.com/{screen_name}"
            else:
                link = f"https://vk.com/id{user_id}"

            analysis = profile.get('analysis', {})
            score = analysis.get('compatibility_score', 0)
            big_five = analysis.get('big_five', {})
            humor_type = analysis.get('humor_type', 'не определён')
            humor_analysis = analysis.get('humor_analysis', '')
            reason = analysis.get('reason', '')

            # Извлечение подписок (до 5 штук) для юмористического контекста
            subscriptions = profile.get('subscriptions', [])
            subs_text = ', '.join(subscriptions[:5]) if subscriptions else 'нет данных'

            # Формирование строки для блока юмора
            humor_text = f"<strong>{humor_type}</strong><br>"
            if humor_analysis:
                humor_text += f"{humor_analysis} "
            if subscriptions:
                humor_text += f"Подписки: {subs_text}"
            else:
                humor_text += "Нет подписок на юмористические паблики."

            # Значения Big Five (по умолчанию 0)
            extraversion = big_five.get('extraversion', 0)
            emotional_stability = big_five.get('emotional_stability', 0)
            openness = big_five.get('openness', 0)
            conscientiousness = big_five.get('conscientiousness', 0)

            html += f"""
    <div class="candidate">
        <h3>✅ {first_name} {last_name} <span class="badge">ID {user_id}</span></h3>
        <div class="link">🔗 <a href="{link}" target="_blank">{link}</a></div>
        <div class="score">🎯 Совместимость: {score}/100</div>
        <div class="big-five">
            <span>🧩 Экстраверсия: {extraversion}/10</span>
            <span>🧠 Эмоц. стабильность: {emotional_stability}/10</span>
            <span>🌟 Открытость: {openness}/10</span>
            <span>📋 Добросовестность: {conscientiousness}/10</span>
        </div>
        <div class="humor">🎭 Тип юмора: {humor_text}</div>
        <div class="reason">💡 <strong>Почему подходит:</strong> {reason}</div>
    </div>
"""

    # Закрывающие теги
    html += """
</div>
</body>
</html>"""
    return html


def main():
    """Основная функция"""
    print("=" * 60)
    print("ШАГ 3: Генерация HTML-отчета")
    print("=" * 60)

    # Загрузка конфигурации
    config = load_config()

    # Загрузка проанализированных профилей
    profiles = load_analyzed_profiles()

    if not profiles:
        print("Нет данных для генерации отчета. Сначала запустите step1_collect_profiles.py и step2_analyze.py")
        return

    print(f"Загружено {len(profiles)} проанализированных профилей")

    # Генерация HTML
    html_report = generate_html_report(profiles, config)

    # Сохранение отчета
    output_file = 'result_report.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_report)

    print(f"\n✓ Отчет сохранен в {output_file}")
    print("\n" + "=" * 60)
    print("Пайплайн завершен!")
    print("Откройте result_report.html для просмотра результатов")
    print("=" * 60)


if __name__ == '__main__':
    main()

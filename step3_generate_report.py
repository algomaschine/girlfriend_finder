#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Шаг 3: Генерация Markdown-отчета по результатам анализа.

Этот скрипт:
- Загружает проанализированные профили из analyzed_profiles.json
- Сортирует по совместимости (compatibility_score)
- Генерирует красивый Markdown-отчет с топ-кандидатами и детальным разбором
- Сохраняет отчет в result_report.md

Выходные данные: result_report.md
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


def generate_header(config: Dict[str, Any], total: int, successful: int) -> str:
    """Генерация заголовка отчета"""
    group_id = config.get('group_id', 'Не указан')
    
    header = f"""# 📊 Отчет: Поиск по стратегии «Веселый нрав»

**Дата анализа:** {datetime.now().strftime('%d %B %Y г.')}  
**Источник:** Сообщество VK ID {group_id}  
**Модель анализа:** Qwen 2.5 72B (via Hugging Face Inference API)  

---

## 📈 Статистика

- **Всего обработано профилей:** {total}
- **Успешно проанализировано:** {successful}
- **Высокий скор (≥80):** {sum(1 for p in profiles if p.get('analysis', {}).get('compatibility_score', 0) >= 80)}
- **Средний скор:** {sum(p.get('analysis', {}).get('compatibility_score', 0) for p in profiles) / max(len(profiles), 1):.1f}

---

"""
    return header


def generate_top_candidates_table(profiles: List[Dict[str, Any]], top_n: int = 10) -> str:
    """Генерация таблицы топ-кандидатов"""
    section = "## 🏆 Топ кандидатов (Score ≥ 80)\n\n"
    
    # Фильтруем только те, у кого score >= 80
    high_scores = [p for p in profiles if p.get('analysis', {}).get('compatibility_score', 0) >= 80]
    high_scores = high_scores[:top_n]  # Берем только топ-N
    
    if not high_scores:
        section += "*К сожалению, кандидатов с высоким скором не найдено.*\n\n"
        return section
    
    section += "| Имя | ID / Ссылка | Скор | Тип юмора | Вердикт |\n"
    section += "|-----|-------------|------|-----------|---------|\n"
    
    for profile in high_scores:
        first_name = profile.get('first_name', '')
        last_name = profile.get('last_name', '')
        user_id = profile.get('id', '')
        screen_name = profile.get('screen_name', f'id{user_id}')
        
        analysis = profile.get('analysis', {})
        score = analysis.get('compatibility_score', 0)
        humor_type = analysis.get('humor_type', 'неопределен')
        reason = analysis.get('reason', '')[:50] + '...' if len(analysis.get('reason', '')) > 50 else analysis.get('reason', '')
        
        link = f"https://vk.com/{screen_name}"
        
        section += f"| {first_name} {last_name} | [{user_id}]({link}) | {score} | {humor_type} | {reason} |\n"
    
    section += "\n---\n\n"
    return section


def generate_detailed_analysis(profiles: List[Dict[str, Any]], top_n: int = 20) -> str:
    """Генерация детального разбора топ-кандидатов"""
    section = "## 🔍 Детальный разбор\n\n"
    
    # Берем топ-N профилей по скору
    top_profiles = profiles[:top_n]
    
    for idx, profile in enumerate(top_profiles, 1):
        first_name = profile.get('first_name', '')
        last_name = profile.get('last_name', '')
        user_id = profile.get('id', '')
        screen_name = profile.get('screen_name', f'id{user_id}')
        link = f"https://vk.com/{screen_name}"
        
        analysis = profile.get('analysis', {})
        
        # Проверка на ошибку анализа
        if 'error' in analysis:
            section += f"### ➡️ Профиль {user_id}\n\n"
            section += f"**Ошибка:** {analysis['error']}\n\n"
            section += "---\n\n"
            continue
        
        score = analysis.get('compatibility_score', 0)
        big_five = analysis.get('big_five', {})
        humor_analysis = analysis.get('humor_analysis', '')
        humor_type = analysis.get('humor_type', 'неопределен')
        matches = analysis.get('matches_strategy', False)
        reason = analysis.get('reason', '')
        
        # Основная информация
        status = profile.get('status', '')
        about = profile.get('about', '')
        interests = profile.get('interests', '')
        city = profile.get('city', '')
        
        emoji = "✅" if matches else "❌"
        
        section += f"### {emoji} {first_name} {last_name} (ID: {user_id})\n\n"
        section += f"**Ссылка:** [{link}]({link})  \n"
        section += f"**Совместимость:** {score}/100  \n"
        section += f"**Соответствует стратегии:** {'Да' if matches else 'Нет'}\n\n"
        
        if status:
            section += f"**Статус:** \"{status}\"\n\n"
        
        if about:
            section += f"**О себе:** {about}\n\n"
        
        # Big Five
        section += "**Анализ «Большой пятерки»:**\n"
        section += f"- 🟢 Экстраверсия: {big_five.get('extraversion', 'N/A')}/10\n"
        section += f"- 🟢 Эмоциональная стабильность: {big_five.get('emotional_stability', 'N/A')}/10\n"
        section += f"- 🟢 Открытость опыту: {big_five.get('openness', 'N/A')}/10\n"
        section += f"- 🟢 Добросовестность: {big_five.get('conscientiousness', 'N/A')}/10\n\n"
        
        # Юмор
        section += f"**Стиль юмора:** {humor_type}\n"
        if humor_analysis:
            section += f"{humor_analysis}\n\n"
        
        # Подписки (топ-5)
        subscriptions = profile.get('subscriptions', [])
        if subscriptions:
            section += "**Топ подписок:**\n"
            for sub in subscriptions[:5]:
                section += f"- {sub}\n"
            section += "\n"
        
        # Вердикт
        section += f"**💡 Почему {'подходит' if matches else 'не подходит'}:** {reason}\n\n"
        section += "---\n\n"
    
    return section


def generate_summary(profiles: List[Dict[str, Any]]) -> str:
    """Генерация сводной статистики"""
    section = "## 🛠 Техническая статистика\n\n"
    
    total = len(profiles)
    with_errors = sum(1 for p in profiles if 'error' in p.get('analysis', {}))
    successful = total - with_errors
    
    # Распределение по скорам
    score_ranges = {
        '90-100': 0,
        '80-89': 0,
        '70-79': 0,
        '60-69': 0,
        '0-59': 0
    }
    
    for p in profiles:
        score = p.get('analysis', {}).get('compatibility_score', 0)
        if score >= 90:
            score_ranges['90-100'] += 1
        elif score >= 80:
            score_ranges['80-89'] += 1
        elif score >= 70:
            score_ranges['70-79'] += 1
        elif score >= 60:
            score_ranges['60-69'] += 1
        else:
            score_ranges['0-59'] += 1
    
    section += f"- **Всего обработано:** {total} профилей\n"
    section += f"- **Успешно проанализировано:** {successful}\n"
    section += f"- **С ошибками:** {with_errors}\n\n"
    
    section += "**Распределение по совместимости:**\n"
    for range_name, count in score_ranges.items():
        bar = "█" * count
        section += f"- {range_name}: {count} {bar}\n"
    
    section += "\n---\n\n"
    return section


def generate_footer() -> str:
    """Генерация подвала отчета"""
    footer = f"""## ℹ️ Примечание

Этот отчет сгенерирован автоматически с помощью ИИ-модели Qwen 2.5 72B. 
Результаты анализа носят рекомендательный характер и требуют дополнительной ручной проверки.

**Важно:**
- Анализ основан только на открытых данных профиля
- Закрытые профили были исключены из обработки
- Психометрическая оценка приблизительная и не заменяет профессиональную консультацию

---

*Отчет создан: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
    return footer


def main():
    """Основная функция"""
    print("=" * 60)
    print("ШАГ 3: Генерация Markdown-отчета")
    print("=" * 60)
    
    # Загрузка конфигурации
    config = load_config()
    
    # Загрузка проанализированных профилей
    profiles = load_analyzed_profiles()
    
    if not profiles:
        print("Нет данных для генерации отчета. Сначала запустите step1_collect_profiles.py и step2_analyze.py")
        return
    
    print(f"Загружено {len(profiles)} проанализированных профилей")
    
    # Сортировка по скору
    sorted_profiles = sort_by_score(profiles)
    
    # Генерация отчета
    report = ""
    report += generate_header(config, len(profiles), len([p for p in profiles if 'error' not in p.get('analysis', {})]))
    report += generate_top_candidates_table(sorted_profiles)
    report += generate_detailed_analysis(sorted_profiles)
    report += generate_summary(sorted_profiles)
    report += generate_footer()
    
    # Сохранение отчета
    output_file = 'result_report.md'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✓ Отчет сохранен в {output_file}")
    print("\n" + "=" * 60)
    print("Пайплайн завершен!")
    print("Откройте result_report.md для просмотра результатов")
    print("=" * 60)


if __name__ == '__main__':
    main()

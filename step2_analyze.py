#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Шаг 2: Психометрический анализ профилей с помощью LLM.

Этот скрипт:
- Загружает профили из filtered_profiles.json
- Отправляет каждый профиль на анализ в бесплатную LLM (Qwen 2.5 72B через Hugging Face API)
- Получает JSON-ответ с оценкой по модели "Большой пятерки" и типу юмора
- Экспортирует результаты анализа в analyzed_profiles.json

Выходные данные: analyzed_profiles.json
"""

import json
import time
import requests
from typing import Dict, Any, Optional


def load_config():
    """Загрузка конфигурации из config.json"""
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def load_profiles(filename='filtered_profiles.json'):
    """Загрузка профилей из JSON файла"""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)


def prepare_profile_text(profile: Dict[str, Any]) -> str:
    """Подготовка текста профиля для отправки в LLM"""
    text_parts = []
    
    # Основная информация
    if profile.get('status'):
        text_parts.append(f"Статус: {profile['status']}")
    
    if profile.get('about'):
        text_parts.append(f"О себе: {profile['about']}")
    
    if profile.get('activities'):
        text_parts.append(f"Деятельность: {profile['activities']}")
    
    if profile.get('interests'):
        text_parts.append(f"Интересы: {profile['interests']}")
    
    if profile.get('music'):
        text_parts.append(f"Музыка: {profile['music']}")
    
    if profile.get('movies'):
        text_parts.append(f"Фильмы: {profile['movies']}")
    
    if profile.get('tv'):
        text_parts.append(f"ТВ: {profile['tv']}")
    
    if profile.get('books'):
        text_parts.append(f"Книги: {profile['books']}")
    
    if profile.get('quotes'):
        text_parts.append(f"Цитаты: {profile['quotes']}")
    
    # Подписки
    if profile.get('subscriptions'):
        subs_text = ", ".join(profile['subscriptions'][:15])
        text_parts.append(f"Подписки: {subs_text}")
    
    # Город и образование
    if profile.get('city'):
        text_parts.append(f"Город: {profile['city']}")
    
    if profile.get('education'):
        text_parts.append(f"Образование: {profile['education']}")
    
    return "\n".join(text_parts)


def analyze_with_llm(profile_text: str, hf_token: str) -> Optional[Dict[str, Any]]:
    """
    Анализ профиля с помощью Qwen 2.5 72B через Hugging Face Inference API.
    
    Используется бесплатная серверная версия API.
    Модель: Qwen/Qwen2.5-72B-Instruct
    """
    
    # Системный промпт согласно документации
    system_prompt = """Ты — ИИ-психолог. Твоя цель: проанализировать профиль девушки из ВК на соответствие стратегии «Веселого нрава».

Входные данные: текст статуса, интересы, деятельность и список подписок.

Инструкция на основе документа:
1. Оцени Экстраверсию: ищи маркеры активности (танцы, ивенты, спорт, социальные активности).
2. Оцени Нейротизм: ищи признаки эмоциональной стабильности и позитива (низкий нейротизм — хорошо).
3. Определи тип юмора:
   - Аффилиативный (объединяющий, добрый) — плюс
   - Самоирония (умение смеяться над собой) — плюс
   - Агрессивный (насмешки, сарказм) — минус
4. Оцени Открытость опыту (путешествия, творчество, мастер-классы, танцы, скалолазание).
5. Оцени Добросовестность (стабильность, надежность).

Выдай ответ СТРОГО в формате JSON без дополнительного текста:
{
  "compatibility_score": число от 0 до 100,
  "big_five": {
    "extraversion": число от 1 до 10,
    "emotional_stability": число от 1 до 10,
    "openness": число от 1 до 10,
    "conscientiousness": число от 1 до 10
  },
  "humor_analysis": "краткое описание стиля юмора",
  "humor_type": "аффилиативный" или "самоирония" или "дезадаптивный" или "неопределен",
  "matches_strategy": true или false,
  "reason": "краткое обоснование почему подходит или не подходит согласно критериям из PDF"
}"""

    # Формируем пользовательский запрос
    user_message = f"""Проанализируй следующий профиль:

{profile_text}

Помни: выдай ответ ТОЛЬКО в формате JSON, без пояснений и дополнительного текста."""

    # Endpoint для Qwen 2.5 72B
    api_url = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-72B-Instruct/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "Qwen/Qwen2.5-72B-Instruct",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.3,
        "max_tokens": 500,
        "response_format": {"type": "json_object"}
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            # Парсим JSON ответ
            try:
                analysis = json.loads(content)
                return analysis
            except json.JSONDecodeError:
                print(f"Ошибка парсинга JSON ответа: {content[:200]}")
                return None
                
        elif response.status_code == 503:
            print("Модель загружается... Повторная попытка через 30 секунд")
            time.sleep(30)
            return analyze_with_llm(profile_text, hf_token)
        else:
            print(f"Ошибка API: {response.status_code} - {response.text[:200]}")
            return None
            
    except requests.exceptions.Timeout:
        print("Таймаут запроса к API")
        return None
    except Exception as e:
        print(f"Ошибка при вызове LLM: {e}")
        return None


def analyze_all_profiles(profiles: list, hf_token: str, start_index: int = 0) -> list:
    """Анализ всех профилей с сохранением прогресса"""
    
    analyzed = []
    total = len(profiles)
    
    print(f"Начинаем анализ {total} профилей...")
    
    for idx, profile in enumerate(profiles):
        if idx < start_index:
            continue
            
        user_id = profile.get('id', 'unknown')
        print(f"\n[{idx + 1}/{total}] Анализ профиля {user_id} ({profile.get('first_name', '')} {profile.get('last_name', '')})...")
        
        # Подготовка текста
        profile_text = prepare_profile_text(profile)
        
        if not profile_text.strip():
            print(f"  Профиль пуст, пропускаем")
            analyzed.append({
                **profile,
                'analysis': {
                    'error': 'Пустой профиль',
                    'compatibility_score': 0
                }
            })
            continue
        
        # Вызов LLM
        analysis = analyze_with_llm(profile_text, hf_token)
        
        if analysis:
            print(f"  ✓ Анализ успешен. Score: {analysis.get('compatibility_score', 'N/A')}")
            analyzed.append({
                **profile,
                'analysis': analysis
            })
        else:
            print(f"  ✗ Ошибка анализа")
            analyzed.append({
                **profile,
                'analysis': {
                    'error': 'Не удалось получить анализ от LLM',
                    'compatibility_score': 0
                }
            })
        
        # Сохраняем прогресс каждые 5 профилей
        if (idx + 1) % 5 == 0:
            save_intermediate(analyzed, 'analyzed_profiles_temp.json')
            print(f"  Прогресс сохранен в analyzed_profiles_temp.json")
        
        # Соблюдение лимитов Hugging Face API
        time.sleep(1.5)
    
    return analyzed


def save_intermediate(data: list, filename: str):
    """Промежуточное сохранение результатов"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_results(analyzed: list, filename='analyzed_profiles.json'):
    """Сохранение финальных результатов"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(analyzed, f, ensure_ascii=False, indent=2)
    print(f"\nРезультаты сохранены в {filename}")


def main():
    """Основная функция"""
    print("=" * 60)
    print("ШАГ 2: Психометрический анализ профилей с помощью LLM")
    print("=" * 60)
    
    # Загрузка конфигурации
    config = load_config()
    hf_token = config.get('huggingface_token')
    
    if not hf_token:
        print("Ошибка: Не указан huggingface_token в config.json")
        print("Получите токен на https://huggingface.co/settings/tokens")
        return
    
    # Загрузка профилей
    profiles = load_profiles()
    
    if not profiles:
        print("Нет профилей для анализа. Сначала запустите step1_collect_profiles.py")
        return
    
    print(f"Загружено {len(profiles)} профилей для анализа")
    
    # Анализ
    analyzed = analyze_all_profiles(profiles, hf_token)
    
    # Сохранение результатов
    save_results(analyzed)
    
    # Статистика
    successful = sum(1 for p in analyzed if 'error' not in p.get('analysis', {}))
    high_scores = sum(1 for p in analyzed if p.get('analysis', {}).get('compatibility_score', 0) >= 80)
    
    print("\n" + "=" * 60)
    print(f"Анализ завершен!")
    print(f"Успешно проанализировано: {successful}/{len(analyzed)}")
    print(f"Высокий скор (>=80): {high_scores} профилей")
    print("Следующий шаг: запустите step3_generate_report.py для создания отчета")
    print("=" * 60)


if __name__ == '__main__':
    main()

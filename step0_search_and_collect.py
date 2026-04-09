#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
step1_search_and_collect.py
ШАГ 0 (Опциональный): Поиск групп в Москве и сбор активных женских профилей.

Ищет группы по ключевым словам (психология, знакомства, Москва),
проверяет активность участников (обновления за 7 дней) и фильтрует девушек.
Экспортирует результат в `active_female_profiles.json`.
"""

import json
import time
import requests
import vk_api
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from vk_api.utils import get_random_id

# --- КОНФИГУРАЦИЯ ---
CONFIG_FILE = "config.json"
OUTPUT_FILE = "active_female_profiles.json"
TEMP_FILE = "active_female_profiles_temp.json"

# Ключевые слова для поиска групп (можно дополнять)
SEARCH_KEYWORDS = [
    "психология отношений москва",
    "знакомства москва",
    "девушки москва",
    "саморазвитие москва",
    "одинокие сердца москва",
    "любовь москва",
    "семья и отношения москва",
    "женский клуб москва",
    "фотограф москва модель", # Для поиска моделей/активных
    "мероприятия москва"
]

# Лимиты
MAX_GROUPS_TO_SEARCH = 20       # Сколько групп найти всего
PROFILES_PER_GROUP = 50         # Сколько профилей проверить в каждой группе
DAYS_ACTIVE_THRESHOLD = 7       # Дней с последнего обновления
DELAY_BETWEEN_REQUESTS = 0.4    # Задержка между запросами к VK

# --- ФУНКЦИИ ---

def load_config() -> Dict[str, Any]:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Ошибка: Файл {CONFIG_FILE} не найден!")
        print("💡 Скопируйте config.json.example в config.json и заполните токены.")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка: Неверный формат JSON в {CONFIG_FILE}: {e}")
        exit(1)

def init_vk_session(token: str) -> vk_api.VkApi:
    vk_session = vk_api.VkApi(token=token)
    try:
        vk_session.authorization()
    except vk_api.AuthError as error_msg:
        print(f"❌ Ошибка авторизации VK: {error_msg}")
        exit(1)
    return vk_session

def search_groups(vk: vk_api.VkApi, keywords: List[str], max_count: int) -> List[Dict]:
    """Ищет группы по ключевым словам."""
    found_groups = []
    seen_ids = set()
    
    print(f"\n🔍 Поиск групп по ключевым словам: {', '.join(keywords[:3])}...")
    
    for keyword in keywords:
        if len(found_groups) >= max_count:
            break
            
        try:
            response = vk.method('groups.search', {
                'q': keyword,
                'sort': 6,      # По активности
                'type': 1,      # Только открытые
                'count': 20
            })
            
            items = response.get('items', [])
            for group in items:
                gid = group['id']
                if gid not in seen_ids and len(found_groups) < max_count:
                    seen_ids.add(gid)
                    found_groups.append(group)
                    print(f"   [+] Найдена группа: {group['name']} (id: {gid}, участники: {group.get('members_count', '?')})")
            
            time.sleep(DELAY_BETWEEN_REQUESTS)
        except Exception as e:
            print(f"   ⚠️ Ошибка при поиске '{keyword}': {e}")
            continue
            
    return found_groups

def is_profile_active_recently(vk: vk_api.VkApi, user_id: int, days: int) -> bool:
    """
    Проверяет, было ли обновление профиля (статус, фото, стена) за последние N дней.
    Примечание: Точную дату последнего входа VK скрывает, проверяем косвенно.
    """
    threshold_date = datetime.now() - timedelta(days=days)
    
    try:
        # 1. Проверка статуса (date не всегда доступна, но попробуем)
        # 2. Проверка последнего поста на стене
        wall = vk.method('wall.get', {
            'owner_id': user_id,
            'count': 1,
            'filter': 'owner' # Только свои посты
        })
        
        if wall.get('items'):
            post_date = wall['items'][0].get('date')
            if post_date:
                post_datetime = datetime.fromtimestamp(post_date)
                if post_datetime > threshold_date:
                    return True
        
        # 3. Проверка обновлений фото (загруженные пользователем)
        # Это тяжелый запрос, делаем опционально или если стена пуста
        # Для скорости пока ограничимся стеной и статусом
        
        # Если стена закрыта или пуста, считаем неактивным для надежности
        return False
        
    except vk_api.exceptions.ApiError as e:
        # Стена закрыта или недоступна - считаем неактивным или неизвестным
        return False
    except Exception:
        return False

def get_user_details_with_activity(vk: vk_api.VkApi, user_id: int) -> Optional[Dict]:
    """Получает детали пользователя и проверяет активность."""
    try:
        fields = "sex,relation,bdate,city,occupation,activities,interests,about,status,last_seen"
        user_data = vk.method('users.get', {
            'user_ids': user_id,
            'fields': fields
        })
        
        if not user_data:
            return None
            
        user = user_data[0]
        
        # Фильтр: Женский пол (1)
        if user.get('sex') != 1:
            return None
            
        # Фильтр: Семейное положение (1 - не замужем, 6 - в активном поиске)
        # Можно настроить под себя
        relation = user.get('relation', 0)
        if relation not in [1, 6, 0]: # 0 - не указано, тоже берем
             # Если нужно строго "не замужем", раскомментируйте ниже:
             # if relation in [2, 3, 4, 5, 7, 8]: return None
             pass 

        # Проверка активности за последнюю неделю
        # last_seen дает время онлайн, но не дату обновления контента
        # Используем нашу функцию проверки стены
        is_active = is_profile_active_recently(vk, user_id, DAYS_ACTIVE_THRESHOLD)
        
        if not is_active:
            return None
            
        # Дополнительная информация
        user['is_active_last_week'] = True
        user['analyzed_at'] = datetime.now().isoformat()
        
        return user
        
    except Exception as e:
        return None

def collect_profiles_from_group(vk: vk_api.VkApi, group_id: int, count: int) -> List[Dict]:
    """Собирает активные женские профили из конкретной группы."""
    active_profiles = []
    
    try:
        # Получаем участников группы
        # Метод groups.getMembers доступен для открытых групп
        members_response = vk.method('groups.getMembers', {
            'group_id': group_id,
            'fields': 'sex,relation,last_seen',
            'count': min(count, 100), # Максимум за запрос
            'sort': 0 # По времени вступления (новые чаще активны)
        })
        
        members = members_response.get('items', [])
        
        print(f"   📥 Проверка {len(members)} участников из группы {group_id}...")
        
        for member in members:
            if len(active_profiles) >= count:
                break
                
            user_id = member['id']
            
            # Быстрая предфильтрация по полу (если доступно в members)
            if member.get('sex') == 2: # Мужчина
                continue
                
            # Глубокая проверка (стена, активность)
            detailed_user = get_user_details_with_activity(vk, user_id)
            
            if detailed_user:
                active_profiles.append(detailed_user)
                print(f"      ✅ Активный профиль: {detailed_user['first_name']} {detailed_user.get('last_name', '')} (id: {user_id})")
            
            time.sleep(DELAY_BETWEEN_REQUESTS * 2) # Чуть больше задержка для детальных запросов
            
    except Exception as e:
        print(f"   ❌ Ошибка при сборе из группы {group_id}: {e}")
        
    return active_profiles

def save_progress(data: List[Dict], filename: str):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    print("="*60)
    print("ШАГ 0: Поиск групп в Москве и сбор активных женских профилей")
    print("="*60)
    
    config = load_config()
    vk_token = config.get('vk_token')
    
    if not vk_token:
        print("❌ Отсутствует vk_token в config.json")
        exit(1)
        
    vk = init_vk_session(vk_token)
    
    # 1. Поиск групп
    groups = search_groups(vk, SEARCH_KEYWORDS, MAX_GROUPS_TO_SEARCH)
    
    if not groups:
        print("❌ Группы не найдены. Попробуйте изменить ключевые слова в скрипте.")
        exit(1)
        
    print(f"\n✅ Найдено {len(groups)} групп для анализа.")
    
    # 2. Сбор профилей
    all_active_profiles = []
    
    print(f"\n🚀 Начинаем сбор активных профилей (критерий: обновление за {DAYS_ACTIVE_THRESHOLD} дн.)...")
    
    for i, group in enumerate(groups):
        gid = group['id']
        gname = group['name']
        print(f"\n[{i+1}/{len(groups)}] Группа: {gname}")
        
        profiles = collect_profiles_from_group(vk, gid, PROFILES_PER_GROUP)
        all_active_profiles.extend(profiles)
        
        print(f"   🎯 Из этой группы найдено активных: {len(profiles)}")
        
        # Сохранение прогресса после каждой группы
        save_progress(all_active_profiles, TEMP_FILE)
        
        if len(all_active_profiles) >= 200: # Лимит на общий сбор, чтобы не долго
            print("⚠️ Достигнут лимит сбора профилей (200). Останавливаем.")
            break
            
    # 3. Финальное сохранение
    save_progress(all_active_profiles, OUTPUT_FILE)
    
    print("\n" + "="*60)
    print(f"✅ ГОТОВО! Найдено {len(all_active_profiles)} активных женских профилей.")
    print(f"💾 Данные сохранены в: {OUTPUT_FILE}")
    print("💡 Следующий шаг: запустите python step2_analyze.py")
    print("="*60)

if __name__ == "__main__":
    main()

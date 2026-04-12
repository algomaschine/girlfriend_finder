#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Шаг 1: Сбор и фильтрация профилей из сообщества ВКонтакте.

Этот скрипт:
- Получает список участников заданного сообщества
- Фильтрует по полу (женский), семейному положению (свободна)
- Проверяет открытость профиля
- Собирает расширенную информацию о профиле и подписки
- Экспортирует результаты в JSON файл

Выходные данные: filtered_profiles.json
"""

import json
import time
import vk_api
from vk_api.utils import get_random_id


def load_config():
    """Загрузка конфигурации из config.json"""
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def get_vk_session(user_token):
    """Создание сессии VK API"""
    session = vk_api.VkApi(token=user_token)
    return session


def fetch_group_members(session, group_id, count=1000):
    """Получение списка участников сообщества"""
    print(f"Получение участников сообщества {group_id}...")
    
    members = []
    offset = 0
    batch_size = 1000
    
    while True:
        try:
            response = session.method('groups.getMembers', {
                'group_id': group_id,
                'offset': offset,
                'count': min(batch_size, count - offset),
                'fields': 'sex,relation,is_closed'
            })
            
            items = response.get('items', [])
            if not items:
                break
                
            members.extend(items)
            offset += len(items)
            
            print(f"Получено {len(members)} участников...")
            
            if len(members) >= count or len(items) < batch_size:
                break
                
            # Соблюдение лимитов API (3 запроса в секунду)
            time.sleep(0.4)
            
        except vk_api.exceptions.ApiError as e:
            print(f"Ошибка API: {e}")
            break
        except Exception as e:
            print(f"Общая ошибка: {e}")
            break
    
    return members


def filter_profiles(members):
    """Фильтрация профилей по критериям"""
    print("Фильтрация профилей...")
    
    filtered = []
    
    for member in members:
        # Проверка на существование обязательных полей
        if 'sex' not in member or 'relation' not in member:
            continue
            
        # Только женский пол (1)
        if member.get('sex') != 1:
            continue
        
        # Исключаем тех, кто не свободен
        # relation: 0-не указано, 1-не замужем, 2-есть друг, 3-помолвлена, 
        # 4-замужем, 5-в активном поиске, 6-влюблена, 7-влюблена, 8-в гражданском браке
        relation = member.get('relation', 0)
        if relation in [2, 3, 4, 7, 8]:
            continue
        
        # Проверка на закрытость профиля
        if member.get('is_closed', False):
            continue
        
        filtered.append(member)
    
    print(f"Найдено {len(filtered)} подходящих профилей из {len(members)}")
    return filtered


def get_extended_profile(session, user_id):
    """Получение расширенной информации о профиле с проверкой доступности"""
    try:
        response = session.method('users.get', {
            'user_ids': user_id,
            'fields': 'about,activities,interests,music,movies,tv,books,games,status,quotes,personal,city,bdate,education,site,contacts,is_closed,last_seen'
        })
        
        if response:
            profile = response[0]
            
            # ПОВТОРНАЯ проверка на закрытость профиля после получения полных данных
            if profile.get('is_closed', False):
                print(f"   ⚠️ Профиль {user_id} закрыт (пропущен)")
                return None
            
            # Проверка на активность (last_seen)
            last_seen = profile.get('last_seen')
            if last_seen:
                import time
                current_time = int(time.time())
                time_since_seen = current_time - last_seen.get('time', 0)
                days_since_seen = time_since_seen / (24 * 3600)
                
                # Если не был в сети больше 90 дней - считаем неактивным
                if days_since_seen > 90:
                    print(f"   ⚠️ Профиль {user_id} неактивен ({int(days_since_seen)} дн. назад) (пропущен)")
                    return None
            
            return profile
        return None
        
    except vk_api.exceptions.ApiError as e:
        print(f"Ошибка при получении профиля {user_id}: {e}")
        return None
    except Exception as e:
        print(f"Общая ошибка при получении профиля {user_id}: {e}")
        return None


def get_subscriptions(session, user_id, count=20):
    """Получение списка подписок пользователя"""
    try:
        response = session.method('users.getSubscriptions', {
            'user_id': user_id,
            'count': count,
            'extended': 1
        })
        
        groups = response.get('items', [])
        group_names = [g.get('name', 'Unknown') for g in groups]
        return group_names
        
    except vk_api.exceptions.ApiError as e:
        print(f"Ошибка при получении подписок {user_id}: {e}")
        return []
    except Exception as e:
        print(f"Общая ошибка при получении подписок {user_id}: {e}")
        return []


def collect_full_data(session, filtered_members):
    """Сбор полной информации о каждом профиле"""
    print("Сбор расширенной информации о профилях...")
    
    profiles_data = []
    total = len(filtered_members)
    
    for idx, member in enumerate(filtered_members, 1):
        user_id = member.get('id')
        print(f"[{idx}/{total}] Обработка профиля {user_id}...")
        
        # Получаем расширенный профиль
        extended = get_extended_profile(session, user_id)
        if not extended:
            continue
        
        # Получаем подписки
        subscriptions = get_subscriptions(session, user_id)
        
        # Формируем полный профиль для анализа
        profile = {
            'id': user_id,
            'first_name': extended.get('first_name', ''),
            'last_name': extended.get('last_name', ''),
            'screen_name': extended.get('screen_name', f"id{user_id}"),
            'status': extended.get('status', ''),
            'about': extended.get('about', ''),
            'activities': extended.get('activities', ''),
            'interests': extended.get('interests', ''),
            'music': extended.get('music', ''),
            'movies': extended.get('movies', ''),
            'tv': extended.get('tv', ''),
            'books': extended.get('books', ''),
            'games': extended.get('games', ''),
            'quotes': extended.get('quotes', ''),
            'personal': extended.get('personal', {}),
            'city': extended.get('city', {}).get('title', '') if extended.get('city') else '',
            'bdate': extended.get('bdate', ''),
            'education': extended.get('university_name', '') or extended.get('faculty_name', ''),
            'site': extended.get('site', ''),
            'contacts': {
                'mobile_phone': extended.get('mobile_phone', ''),
                'home_phone': extended.get('home_phone', '')
            },
            'subscriptions': subscriptions,
            'relation': extended.get('relation', 0),
            'sex': extended.get('sex', 0)
        }
        
        profiles_data.append(profile)
        
        # Соблюдение лимитов API
        time.sleep(0.4)
    
    return profiles_data


def save_to_json(data, filename='filtered_profiles.json'):
    """Сохранение данных в JSON файл"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Данные сохранены в {filename}")


def main():
    """Основная функция"""
    print("=" * 60)
    print("ШАГ 1: Сбор и фильтрация профилей ВКонтакте")
    print("=" * 60)
    
    # Загрузка конфигурации
    config = load_config()
    user_token = config.get('vk_user_token')
    group_id = config.get('group_id')
    max_profiles = config.get('max_profiles', 1000)
    
    if not user_token:
        print("Ошибка: Не указан vk_user_token в config.json")
        return
    
    if not group_id:
        print("Ошибка: Не указан group_id в config.json")
        return
    
    # Создание сессии
    session = get_vk_session(user_token)
    
    # Получение участников
    members = fetch_group_members(session, group_id, max_profiles)
    
    if not members:
        print("Не удалось получить участников сообщества")
        return
    
    # Фильтрация
    filtered = filter_profiles(members)
    
    if not filtered:
        print("Не найдено подходящих профилей после фильтрации")
        return
    
    # Сбор полной информации
    profiles_data = collect_full_data(session, filtered)
    
    if not profiles_data:
        print("Не удалось собрать данные ни об одном профиле")
        return
    
    # Сохранение результатов
    save_to_json(profiles_data)
    
    print("=" * 60)
    print(f"Готово! Обработано {len(profiles_data)} профилей")
    print("Следующий шаг: запустите step2_analyze.py для психометрического анализа")
    print("=" * 60)


if __name__ == '__main__':
    main()

"""
Steam Profile Parser - Streamlit Web App
========================================
Веб-интерфейс для парсинга Steam профилей

Установка:
  pip install streamlit requests beautifulsoup4 openpyxl pandas

Запуск:
  streamlit run app.py
"""

import streamlit as st
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
import json
import io

# Настройка страницы
st.set_page_config(
    page_title="Steam Profile Parser",
    page_icon="🎮",
    layout="wide"
)

# Стили
st.markdown("""
    <style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    </style>
""", unsafe_allow_html=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
}

# -------------------------
# Sidebar - Настройки
# -------------------------

st.sidebar.title("⚙️ Настройки")

API_KEY = st.sidebar.text_input(
    "Steam Web API Key",
    value="",
    type="password",
    help="Получить можно на https://steamcommunity.com/dev/apikey"
)

delay = st.sidebar.slider(
    "Задержка между профилями (сек)",
    min_value=1,
    max_value=10,
    value=3,
    help="Чем больше задержка, тем меньше шанс получить блокировку от Steam"
)

st.sidebar.markdown("---")
st.sidebar.markdown("""
### 📖 Инструкция
1. Вставьте ссылки на профили (по одной на строку)
2. Нажмите **Начать парсинг**
3. Дождитесь завершения
4. Скачайте Excel файл

### ℹ️ Требования
- Профили должны быть **публичными**
- Нужен валидный **API ключ**
""")

# -------------------------
# Utils & API Functions
# -------------------------

def extract_steamid(profile_url: str) -> str:
    """Получаем SteamID64 из URL профиля"""
    try:
        if "/profiles/" in profile_url:
            return profile_url.rstrip("/").split("/")[-1]

        r = requests.get(profile_url, headers=HEADERS, timeout=10)
        m = re.search(r'"steamid":"(\d+)"', r.text)
        if not m:
            raise ValueError("Не удалось извлечь SteamID")
        return m.group(1)
    except Exception as e:
        raise ValueError(f"Ошибка извлечения SteamID: {e}")


def api_request_with_retry(url, params, max_retries=3):
    """Запрос к API с автоматическими повторами при ошибках"""
    for attempt in range(max_retries):
        try:
            r = requests.get(url, params=params, timeout=15)
            
            if r.status_code == 429:
                wait_time = 30 * (attempt + 1)
                st.warning(f"⏳ Rate limit! Жду {wait_time} секунд...")
                time.sleep(wait_time)
                continue
            
            if r.status_code != 200:
                time.sleep(5)
                continue
                
            return r.json()
            
        except requests.exceptions.Timeout:
            if attempt == max_retries - 1:
                raise
            time.sleep(5)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(5)
    
    raise Exception("Превышено максимальное количество попыток")


def get_profile_summary(steamid):
    url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
    params = {"key": API_KEY, "steamids": steamid}
    r = api_request_with_retry(url, params)

    if not r.get("response", {}).get("players"):
        return None

    p = r["response"]["players"][0]
    time.sleep(0.5)
    return {
        "nickname": p.get("personaname"),
        "avatar": p.get("avatarfull"),
        "country": p.get("loccountrycode"),
        "profile_state": p.get("communityvisibilitystate")
    }


def get_steam_level(steamid):
    url = "https://api.steampowered.com/IPlayerService/GetSteamLevel/v1/"
    params = {"key": API_KEY, "steamid": steamid}
    r = api_request_with_retry(url, params)
    time.sleep(0.5)
    return r.get("response", {}).get("player_level")


def get_games(steamid):
    """Получаем игры через API"""
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": API_KEY,
        "steamid": steamid,
        "include_appinfo": True,
        "include_played_free_games": True
    }
    r = api_request_with_retry(url, params)
    games = r.get("response", {}).get("games", [])
    time.sleep(0.5)

    return [
        {
            "appid": g["appid"],
            "name": g.get("name"),
            "playtime": g.get("playtime_forever", 0)
        }
        for g in games
    ]


def get_games_from_html(profile_url):
    """Парсим полный список игр со страницы профиля"""
    try:
        games_url = profile_url.rstrip('/') + '/games/?tab=all'
        r = requests.get(games_url, headers=HEADERS, timeout=15)
        
        match = re.search(r'var rgGames = (\[.+?\]);', r.text, re.DOTALL)
        if not match:
            return []
        
        games_data = json.loads(match.group(1))
        
        games = []
        for g in games_data:
            games.append({
                "appid": g.get("appid"),
                "name": g.get("name"),
                "playtime": g.get("hours_forever", "0").replace(",", ""),
                "logo": g.get("logo")
            })
        
        time.sleep(0.5)
        return games
    except:
        return []


def get_friends(steamid):
    url = "https://api.steampowered.com/ISteamUser/GetFriendList/v1/"
    params = {"key": API_KEY, "steamid": steamid, "relationship": "friend"}
    try:
        r = api_request_with_retry(url, params)
        time.sleep(0.5)
        return r.get("friendslist", {}).get("friends", [])
    except:
        return []


def get_groups(profile_url):
    try:
        r = requests.get(profile_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        groups = []
        for g in soup.select(".profile_group_links a"):
            groups.append({
                "name": g.get_text(strip=True),
                "url": g.get("href")
            })
        return groups
    except:
        return []


def collect_profile(profile_url):
    steamid = extract_steamid(profile_url)

    summary = get_profile_summary(steamid)
    if not summary or summary["profile_state"] != 3:
        return {"steamid": steamid, "error": "PROFILE_PRIVATE"}

    games = get_games_from_html(profile_url)
    if not games:
        games = get_games(steamid)

    data = {
        "steamid": steamid,
        "profile_url": profile_url,
        "nickname": summary["nickname"],
        "avatar": summary["avatar"],
        "country": summary["country"],
        "level": get_steam_level(steamid),
        "games": games,
        "friends": get_friends(steamid),
        "groups": get_groups(profile_url)
    }

    return data


def create_excel(results):
    """Создаем Excel файл в памяти"""
    output = io.BytesIO()
    
    # Лист 1: Профили
    profiles_data = []
    for r in results:
        if "error" in r:
            profiles_data.append({
                "SteamID": r["steamid"],
                "Статус": r["error"],
                "Никнейм": "-",
                "Страна": "-",
                "Уровень": "-",
                "Кол-во игр": 0,
                "Кол-во друзей": 0,
                "Кол-во групп": 0,
                "URL": r.get("profile_url", "-")
            })
        else:
            profiles_data.append({
                "SteamID": r["steamid"],
                "Статус": "OK",
                "Никнейм": r["nickname"],
                "Страна": r.get("country", "-"),
                "Уровень": r.get("level", 0),
                "Кол-во игр": len(r.get("games", [])),
                "Кол-во друзей": len(r.get("friends", [])),
                "Кол-во групп": len(r.get("groups", [])),
                "URL": r["profile_url"]
            })

    df_profiles = pd.DataFrame(profiles_data)

    # Лист 2: Игры
    games_data = []
    for r in results:
        if "error" not in r:
            for game in r.get("games", []):
                playtime = game.get("playtime", 0)
                if isinstance(playtime, str):
                    try:
                        playtime = float(playtime) * 60
                    except:
                        playtime = 0
                
                games_data.append({
                    "Никнейм": r["nickname"],
                    "SteamID": r["steamid"],
                    "Игра": game["name"],
                    "AppID": game["appid"],
                    "Время (минуты)": int(playtime),
                    "Время (часы)": round(playtime / 60, 1)
                })

    df_games = pd.DataFrame(games_data)

    # Лист 3: Друзья
    friends_data = []
    for r in results:
        if "error" not in r:
            for friend in r.get("friends", []):
                friends_data.append({
                    "Пользователь": r["nickname"],
                    "SteamID пользователя": r["steamid"],
                    "SteamID друга": friend["steamid"],
                    "Дружат с": datetime.fromtimestamp(friend["friend_since"]).strftime("%Y-%m-%d")
                })

    df_friends = pd.DataFrame(friends_data)

    # Лист 4: Группы
    groups_data = []
    for r in results:
        if "error" not in r:
            for group in r.get("groups", []):
                groups_data.append({
                    "Пользователь": r["nickname"],
                    "SteamID": r["steamid"],
                    "Группа": group["name"],
                    "URL группы": group["url"]
                })

    df_groups = pd.DataFrame(groups_data)

    # Запись в Excel
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_profiles.to_excel(writer, sheet_name='Profiles', index=False)
        if not df_games.empty:
            df_games.to_excel(writer, sheet_name='Games', index=False)
        if not df_friends.empty:
            df_friends.to_excel(writer, sheet_name='Friends', index=False)
        if not df_groups.empty:
            df_groups.to_excel(writer, sheet_name='Groups', index=False)

    output.seek(0)
    return output


# -------------------------
# Main Interface
# -------------------------

st.title("🎮 Steam Profile Parser")
st.markdown("Парсинг публичных Steam профилей с сохранением в Excel")

# Поле ввода профилей
profile_input = st.text_area(
    "Введите ссылки на профили (по одной на строку)",
    height=200,
    placeholder="https://steamcommunity.com/profiles/76561199173282872\nhttps://steamcommunity.com/id/username"
)

col1, col2, col3 = st.columns([1, 1, 3])

with col1:
    start_button = st.button("🚀 Начать парсинг", type="primary", use_container_width=True)

with col2:
    if st.button("🗑️ Очистить", use_container_width=True):
        st.rerun()

# Парсинг
if start_button and profile_input:
    profile_urls = [url.strip() for url in profile_input.split('\n') if url.strip()]
    
    if not profile_urls:
        st.error("❌ Введите хотя бы одну ссылку на профиль")
    else:
        st.info(f"📊 Всего профилей для обработки: {len(profile_urls)}")
        
        # Прогресс бар
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        result_container = st.container()
        
        for i, url in enumerate(profile_urls):
            try:
                status_text.text(f"Обработка {i+1}/{len(profile_urls)}: {url}")
                
                profile_data = collect_profile(url)
                results.append(profile_data)
                
                # Показываем результат
                with result_container:
                    if "error" in profile_data:
                        st.error(f"❌ {url} - {profile_data['error']}")
                    else:
                        st.success(f"✅ {profile_data['nickname']} | Игр: {len(profile_data['games'])} | Друзей: {len(profile_data['friends'])}")
                
                # Обновляем прогресс
                progress_bar.progress((i + 1) / len(profile_urls))
                
                # Задержка
                if i < len(profile_urls) - 1:
                    time.sleep(delay)
                    
            except Exception as e:
                with result_container:
                    st.error(f"⚠️ Ошибка при обработке {url}: {str(e)}")
                results.append({"steamid": url, "error": str(e)})
        
        status_text.text("✅ Парсинг завершён!")
        
        # Статистика
        st.markdown("---")
        st.subheader("📈 Статистика")
        
        col1, col2, col3, col4 = st.columns(4)
        
        success_count = len([r for r in results if "error" not in r])
        total_games = sum(len(r.get("games", [])) for r in results if "error" not in r)
        total_friends = sum(len(r.get("friends", [])) for r in results if "error" not in r)
        total_groups = sum(len(r.get("groups", [])) for r in results if "error" not in r)
        
        col1.metric("Успешно обработано", f"{success_count}/{len(profile_urls)}")
        col2.metric("Всего игр", total_games)
        col3.metric("Всего друзей", total_friends)
        col4.metric("Всего групп", total_groups)
        
        # Кнопка скачивания
        if results:
            st.markdown("---")
            excel_file = create_excel(results)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            st.download_button(
                label="📥 Скачать Excel файл",
                data=excel_file,
                file_name=f"steam_data_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

elif start_button:
    st.warning("⚠️ Введите ссылки на профили")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>Made with ❤️ using Streamlit | Steam Web API</p>
</div>
""", unsafe_allow_html=True)
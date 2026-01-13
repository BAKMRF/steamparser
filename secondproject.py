"""
Steam Profile Parser - Streamlit Web App with Multi-page Analytics
==================================================================
Веб-интерфейс для парсинга Steam профилей с многостраничной аналитикой

Установка:
  pip install streamlit requests beautifulsoup4 openpyxl pandas plotly

Запуск:
  streamlit run app.py
"""

import streamlit as st
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
import json
import io
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter

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
        max-width: 1400px;
        margin: 0 auto;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
}

# Инициализация session state
if 'api_key' not in st.session_state:
    st.session_state.api_key = None
if 'api_key_confirmed' not in st.session_state:
    st.session_state.api_key_confirmed = False
if 'parsed_results' not in st.session_state:
    st.session_state.parsed_results = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = "parser"

# Словарь стран для карты
COUNTRY_NAMES = {
    'US': 'United States', 'RU': 'Russia', 'DE': 'Germany', 'GB': 'United Kingdom',
    'FR': 'France', 'CN': 'China', 'JP': 'Japan', 'BR': 'Brazil', 'CA': 'Canada',
    'AU': 'Australia', 'IT': 'Italy', 'ES': 'Spain', 'MX': 'Mexico', 'KR': 'South Korea',
    'NL': 'Netherlands', 'PL': 'Poland', 'SE': 'Sweden', 'NO': 'Norway', 'FI': 'Finland',
    'DK': 'Denmark', 'BE': 'Belgium', 'CH': 'Switzerland', 'AT': 'Austria', 'CZ': 'Czech Republic',
    'UA': 'Ukraine', 'TR': 'Turkey', 'GR': 'Greece', 'PT': 'Portugal', 'HU': 'Hungary',
    'RO': 'Romania', 'BG': 'Bulgaria', 'SK': 'Slovakia', 'HR': 'Croatia', 'SI': 'Slovenia',
    'LT': 'Lithuania', 'LV': 'Latvia', 'EE': 'Estonia', 'IE': 'Ireland', 'NZ': 'New Zealand',
    'SG': 'Singapore', 'MY': 'Malaysia', 'TH': 'Thailand', 'ID': 'Indonesia', 'PH': 'Philippines',
    'VN': 'Vietnam', 'IN': 'India', 'PK': 'Pakistan', 'BD': 'Bangladesh', 'LK': 'Sri Lanka',
    'SA': 'Saudi Arabia', 'AE': 'United Arab Emirates', 'IL': 'Israel', 'EG': 'Egypt',
    'ZA': 'South Africa', 'AR': 'Argentina', 'CL': 'Chile', 'CO': 'Colombia', 'PE': 'Peru',
    'VE': 'Venezuela', 'UY': 'Uruguay', 'EC': 'Ecuador', 'BO': 'Bolivia', 'PY': 'Paraguay'
}

# Координаты стран для карты (широта, долгота)
COUNTRY_COORDINATES = {
    'US': (37.0902, -95.7129), 'RU': (61.5240, 105.3188), 'DE': (51.1657, 10.4515),
    'GB': (55.3781, -3.4360), 'FR': (46.6034, 1.8883), 'CN': (35.8617, 104.1954),
    'JP': (36.2048, 138.2529), 'BR': (-14.2350, -51.9253), 'CA': (56.1304, -106.3468),
    'AU': (-25.2744, 133.7751), 'IT': (41.8719, 12.5674), 'ES': (40.4637, -3.7492),
    'MX': (23.6345, -102.5528), 'KR': (35.9078, 127.7669), 'NL': (52.1326, 5.2913),
    'PL': (51.9194, 19.1451), 'SE': (60.1282, 18.6435), 'NO': (60.4720, 8.4689),
    'FI': (61.9241, 25.7482), 'DK': (56.2639, 9.5018), 'BE': (50.5039, 4.4699),
    'CH': (46.8182, 8.2275), 'AT': (47.5162, 14.5501), 'CZ': (49.8175, 15.4720),
    'UA': (48.3794, 31.1656), 'TR': (38.9637, 35.2433), 'GR': (39.0742, 21.8243),
    'PT': (39.3999, -8.2245), 'HU': (47.1625, 19.5033), 'RO': (45.9432, 24.9668),
    'BG': (42.7339, 25.4858), 'SK': (48.6690, 19.6990), 'HR': (45.1000, 15.2000),
    'SI': (46.1512, 14.9955), 'LT': (55.1694, 23.8813), 'LV': (56.8796, 24.6032),
    'EE': (58.5953, 25.0136), 'IE': (53.1424, -7.6921), 'NZ': (-40.9006, 174.8860),
    'SG': (1.3521, 103.8198), 'MY': (4.2105, 101.9758), 'TH': (15.8700, 100.9925),
    'ID': (-0.7893, 113.9213), 'PH': (12.8797, 121.7740), 'VN': (14.0583, 108.2772),
    'IN': (20.5937, 78.9629), 'PK': (30.3753, 69.3451), 'BD': (23.6850, 90.3563),
    'LK': (7.8731, 80.7718), 'SA': (23.8859, 45.0792), 'AE': (23.4241, 53.8478),
    'IL': (31.0461, 34.8516), 'EG': (26.8206, 30.8025), 'ZA': (-30.5595, 22.9375),
    'AR': (-38.4161, -63.6167), 'CL': (-35.6751, -71.5430), 'CO': (4.5709, -74.2973),
    'PE': (-9.1900, -75.0152), 'VE': (6.4238, -66.5897), 'UY': (-32.5228, -55.7658),
    'EC': (-1.8312, -78.1834), 'BO': (-16.2902, -63.5887), 'PY': (-23.4425, -58.4438)
}

# -------------------------
# Проверка API ключа
# -------------------------

if not st.session_state.api_key_confirmed:
    st.title("🔑 Настройка Steam API Key")
    st.markdown("""
    Для работы парсера необходим **Steam Web API Key**.
    
    ### Как получить API ключ:
    1. Перейдите на [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)
    2. Войдите в свой Steam аккаунт
    3. Заполните форму (Domain Name можно указать `localhost`)
    4. Скопируйте полученный ключ и вставьте ниже
    """)
    
    api_key_input = st.text_input(
        "Введите ваш Steam API Key",
        type="password",
        placeholder="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("✅ Подтвердить", type="primary", use_container_width=True):
            if api_key_input and len(api_key_input) == 32:
                st.session_state.api_key = api_key_input
                st.session_state.api_key_confirmed = True
                st.rerun()
            else:
                st.error("❌ API ключ должен содержать 32 символа")
    
    st.info("💡 **Примечание:** API ключ сохраняется только для текущей сессии")
    st.stop()

API_KEY = st.session_state.api_key

# -------------------------
# Sidebar - Навигация
# -------------------------

st.sidebar.title("🎮 Steam Analytics")

masked_key = API_KEY[:4] + "..." + API_KEY[-4:]
st.sidebar.info(f"🔑 API: `{masked_key}`")

if st.sidebar.button("🔄 Изменить ключ", use_container_width=True):
    st.session_state.api_key_confirmed = False
    st.rerun()

st.sidebar.markdown("---")

# Навигация
st.sidebar.subheader("📄 Страницы")

pages = {
    "parser": {"icon": "🔍", "name": "Парсер"},
    "overview": {"icon": "📊", "name": "Обзор"},
    "geography": {"icon": "🌍", "name": "География"},
    "libraries": {"icon": "📚", "name": "Библиотеки"},
    "games": {"icon": "🎮", "name": "Игры"}
}

for page_id, page_info in pages.items():
    if page_id == "parser" or st.session_state.parsed_results:
        button_type = "primary" if st.session_state.current_page == page_id else "secondary"
        if st.sidebar.button(
            f"{page_info['icon']} {page_info['name']}", 
            use_container_width=True,
            type=button_type
        ):
            st.session_state.current_page = page_id
            st.rerun()

if st.session_state.parsed_results:
    success_count = len([r for r in st.session_state.parsed_results if "error" not in r])
    st.sidebar.success(f"✅ Профилей: {success_count}")

st.sidebar.markdown("---")

# -------------------------
# API Functions
# -------------------------

def extract_steamid(profile_url: str) -> str:
    try:
        if "/profiles/" in profile_url:
            return profile_url.rstrip("/").split("/")[-1]
        r = requests.get(profile_url, headers=HEADERS, timeout=10)
        m = re.search(r'"steamid":"(\d+)"', r.text)
        if not m:
            raise ValueError("Не удалось извлечь SteamID")
        return m.group(1)
    except Exception as e:
        raise ValueError(f"Ошибка: {e}")

def api_request_with_retry(url, params, max_retries=3):
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
        "profile_state": p.get("communityvisibilitystate"),
        "last_logoff": p.get("lastlogoff"),
        "timecreated": p.get("timecreated")
    }

def get_steam_level(steamid):
    url = "https://api.steampowered.com/IPlayerService/GetSteamLevel/v1/"
    params = {"key": API_KEY, "steamid": steamid}
    r = api_request_with_retry(url, params)
    time.sleep(0.5)
    return r.get("response", {}).get("player_level")

def get_games(steamid):
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

def get_recent_playtime(steamid):
    """Получить время игры за последние 2 недели"""
    try:
        url = "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v1/"
        params = {
            "key": API_KEY,
            "steamid": steamid,
            "count": 100  # Максимальное количество игр
        }
        r = api_request_with_retry(url, params)
        games = r.get("response", {}).get("games", [])
        
        total_2weeks = 0
        recent_games = []
        
        for game in games:
            playtime = game.get("playtime_2weeks", 0)
            total_2weeks += playtime
            recent_games.append({
                "name": game.get("name"),
                "playtime_2weeks": playtime,
                "playtime_total": game.get("playtime_forever", 0)
            })
        
        time.sleep(0.5)
        return {
            "total_2weeks_minutes": total_2weeks,
            "total_2weeks_hours": round(total_2weeks / 60, 1),
            "recent_games": recent_games
        }
    except Exception as e:
        return {
            "total_2weeks_minutes": 0,
            "total_2weeks_hours": 0,
            "recent_games": [],
            "error": str(e)
        }

def get_game_prices(appids):
    """Получить цены игр из Steam Store"""
    prices = {}
    
    # Разбиваем на группы по 50 appids для запроса
    for i in range(0, len(appids), 50):
        appids_chunk = appids[i:i+50]
        
        try:
            # Используем Steam Store API
            url = "https://store.steampowered.com/api/appdetails"
            params = {
                "appids": ",".join(map(str, appids_chunk)),
                "filters": "price_overview"
            }
            
            r = requests.get(url, headers=HEADERS, timeout=10)
            data = r.json()
            
            for appid_str, game_data in data.items():
                if game_data and game_data.get("success"):
                    price_data = game_data.get("data", {}).get("price_overview")
                    if price_data:
                        appid = int(appid_str)
                        # Цена в долларах (делим на 100)
                        price_usd = price_data.get("final", 0) / 100
                        prices[appid] = price_usd
            
            time.sleep(1)  # Задержка между запросами
            
        except Exception as e:
            st.warning(f"⚠️ Ошибка при получении цен: {str(e)}")
            continue
    
    return prices

def collect_profile(profile_url):
    steamid = extract_steamid(profile_url)
    summary = get_profile_summary(steamid)
    if not summary or summary["profile_state"] != 3:
        return {"steamid": steamid, "error": "PROFILE_PRIVATE"}
    
    games = get_games_from_html(profile_url)
    if not games:
        games = get_games(steamid)
    
    # Получаем время игры за 2 недели
    recent_data = get_recent_playtime(steamid)
    
    return {
        "steamid": steamid,
        "profile_url": profile_url,
        "nickname": summary["nickname"],
        "avatar": summary["avatar"],
        "country": summary["country"],
        "level": get_steam_level(steamid),
        "games": games,
        "friends": get_friends(steamid),
        "groups": get_groups(profile_url),
        "last_logoff": summary.get("last_logoff"),
        "timecreated": summary.get("timecreated"),
        "recent_playtime": recent_data.get("total_2weeks_hours", 0),
        "recent_games": recent_data.get("recent_games", [])
    }

def create_excel(results):
    output = io.BytesIO()
    profiles_data = []
    for r in results:
        if "error" in r:
            profiles_data.append({
                "SteamID": r["steamid"], "Статус": r["error"], "Никнейм": "-",
                "Страна": "-", "Уровень": "-", "Кол-во игр": 0,
                "Кол-во друзей": 0, "Кол-во групп": 0, "URL": r.get("profile_url", "-"),
                "Часы за 2 недели": 0
            })
        else:
            profiles_data.append({
                "SteamID": r["steamid"], "Статус": "OK", "Никнейм": r["nickname"],
                "Страна": r.get("country", "-"), "Уровень": r.get("level", 0),
                "Кол-во игр": len(r.get("games", [])), "Кол-во друзей": len(r.get("friends", [])),
                "Кол-во групп": len(r.get("groups", [])), "URL": r["profile_url"],
                "Часы за 2 недели": r.get("recent_playtime", 0)
            })
    
    df_profiles = pd.DataFrame(profiles_data)
    
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
                    "Никнейм": r["nickname"], "SteamID": r["steamid"],
                    "Игра": game["name"], "AppID": game["appid"],
                    "Время (минуты)": int(playtime), "Время (часы)": round(playtime / 60, 1)
                })
    
    df_games = pd.DataFrame(games_data)
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_profiles.to_excel(writer, sheet_name='Profiles', index=False)
        if not df_games.empty:
            df_games.to_excel(writer, sheet_name='Games', index=False)
    
    output.seek(0)
    return output

# -------------------------
# PAGE 1: Parser
# -------------------------

def render_parser_page():
    st.title("🔍 Steam Profile Parser")
    st.markdown("Парсинг публичных Steam профилей")
    
    delay = st.slider("⏱️ Задержка между профилями (сек)", 1, 10, 3)
    
    profile_input = st.text_area(
        "Введите ссылки на профили (по одной на строку)",
        height=200,
        placeholder="https://steamcommunity.com/profiles/76561199173282872\nhttps://steamcommunity.com/id/username"
    )
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        start_button = st.button("🚀 Начать парсинг", type="primary", use_container_width=True)
    
    with col2:
        if st.button("🗑️ Очистить", use_container_width=True):
            st.session_state.parsed_results = None
            st.rerun()
    
    if start_button and profile_input:
        profile_urls = [url.strip() for url in profile_input.split('\n') if url.strip()]
        
        if not profile_urls:
            st.error("❌ Введите хотя бы одну ссылку")
        else:
            st.info(f"📊 Профилей для обработки: {len(profile_urls)}")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []
            result_container = st.container()
            
            for i, url in enumerate(profile_urls):
                try:
                    status_text.text(f"Обработка {i+1}/{len(profile_urls)}: {url}")
                    profile_data = collect_profile(url)
                    results.append(profile_data)
                    
                    with result_container:
                        if "error" in profile_data:
                            st.error(f"❌ {url} - {profile_data['error']}")
                        else:
                            st.success(f"✅ {profile_data['nickname']} | Игр: {len(profile_data['games'])} | 2 недели: {profile_data.get('recent_playtime', 0)}ч")
                    
                    progress_bar.progress((i + 1) / len(profile_urls))
                    
                    if i < len(profile_urls) - 1:
                        time.sleep(delay)
                        
                except Exception as e:
                    with result_container:
                        st.error(f"⚠️ Ошибка: {str(e)}")
                    results.append({"steamid": url, "error": str(e)})
            
            status_text.text("✅ Парсинг завершён!")
            st.session_state.parsed_results = results
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                excel_file = create_excel(results)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    "📥 Скачать Excel",
                    data=excel_file,
                    file_name=f"steam_data_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            with col2:
                if st.button("📊 Перейти к аналитике", type="primary", use_container_width=True):
                    st.session_state.current_page = "overview"
                    st.rerun()
    
    elif start_button:
        st.warning("⚠️ Введите ссылки на профили")

# -------------------------
# PAGE 2: Overview
# -------------------------

def render_overview_page():
    st.title("📊 Обзор")
    
    if not st.session_state.parsed_results:
        st.warning("⚠️ Сначала выполните парсинг")
        return
    
    results = [r for r in st.session_state.parsed_results if "error" not in r]
    
    if not results:
        st.error("❌ Нет данных для анализа")
        return
    
    # Основные метрики
    col1, col2, col3, col4 = st.columns(4)
    
    total_games = sum(len(r.get("games", [])) for r in results)
    total_friends = sum(len(r.get("friends", [])) for r in results)
    total_groups = sum(len(r.get("groups", [])) for r in results)
    avg_level = sum(r.get("level", 0) for r in results) / len(results) if results else 0
    
    with col1:
        st.metric("👥 Пользователей", len(results))
    with col2:
        st.metric("🎮 Всего игр", f"{total_games:,}")
    with col3:
        st.metric("👤 Друзей", f"{total_friends:,}")
    with col4:
        st.metric("⭐ Средний уровень", f"{avg_level:.1f}")
    
    st.markdown("---")
    
    # CS2 Analysis
    st.header("🎯 Counter-Strike 2")
    
    cs2_data = []
    CS2_APPIDS = [730, 710]
    
    for profile in results:
        cs2_time = 0
        for game in profile.get('games', []):
            if game['appid'] in CS2_APPIDS:
                playtime = game.get('playtime', 0)
                if isinstance(playtime, str):
                    try:
                        playtime = float(playtime) * 60
                    except:
                        playtime = 0
                cs2_time += playtime
        
        cs2_data.append({
            'nickname': profile['nickname'],
            'hours': round(cs2_time / 60, 1)
        })
    
    cs2_data.sort(key=lambda x: x['hours'], reverse=True)
    df_cs2 = pd.DataFrame(cs2_data)
    
    if df_cs2['hours'].sum() > 0:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            fig_bar = go.Figure(data=[
                go.Bar(
                    x=df_cs2['nickname'],
                    y=df_cs2['hours'],
                    text=df_cs2['hours'],
                    textposition='auto',
                    marker=dict(
                        color=df_cs2['hours'],
                        colorscale='Viridis'
                    )
                )
            ])
            
            fig_bar.update_layout(
                title="Наигранные часы в CS2",
                xaxis_title="Игрок",
                yaxis_title="Часы",
                height=400
            )
            
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with col2:
            st.subheader("🏆 Топ-3")
            for idx, row in df_cs2.head(3).iterrows():
                if idx == 0:
                    st.success(f"🥇 {row['nickname']}: **{row['hours']}** ч")
                elif idx == 1:
                    st.info(f"🥈 {row['nickname']}: **{row['hours']}** ч")
                else:
                    st.warning(f"🥉 {row['nickname']}: **{row['hours']}** ч")
    else:
        st.info("ℹ️ Никто не играл в CS2")

# -------------------------
# PAGE 3: Geography
# -------------------------

def render_geography_page():
    st.title("🌍 География пользователей")
    
    if not st.session_state.parsed_results:
        st.warning("⚠️ Сначала выполните парсинг")
        return
    
    results = [r for r in st.session_state.parsed_results if "error" not in r]
    
    # Подготовка данных для карты
    users_by_country = {}
    for profile in results:
        country_code = profile.get('country')
        if country_code:
            if country_code not in users_by_country:
                users_by_country[country_code] = []
            users_by_country[country_code].append(profile['nickname'])
    
    if not users_by_country:
        st.info("ℹ️ Нет данных о странах")
        return
    
    # Создаем DataFrame для карты с метками
    map_data = []
    for country_code, users in users_by_country.items():
        if country_code in COUNTRY_COORDINATES:
            lat, lon = COUNTRY_COORDINATES[country_code]
            country_name = COUNTRY_NAMES.get(country_code, country_code)
            
            # Создаем всплывающий текст с информацией
            hover_text = f"<b>{country_name}</b><br>Пользователей: {len(users)}"
            
            # Форматируем список пользователей для отображения
            user_list = "<br>".join([f"• {user}" for user in users[:5]])  # Показываем первые 5
            if len(users) > 5:
                user_list += f"<br>...и еще {len(users) - 5}"
            
            map_data.append({
                'country_code': country_code,
                'country_name': country_name,
                'latitude': lat,
                'longitude': lon,
                'user_count': len(users),
                'users': users,
                'hover_text': hover_text + f"<br><br>Пользователи:<br>{user_list}"
            })
    
    df_map = pd.DataFrame(map_data)
    
    # Карта с метками (точками)
    fig_map = go.Figure()
    
    # Добавляем слой хороплета
    fig_map.add_trace(go.Choropleth(
        locations=df_map['country_code'],
        z=df_map['user_count'],
        text=df_map['country_name'],
        colorscale='Viridis',
        showscale=True,
        hoverinfo='text+z',
        name='Пользователи по стране'
    ))
    
    # Добавляем метки пользователей
    fig_map.add_trace(go.Scattergeo(
        lon=df_map['longitude'],
        lat=df_map['latitude'],
        text=df_map['user_count'].astype(str),
        mode='markers+text',
        marker=dict(
            size=df_map['user_count'] * 2 + 10,
            color='red',
            opacity=0.7,
            symbol='circle'
        ),
        textposition='top center',
        textfont=dict(color='white', size=10),
        hovertext=df_map['hover_text'],
        hoverinfo='text',
        name='Метки пользователей'
    ))
    
    # Настройки карты
    fig_map.update_layout(
        title_text='📍 Расположение пользователей Steam',
        geo=dict(
            showframe=False,
            showcoastlines=True,
            projection_type='natural earth',
            landcolor='rgb(243, 243, 243)',
            countrycolor='rgb(204, 204, 204)',
            lakecolor='rgb(255, 255, 255)',
            showocean=True,
            oceancolor='rgb(230, 242, 255)'
        ),
        height=600
    )
    
    st.plotly_chart(fig_map, use_container_width=True)
    
    # Статистика по странам
    st.markdown("---")
    st.header("📊 Подробная статистика по странам")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Гистограмма по странам
        df_sorted = df_map.sort_values('user_count', ascending=True)
        
        fig_bar = px.bar(
            df_sorted,
            y='country_name',
            x='user_count',
            orientation='h',
            title='Количество пользователей по странам',
            color='user_count',
            color_continuous_scale='Viridis'
        )
        
        fig_bar.update_layout(
            height=400,
            yaxis={'categoryorder': 'total ascending'},
            xaxis_title="Количество пользователей",
            yaxis_title="Страна"
        )
        
        st.plotly_chart(fig_bar, use_container_width=True)
    
    with col2:
        st.subheader("🌐 Список стран")
        for _, row in df_map.sort_values('user_count', ascending=False).iterrows():
            percentage = (row['user_count'] / len(results)) * 100
            st.write(f"**{row['country_name']}**: {row['user_count']} ({percentage:.1f}%)")
            
            # Показываем пользователей этой страны
            with st.expander(f"👤 Показать пользователей"):
                for user in row['users']:
                    st.write(f"• {user}")

# -------------------------
# PAGE 4: Libraries
# -------------------------

def render_libraries_page():
    st.title("📚 Библиотеки игр")
    
    if not st.session_state.parsed_results:
        st.warning("⚠️ Сначала выполните парсинг")
        return
    
    results = [r for r in st.session_state.parsed_results if "error" not in r]
    
    # Собираем все appid для получения цен
    st.info("🔄 Получение цен игр из Steam Store...")
    
    all_appids = set()
    for profile in results:
        for game in profile.get('games', []):
            all_appids.add(game['appid'])
    
    # Получаем цены игр
    game_prices = get_game_prices(list(all_appids))
    
    # Размер библиотек и точная стоимость
    library_data = []
    for profile in results:
        games = profile.get('games', [])
        total_hours = 0
        total_price = 0
        
        for game in games:
            playtime = game.get('playtime', 0)
            if isinstance(playtime, str):
                try:
                    playtime = float(playtime) * 60
                except:
                    playtime = 0
            total_hours += playtime
            
            # Добавляем цену игры
            appid = game['appid']
            if appid in game_prices:
                total_price += game_prices[appid]
        
        library_data.append({
            'nickname': profile['nickname'],
            'games_count': len(games),
            'total_hours': round(total_hours / 60, 1),
            'exact_value': round(total_price, 2)
        })
    
    library_data.sort(key=lambda x: x['games_count'], reverse=True)
    df_lib = pd.DataFrame(library_data)
    
    st.header("🎮 Размер библиотек")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_games = go.Figure(data=[
            go.Bar(
                x=df_lib['nickname'],
                y=df_lib['games_count'],
                text=df_lib['games_count'],
                textposition='auto',
                marker=dict(color='#1f77b4')
            )
        ])
        
        fig_games.update_layout(
            title="Количество игр",
            xaxis_title="Игрок",
            yaxis_title="Игр",
            height=400
        )
        
        st.plotly_chart(fig_games, use_container_width=True)
    
    with col2:
        fig_hours = go.Figure(data=[
            go.Bar(
                x=df_lib['nickname'],
                y=df_lib['total_hours'],
                text=df_lib['total_hours'],
                textposition='auto',
                marker=dict(color='#ff7f0e')
            )
        ])
        
        fig_hours.update_layout(
            title="Общее время в играх",
            xaxis_title="Игрок",
            yaxis_title="Часы",
            height=400
        )
        
        st.plotly_chart(fig_hours, use_container_width=True)
    
    # Точная стоимость библиотек
    st.markdown("---")
    st.header("💰 Точная стоимость библиотек")
    
    fig_value = go.Figure(data=[
        go.Bar(
            x=df_lib['nickname'],
            y=df_lib['exact_value'],
            text=['$' + str(val) for val in df_lib['exact_value']],
            textposition='auto',
            marker=dict(
                color=df_lib['exact_value'],
                colorscale='Greens'
            ),
            hovertemplate='<b>%{x}</b><br>Стоимость: $%{y:.2f}<extra></extra>'
        )
    ])
    
    fig_value.update_layout(
        title="Точная стоимость библиотек (данные Steam Store)",
        xaxis_title="Игрок",
        yaxis_title="Стоимость ($)",
        height=400
    )
    
    st.plotly_chart(fig_value, use_container_width=True)
    
    # Статистика по ценам
    total_value_all = df_lib['exact_value'].sum()
    avg_value = df_lib['exact_value'].mean()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("💰 Общая стоимость", f"${total_value_all:,.2f}")
    with col2:
        st.metric("💵 Средняя стоимость", f"${avg_value:,.2f}")
    with col3:
        st.metric("🏆 Самый дорогой аккаунт", 
                 df_lib.loc[df_lib['exact_value'].idxmax(), 'nickname'],
                 f"${df_lib['exact_value'].max():,.2f}")
    
    # Топ-10 самых дорогих библиотек
    st.markdown("---")
    st.header("🏆 Топ-10 самых дорогих библиотек")
    
    df_top10 = df_lib.nlargest(10, 'exact_value')
    
    fig_top10 = px.bar(
        df_top10,
        x='exact_value',
        y='nickname',
        orientation='h',
        text='exact_value',
        color='exact_value',
        color_continuous_scale='Viridis',
        title='Топ-10 самых дорогих библиотек игр'
    )
    
    fig_top10.update_layout(
        xaxis_title="Стоимость ($)",
        yaxis_title="Игрок",
        height=400,
        yaxis={'categoryorder': 'total ascending'}
    )
    
    fig_top10.update_traces(
        texttemplate='$%{text:.2f}',
        textposition='outside'
    )
    
    st.plotly_chart(fig_top10, use_container_width=True)

# -------------------------
# PAGE 5: Games
# -------------------------

def render_games_page():
    st.title("🎮 Анализ игр")
    
    if not st.session_state.parsed_results:
        st.warning("⚠️ Сначала выполните парсинг")
        return
    
    results = [r for r in st.session_state.parsed_results if "error" not in r]
    
    # Собираем все игры
    all_games = {}
    for profile in results:
        for game in profile.get('games', []):
            game_name = game.get('name', 'Unknown')
            playtime = game.get('playtime', 0)
            
            if isinstance(playtime, str):
                try:
                    playtime = float(playtime) * 60
                except:
                    playtime = 0
            
            if game_name in all_games:
                all_games[game_name]['total_time'] += playtime
                all_games[game_name]['players'] += 1
            else:
                all_games[game_name] = {'total_time': playtime, 'players': 1}
    
    # Активность за 2 недели
    st.header("📈 Активность за последние 2 недели")
    
    recent_activity = []
    for profile in results:
        recent_hours = profile.get('recent_playtime', 0)
        recent_activity.append({
            'nickname': profile['nickname'],
            'hours_2weeks': recent_hours,
            'games_count': len(profile.get('games', [])),
            'total_hours': sum(
                float(g.get('playtime', 0)) if isinstance(g.get('playtime'), str) else g.get('playtime', 0) / 60
                for g in profile.get('games', [])
            )
        })
    
    df_recent = pd.DataFrame(recent_activity)
    df_recent = df_recent.sort_values('hours_2weeks', ascending=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        fig_recent = go.Figure(data=[
            go.Bar(
                y=df_recent['nickname'],
                x=df_recent['hours_2weeks'],
                orientation='h',
                text=df_recent['hours_2weeks'],
                textposition='auto',
                marker=dict(
                    color=df_recent['hours_2weeks'],
                    colorscale='RdYlGn',
                    reversescale=False
                ),
                hovertemplate='<b>%{y}</b><br>Часы: %{x:.1f}<extra></extra>'
            )
        ])
        
        fig_recent.update_layout(
            title="Активность за последние 2 недели (часы)",
            xaxis_title="Часы игры",
            yaxis_title="Игрок",
            height=500,
            yaxis={'categoryorder': 'total ascending'}
        )
        
        st.plotly_chart(fig_recent, use_container_width=True)
    
    with col2:
        st.subheader("🏆 Лидеры активности")
        
        df_top_active = df_recent.nlargest(5, 'hours_2weeks')
        
        for i, (_, row) in enumerate(df_top_active.iterrows()):
            if i == 0:
                st.success(f"🥇 **{row['nickname']}**<br>{row['hours_2weeks']} ч")
            elif i == 1:
                st.info(f"🥈 **{row['nickname']}**<br>{row['hours_2weeks']} ч")
            elif i == 2:
                st.warning(f"🥉 **{row['nickname']}**<br>{row['hours_2weeks']} ч")
            else:
                st.write(f"**{row['nickname']}**: {row['hours_2weeks']} ч")
        
        # Статистика по активности
        st.markdown("---")
        st.subheader("📊 Статистика")
        
        total_2weeks = df_recent['hours_2weeks'].sum()
        avg_2weeks = df_recent['hours_2weeks'].mean()
        max_2weeks = df_recent['hours_2weeks'].max()
        
        st.metric("Всего часов", f"{total_2weeks:.1f}")
        st.metric("В среднем на игрока", f"{avg_2weeks:.1f}")
        st.metric("Максимум", f"{max_2weeks:.1f}")
    
    # Анализ недавно сыгранных игр
    st.markdown("---")
    st.header("🎮 Недавно сыгранные игры")
    
    recent_games_data = {}
    for profile in results:
        recent_games = profile.get('recent_games', [])
        for game in recent_games:
            game_name = game.get('name')
            if game_name:
                if game_name not in recent_games_data:
                    recent_games_data[game_name] = {
                        'total_2weeks': 0,
                        'players': 0,
                        'total_overall': 0
                    }
                
                recent_games_data[game_name]['total_2weeks'] += game.get('playtime_2weeks', 0)
                recent_games_data[game_name]['players'] += 1
                recent_games_data[game_name]['total_overall'] += game.get('playtime_total', 0)
    
    if recent_games_data:
        # Топ игр за 2 недели
        top_recent_games = sorted(
            recent_games_data.items(),
            key=lambda x: x[1]['total_2weeks'],
            reverse=True
        )[:10]
        
        df_top_recent = pd.DataFrame([
            {
                'game': game,
                'hours_2weeks': round(data['total_2weeks'] / 60, 1),
                'players': data['players'],
                'hours_total': round(data['total_overall'] / 60, 1)
            }
            for game, data in top_recent_games
        ])
        
        fig_recent_games = go.Figure(data=[
            go.Bar(
                y=df_top_recent['game'],
                x=df_top_recent['hours_2weeks'],
                orientation='h',
                text=df_top_recent['hours_2weeks'],
                textposition='auto',
                marker=dict(color='#9b59b6'),
                customdata=df_top_recent[['players', 'hours_total']],
                hovertemplate='<b>%{y}</b><br>Часы (2 недели): %{x:.1f}<br>Игроков: %{customdata[0]}<br>Всего часов: %{customdata[1]:.1f}<extra></extra>'
            )
        ])
        
        fig_recent_games.update_layout(
            title="Топ-10 игр по времени за последние 2 недели",
            xaxis_title="Часы",
            yaxis_title="Игра",
            height=500,
            yaxis={'categoryorder': 'total ascending'}
        )
        
        st.plotly_chart(fig_recent_games, use_container_width=True)
    else:
        st.info("ℹ️ Нет данных о недавно сыгранных играх")
    
    # Топ игр по общему времени
    st.markdown("---")
    st.header("⏱️ Топ-10 игр по общему времени")
    
    top_time = sorted(all_games.items(), key=lambda x: x[1]['total_time'], reverse=True)[:10]
    df_time = pd.DataFrame([
        {
            'game': game,
            'hours': round(data['total_time'] / 60, 1),
            'players': data['players']
        }
        for game, data in top_time
    ])
    
    fig_time = go.Figure(data=[
        go.Bar(
            y=df_time['game'],
            x=df_time['hours'],
            orientation='h',
            text=df_time['hours'],
            textposition='auto',
            marker=dict(color='#2ecc71'),
            customdata=df_time['players'],
            hovertemplate='<b>%{y}</b><br>Время: %{x} ч<br>Игроков: %{customdata}<extra></extra>'
        )
    ])
    
    fig_time.update_layout(
        xaxis_title="Часы",
        yaxis_title="Игра",
        height=500,
        yaxis={'categoryorder': 'total ascending'}
    )
    
    st.plotly_chart(fig_time, use_container_width=True)

# -------------------------
# Router
# -------------------------

if st.session_state.current_page == "parser":
    render_parser_page()
elif st.session_state.current_page == "overview":
    render_overview_page()
elif st.session_state.current_page == "geography":
    render_geography_page()
elif st.session_state.current_page == "libraries":
    render_libraries_page()
elif st.session_state.current_page == "games":
    render_games_page()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>Made with ❤️ using Streamlit | Steam Web API</p>
</div>
""", unsafe_allow_html=True)
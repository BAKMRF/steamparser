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
from datetime import datetime
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

def collect_profile(profile_url):
    steamid = extract_steamid(profile_url)
    summary = get_profile_summary(steamid)
    if not summary or summary["profile_state"] != 3:
        return {"steamid": steamid, "error": "PROFILE_PRIVATE"}
    
    games = get_games_from_html(profile_url)
    if not games:
        games = get_games(steamid)
    
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
        "timecreated": summary.get("timecreated")
    }

def create_excel(results):
    output = io.BytesIO()
    profiles_data = []
    for r in results:
        if "error" in r:
            profiles_data.append({
                "SteamID": r["steamid"], "Статус": r["error"], "Никнейм": "-",
                "Страна": "-", "Уровень": "-", "Кол-во игр": 0,
                "Кол-во друзей": 0, "Кол-во групп": 0, "URL": r.get("profile_url", "-")
            })
        else:
            profiles_data.append({
                "SteamID": r["steamid"], "Статус": "OK", "Никнейм": r["nickname"],
                "Страна": r.get("country", "-"), "Уровень": r.get("level", 0),
                "Кол-во игр": len(r.get("games", [])), "Кол-во друзей": len(r.get("friends", [])),
                "Кол-во групп": len(r.get("groups", [])), "URL": r["profile_url"]
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
                            st.success(f"✅ {profile_data['nickname']} | Игр: {len(profile_data['games'])}")
                    
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
    
    countries = [r.get('country') for r in results if r.get('country')]
    
    if not countries:
        st.info("ℹ️ Нет данных о странах")
        return
    
    country_counts = Counter(countries)
    
    # Карта мира
    df_map = pd.DataFrame([
        {
            'country': COUNTRY_NAMES.get(code, code),
            'code': code,
            'count': count
        }
        for code, count in country_counts.items()
    ])
    
    fig_map = px.choropleth(
        df_map,
        locations='code',
        locationmode='ISO-3',
        color='count',
        hover_name='country',
        hover_data={'code': False, 'count': True},
        color_continuous_scale='Viridis',
        title='Распределение пользователей по миру'
    )
    
    fig_map.update_layout(
        height=500,
        geo=dict(
            showframe=False,
            showcoastlines=True,
            projection_type='natural earth'
        )
    )
    
    st.plotly_chart(fig_map, use_container_width=True)
    
    # Статистика по странам
    st.markdown("---")
    st.header("📊 Топ стран")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        df_countries = pd.DataFrame([
            {'Страна': COUNTRY_NAMES.get(code, code), 'Пользователей': count}
            for code, count in country_counts.most_common()
        ])
        
        fig_bar = px.bar(
            df_countries,
            x='Пользователей',
            y='Страна',
            orientation='h',
            title='Количество пользователей по странам'
        )
        
        fig_bar.update_layout(height=400, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)
    
    with col2:
        st.subheader("🌐 Список")
        for country, count in country_counts.most_common():
            country_name = COUNTRY_NAMES.get(country, country)
            percentage = (count / len(results)) * 100
            st.write(f"**{country_name}**: {count} ({percentage:.1f}%)")

# -------------------------
# PAGE 4: Libraries
# -------------------------

def render_libraries_page():
    st.title("📚 Библиотеки игр")
    
    if not st.session_state.parsed_results:
        st.warning("⚠️ Сначала выполните парсинг")
        return
    
    results = [r for r in st.session_state.parsed_results if "error" not in r]
    
    # Размер библиотек
    library_data = []
    for profile in results:
        games = profile.get('games', [])
        total_hours = 0
        
        for game in games:
            playtime = game.get('playtime', 0)
            if isinstance(playtime, str):
                try:
                    playtime = float(playtime) * 60
                except:
                    playtime = 0
            total_hours += playtime
        
        library_data.append({
            'nickname': profile['nickname'],
            'games_count': len(games),
            'total_hours': round(total_hours / 60, 1)
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
    
    # Примерная стоимость
    st.markdown("---")
    st.header("💰 Примерная стоимость библиотек")
    st.info("💡 Средняя цена игры принята за $15")
    
    df_lib['estimated_value'] = df_lib['games_count'] * 15
    
    fig_value = go.Figure(data=[
        go.Bar(
            x=df_lib['nickname'],
            y=df_lib['estimated_value'],
            text=['$' + str(val) for val in df_lib['estimated_value']],
            textposition='auto',
            marker=dict(
                color=df_lib['estimated_value'],
                colorscale='Greens'
            )
        )
    ])
    
    fig_value.update_layout(
        title="Примерная стоимость библиотек",
        xaxis_title="Игрок",
        yaxis_title="Стоимость ($)",
        height=400
    )
    
    st.plotly_chart(fig_value, use_container_width=True)
    
    # Топ владельцев
    col1, col2, col3 = st.columns(3)
    
    top_games = df_lib.iloc[0]
    top_hours = df_lib.nlargest(1, 'total_hours').iloc[0]
    top_value = df_lib.nlargest(1, 'estimated_value').iloc[0]
    
    with col1:
        st.metric("🏆 Больше всего игр", top_games['nickname'], f"{top_games['games_count']} игр")
    with col2:
        st.metric("⏱️ Больше всего часов", top_hours['nickname'], f"{top_hours['total_hours']} ч")
    with col3:
        st.metric("💎 Самая дорогая", top_value['nickname'], f"${top_value['estimated_value']}")

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
    
    # Топ игр по времени
    st.header("⏱️ Топ-10 игр по времени")
    
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
    
    # Топ популярных игр
    st.markdown("---")
    st.header("👥 Топ-10 популярных игр")
    st.caption("Игры, в которые играет больше всего человек")
    
    top_popular = sorted(all_games.items(), key=lambda x: x[1]['players'], reverse=True)[:10]
    df_popular = pd.DataFrame([
        {
            'game': game,
            'players': data['players'],
            'percentage': round((data['players'] / len(results)) * 100, 1)
        }
        for game, data in top_popular
    ])
    
    fig_popular = go.Figure(data=[
        go.Bar(
            y=df_popular['game'],
            x=df_popular['players'],
            orientation='h',
            text=[f"{p} ({pct}%)" for p, pct in zip(df_popular['players'], df_popular['percentage'])],
            textposition='auto',
            marker=dict(color='#e74c3c')
        )
    ])
    
    fig_popular.update_layout(
        xaxis_title="Игроков",
        yaxis_title="Игра",
        height=500,
        yaxis={'categoryorder': 'total ascending'}
    )
    
    st.plotly_chart(fig_popular, use_container_width=True)
    
    # Активность пользователей
    st.markdown("---")
    st.header("📈 Активность пользователей")
    
    activity_data = []
    for profile in results:
        last_logoff = profile.get('last_logoff')
        if last_logoff:
            days_ago = (datetime.now().timestamp() - last_logoff) / 86400
            activity_data.append({
                'nickname': profile['nickname'],
                'days_ago': round(days_ago, 1),
                'status': 'Активен' if days_ago < 7 else 'Неактивен' if days_ago > 30 else 'Умеренно активен'
            })
    
    if activity_data:
        df_activity = pd.DataFrame(activity_data)
        df_activity = df_activity.sort_values('days_ago')
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            fig_activity = go.Figure(data=[
                go.Bar(
                    y=df_activity['nickname'],
                    x=df_activity['days_ago'],
                    orientation='h',
                    text=df_activity['days_ago'],
                    textposition='auto',
                    marker=dict(
                        color=df_activity['days_ago'],
                        colorscale='RdYlGn',
                        reversescale=True
                    )
                )
            ])
            
            fig_activity.update_layout(
                title="Дней с последней активности",
                xaxis_title="Дней",
                yaxis_title="Игрок",
                height=400,
                yaxis={'categoryorder': 'total ascending'}
            )
            
            st.plotly_chart(fig_activity, use_container_width=True)
        
        with col2:
            st.subheader("📊 Статус")
            status_counts = df_activity['status'].value_counts()
            
            for status, count in status_counts.items():
                if status == 'Активен':
                    st.success(f"✅ {status}: {count}")
                elif status == 'Неактивен':
                    st.error(f"❌ {status}: {count}")
                else:
                    st.warning(f"⚠️ {status}: {count}")
    else:
        st.info("ℹ️ Нет данных об активности")

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
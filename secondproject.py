"""
Steam Profile Parser - Streamlit Web App with Analytics
=======================================================
Веб-интерфейс для парсинга Steam профилей с аналитикой

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

# Инициализация session state
if 'api_key' not in st.session_state:
    st.session_state.api_key = None
if 'api_key_confirmed' not in st.session_state:
    st.session_state.api_key_confirmed = False
if 'parsed_results' not in st.session_state:
    st.session_state.parsed_results = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = "parser"

# -------------------------
# Проверка API ключа при первом входе
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
    
    st.info("💡 **Примечание:** API ключ сохраняется только для текущей сессии и не передается третьим лицам")
    st.stop()

# API ключ подтвержден - устанавливаем глобальную переменную
API_KEY = st.session_state.api_key

# -------------------------
# Sidebar - Навигация
# -------------------------

st.sidebar.title("🎮 Steam Parser")

# Показываем замаскированный API ключ
masked_key = API_KEY[:4] + "..." + API_KEY[-4:]
st.sidebar.info(f"🔑 API Key: `{masked_key}`")

if st.sidebar.button("🔄 Изменить API ключ", use_container_width=True):
    st.session_state.api_key_confirmed = False
    st.rerun()

st.sidebar.markdown("---")

# Навигация между страницами
st.sidebar.subheader("📄 Навигация")

if st.sidebar.button("🔍 Парсер профилей", use_container_width=True, 
                     type="primary" if st.session_state.current_page == "parser" else "secondary"):
    st.session_state.current_page = "parser"
    st.rerun()

# Показываем кнопку аналитики только если есть данные
if st.session_state.parsed_results:
    if st.sidebar.button("📊 Аналитика и графики", use_container_width=True,
                         type="primary" if st.session_state.current_page == "analytics" else "secondary"):
        st.session_state.current_page = "analytics"
        st.rerun()
    
    st.sidebar.success(f"✅ Загружено профилей: {len(st.session_state.parsed_results)}")

st.sidebar.markdown("---")

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
# PAGE 1: Parser
# -------------------------

def render_parser_page():
    st.title("🎮 Steam Profile Parser")
    st.markdown("Парсинг публичных Steam профилей с сохранением в Excel")

    # Настройки парсинга
    delay = st.slider(
        "⏱️ Задержка между профилями (секунды)",
        min_value=1,
        max_value=10,
        value=3,
        help="Чем больше задержка, тем меньше шанс получить блокировку от Steam"
    )

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
            st.session_state.parsed_results = None
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
            
            # Сохраняем результаты в session state
            st.session_state.parsed_results = results
            
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
            
            # Кнопки действий
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                # Кнопка скачивания
                if results:
                    excel_file = create_excel(results)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    st.download_button(
                        label="📥 Скачать Excel файл",
                        data=excel_file,
                        file_name=f"steam_data_{timestamp}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="secondary",
                        use_container_width=True
                    )
            
            with col2:
                # Кнопка перехода к аналитике
                if st.button("📊 Перейти к аналитике", type="primary", use_container_width=True):
                    st.session_state.current_page = "analytics"
                    st.rerun()

    elif start_button:
        st.warning("⚠️ Введите ссылки на профили")


# -------------------------
# PAGE 2: Analytics
# -------------------------

def render_analytics_page():
    st.title("📊 Аналитика Steam профилей")
    
    if not st.session_state.parsed_results:
        st.warning("⚠️ Нет данных для анализа. Сначала выполните парсинг профилей.")
        if st.button("← Вернуться к парсеру"):
            st.session_state.current_page = "parser"
            st.rerun()
        return
    
    results = st.session_state.parsed_results
    successful_results = [r for r in results if "error" not in r]
    
    if not successful_results:
        st.error("❌ Нет успешно спарсенных профилей для анализа")
        return
    
    st.markdown("---")
    
    # CS2 Analysis
    st.header("🎯 Сравнение по Counter-Strike 2")
    
    cs2_data = []
    CS2_APPIDS = [730, 710]  # CS:GO и CS2
    
    for profile in successful_results:
        nickname = profile['nickname']
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
            'nickname': nickname,
            'hours': round(cs2_time / 60, 1),
            'minutes': int(cs2_time)
        })
    
    # Сортируем по часам
    cs2_data.sort(key=lambda x: x['hours'], reverse=True)
    df_cs2 = pd.DataFrame(cs2_data)
    
    if df_cs2['hours'].sum() == 0:
        st.info("ℹ️ Ни у кого из пользователей не найдено времени в Counter-Strike 2")
    else:
        # График 1: Столбчатая диаграмма
        fig_bar = go.Figure(data=[
            go.Bar(
                x=df_cs2['nickname'],
                y=df_cs2['hours'],
                text=df_cs2['hours'],
                textposition='auto',
                marker=dict(
                    color=df_cs2['hours'],
                    colorscale='Viridis',
                    showscale=False
                )
            )
        ])
        
        fig_bar.update_layout(
            title="⏱️ Наигранные часы в CS2",
            xaxis_title="Игрок",
            yaxis_title="Часы",
            height=500,
            showlegend=False
        )
        
        st.plotly_chart(fig_bar, use_container_width=True)
        
        # График 2: Круговая диаграмма
        col1, col2 = st.columns(2)
        
        with col1:
            fig_pie = go.Figure(data=[
                go.Pie(
                    labels=df_cs2['nickname'],
                    values=df_cs2['hours'],
                    hole=0.3,
                    textinfo='label+percent',
                    marker=dict(colors=px.colors.qualitative.Set3)
                )
            ])
            
            fig_pie.update_layout(
                title="📊 Распределение времени в CS2",
                height=400
            )
            
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # Таблица с рейтингом
            st.subheader("🏆 Топ игроков")
            
            for idx, row in df_cs2.iterrows():
                if idx == 0:
                    st.success(f"🥇 {row['nickname']}: **{row['hours']}** часов")
                elif idx == 1:
                    st.info(f"🥈 {row['nickname']}: **{row['hours']}** часов")
                elif idx == 2:
                    st.warning(f"🥉 {row['nickname']}: **{row['hours']}** часов")
                else:
                    st.write(f"{idx + 1}. {row['nickname']}: **{row['hours']}** часов")
    
    # Дополнительная статистика
    st.markdown("---")
    st.header("📈 Общая статистика")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_cs2_hours = df_cs2['hours'].sum()
        st.metric("Общее время в CS2", f"{total_cs2_hours:,.1f} часов")
    
    with col2:
        avg_cs2_hours = df_cs2['hours'].mean()
        st.metric("Среднее время", f"{avg_cs2_hours:,.1f} часов")
    
    with col3:
        max_cs2_hours = df_cs2['hours'].max()
        st.metric("Максимум", f"{max_cs2_hours:,.1f} часов")
    
    # Топ игр среди всех пользователей
    st.markdown("---")
    st.header("🎮 Топ-10 самых популярных игр")
    
    all_games = {}
    for profile in successful_results:
        for game in profile.get('games', []):
            game_name = game.get('name', 'Unknown')
            playtime = game.get('playtime', 0)
            
            if isinstance(playtime, str):
                try:
                    playtime = float(playtime) * 60
                except:
                    playtime = 0
            
            if game_name in all_games:
                all_games[game_name] += playtime
            else:
                all_games[game_name] = playtime
    
    # Сортируем и берем топ-10
    top_games = sorted(all_games.items(), key=lambda x: x[1], reverse=True)[:10]
    
    if top_games:
        df_top_games = pd.DataFrame([
            {'game': game, 'hours': round(hours / 60, 1)}
            for game, hours in top_games
        ])
        
        fig_top = go.Figure(data=[
            go.Bar(
                y=df_top_games['game'],
                x=df_top_games['hours'],
                orientation='h',
                text=df_top_games['hours'],
                textposition='auto',
                marker=dict(color='#1f77b4')
            )
        ])
        
        fig_top.update_layout(
            title="Игры с наибольшим общим временем",
            xaxis_title="Часы",
            yaxis_title="Игра",
            height=500,
            yaxis={'categoryorder': 'total ascending'}
        )
        
        st.plotly_chart(fig_top, use_container_width=True)


# -------------------------
# Main Router
# -------------------------

if st.session_state.current_page == "parser":
    render_parser_page()
elif st.session_state.current_page == "analytics":
    render_analytics_page()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>Made with ❤️ using Streamlit | Steam Web API</p>
</div>
""", unsafe_allow_html=True)
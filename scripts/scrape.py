import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime, timezone

BASE_URL = "https://m-league.jp"
API_URL = f"{BASE_URL}/api/mleague/data?kind=games"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "data")
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "images", "players")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")

SEASON_START = "2026-09-15"  # 今シーズンの開始日（これ以降のデータのみ保存）
STATS_URL = f"{BASE_URL}/stats/"
STATS_FILE = os.path.join(DATA_DIR, "stats.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def load_results():
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_results(data):
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_score(text):
    """'57.4pt' や '▲15.4pt' をfloatに変換"""
    text = text.strip().replace("pt", "").replace("▲", "-").replace(",", "").replace("▲", "-")
    try:
        return float(text)
    except ValueError:
        return 0.0


def parse_date_from_modal(modal_id, date_text):
    """
    modal_id: "key20260302-135" -> 2026-03-02
    date_text: "3/2" (バックアップ用)
    """
    m = re.match(r"key(\d{4})(\d{2})(\d{2})-", modal_id)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # フォールバック: date_textから推定
    m2 = re.search(r"(\d+)/(\d+)", date_text)
    if m2:
        month, day = int(m2.group(1)), int(m2.group(2))
        now = datetime.now()
        year = now.year if month >= 9 else now.year
        if now.month < 9 and month >= 9:
            year = now.year - 1
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def download_player_image(player_name, img_src):
    """選手顔写真を保存（未保存の場合のみ）"""
    if not player_name:
        return None
    safe_name = re.sub(r"[^\w぀-ゟ゠-ヿ一-鿿]", "_", player_name)
    filepath = os.path.join(IMAGES_DIR, f"{safe_name}.png")
    if os.path.exists(filepath):
        return f"images/players/{safe_name}.png"
    if not img_src:
        return None
    url = img_src if img_src.startswith("http") else BASE_URL + img_src
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(r.content)
            print(f"  画像保存: {player_name}")
            return f"images/players/{safe_name}.png"
    except Exception as e:
        print(f"  画像取得失敗 {player_name}: {e}")
    return None


def parse_column(column_el, date, round_num):
    """p-gamesResult__column要素から1回戦分のデータをパース"""
    rank_list = column_el.find("ol", class_="p-gamesResult__rank-list")
    if not rank_list:
        return None

    players = []
    for li in rank_list.find_all("li"):
        item = li.find(class_="p-gamesResult__rank-item")
        if not item:
            continue

        # 順位
        badge = item.find(class_=re.compile(r"p-gamesResult__rank-badge"))
        rank = int(badge.get_text(strip=True)) if badge else len(players) + 1

        # 選手名
        name_el = item.find(class_="p-gamesResult__name")
        player_name = name_el.get_text(strip=True) if name_el else ""

        # スコア
        point_el = item.find(class_="p-gamesResult__point")
        score_text = point_el.get_text(strip=True) if point_el else "0"
        score = parse_score(score_text)

        # 顔写真
        thumb = item.find(class_="p-gamesResult__thumbnail")
        img = thumb.find("img") if thumb else None
        img_src = img.get("src") if img else None
        image_path = download_player_image(player_name, img_src) if player_name else None

        players.append({
            "rank": rank,
            "player": player_name,
            "score": score,
            "image": image_path
        })

    if len(players) < 4 or not any(p["player"] for p in players):
        return None

    return {
        "date": date,
        "round": round_num,
        "players": players
    }


def scrape_games():
    print(f"APIスクレイピング開始: {API_URL}")
    resp = requests.get(API_URL, headers=HEADERS, timeout=30)
    api_data = resp.json()

    games = api_data.get("games", [])
    print(f"取得試合数（API）: {len(games)}")

    results = load_results()
    existing_keys = {f"{m['date']}-{m['round']}" for m in results["matches"]}

    # 同日の試合に通し番号を振る
    date_round_counter = {}
    new_count = 0

    for game in games:
        if not game.get("complete"):
            continue

        # UTC→JST日付
        date_str = game["date"][:10]  # "2026-09-13T15:00:00.000Z" → "2026-09-13"
        # UTCの15:00以降はJSTで翌日になるため+1日
        from datetime import timedelta
        dt_utc = datetime.fromisoformat(game["date"].replace("Z", "+00:00"))
        dt_jst = dt_utc + timedelta(hours=9)
        date = dt_jst.strftime("%Y-%m-%d")

        if date < SEASON_START:
            continue

        date_round_counter[date] = date_round_counter.get(date, 0) + 1
        round_num = date_round_counter[date]
        key = f"{date}-{round_num}"
        if key in existing_keys:
            continue

        players = []
        for p in game.get("players", []):
            name = p.get("name", "").replace(" ", "").replace("　", "")
            img_src = p.get("image")
            image_path = download_player_image(name, img_src) if name else None
            players.append({
                "rank": p.get("rank", 0),
                "player": name,
                "score": float(p.get("point", 0)),
                "image": image_path
            })

        if len(players) < 4:
            continue

        results["matches"].append({
            "date": date,
            "round": round_num,
            "players": players
        })
        existing_keys.add(key)
        new_count += 1
        print(f"  追加: {date} 第{round_num}回戦 {[p['player'] for p in players]}")

    if new_count > 0:
        results["matches"].sort(key=lambda m: (m["date"], m["round"]))
        save_results(results)
        print(f"新規追加: {new_count}試合")
    else:
        print("新しいデータなし（既に最新、または試合なし）")

    return new_count


def parse_stat_value(text):
    text = text.strip()
    try:
        return float(text)
    except ValueError:
        return text


def scrape_stats():
    print(f"成績表スクレイピング開始: {STATS_URL}")
    resp = requests.get(STATS_URL, headers=HEADERS, timeout=30)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    players = {}

    for team_el in soup.find_all(class_="p-stats__team"):
        team_name_el = team_el.find(class_="p-stats__teamName")
        table = team_el.find(class_="p-stats__table")
        if not team_name_el or not table:
            continue

        rows = table.find_all("tr")
        if not rows:
            continue

        # 1行目: 選手名
        header_row = rows[0]
        player_names = [th.get_text(strip=True) for th in header_row.find_all("th", scope="col")]
        # スペース除去して正規化（"石井 一馬" → "石井一馬"）
        normalized_names = [n.replace(" ", "").replace("　", "") for n in player_names]

        # 選手ごとに辞書初期化
        for name in normalized_names:
            if name and name not in players:
                players[name] = {}

        # 2行目以降: 各統計
        for row in rows[1:]:
            label_el = row.find("th", scope="row")
            if not label_el:
                continue
            label = label_el.get_text(strip=True)
            cells = row.find_all("td")
            for i, cell in enumerate(cells):
                if i < len(normalized_names) and normalized_names[i]:
                    players[normalized_names[i]][label] = parse_stat_value(cell.get_text(strip=True))

    data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "players": players
    }
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"成績表保存完了: {len(players)}選手")


if __name__ == "__main__":
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    scrape_games()
    scrape_stats()

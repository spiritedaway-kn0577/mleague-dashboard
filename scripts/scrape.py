import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime

BASE_URL = "https://m-league.jp"
GAMES_URL = f"{BASE_URL}/games"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "data")
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "images", "players")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")

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
    print(f"スクレイピング開始: {GAMES_URL}")
    resp = requests.get(GAMES_URL, headers=HEADERS, timeout=30)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    results = load_results()
    existing_keys = {f"{m['date']}-{m['round']}" for m in results["matches"]}

    new_count = 0

    # js-modal-key{YYYYMMDD}-{ID} のdivを全て取得
    modals = soup.find_all("div", id=re.compile(r"^js-modal-key\d{8}-\d+$"))
    print(f"試合モーダル数: {len(modals)}")

    for modal in modals:
        modal_id = modal["id"].replace("js-modal-", "")  # "key20260302-135"

        # 日付取得
        date_el = modal.find(class_="p-gamesResult__date")
        date_text = date_el.get_text(strip=True) if date_el else ""
        date = parse_date_from_modal(modal_id, date_text)
        if not date:
            continue

        # 回戦ごとにカラムを処理
        columns = modal.find_all(class_="p-gamesResult__column")
        for round_num, col in enumerate(columns, start=1):
            key = f"{date}-{round_num}"
            if key in existing_keys:
                continue

            match_data = parse_column(col, date, round_num)
            if match_data:
                results["matches"].append(match_data)
                existing_keys.add(key)
                new_count += 1
                print(f"  追加: {date} 第{round_num}回戦 {[p['player'] for p in match_data['players']]}")

    if new_count > 0:
        results["matches"].sort(key=lambda m: (m["date"], m["round"]))
        save_results(results)
        print(f"新規追加: {new_count}試合")
    else:
        print("新しいデータなし（既に最新、または試合なし）")

    return new_count


if __name__ == "__main__":
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    scrape_games()

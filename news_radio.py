"""
Daily Star News Radio
======================
Daily Star থেকে খবর নিয়ে MP3 বানায়।
GitHub Actions প্রতি ঘণ্টায় এটা চালাবে।
"""

import requests
from bs4 import BeautifulSoup
from gtts import gTTS
from pydub import AudioSegment
import os
import json
import re
from datetime import datetime

# ================================
# কনফিগারেশন
# ================================
NEWS_URL = "https://www.thedailystar.net/news/bangladesh"
OUTPUT_DIR = "audio"
PLAYLIST_FILE = "playlist.json"
MAX_NEWS = 10          # কতটা নিউজ নেবে
MAX_CHARS = 800        # প্রতি নিউজে সর্বোচ্চ কতটা অক্ষর পড়বে

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ================================
# ১. Daily Star থেকে নিউজ স্ক্র্যাপ
# ================================
def scrape_daily_star():
    print("📰 Daily Star থেকে নিউজ নামানো হচ্ছে...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        res = requests.get(NEWS_URL, headers=headers, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"❌ সাইট থেকে ডেটা আনতে সমস্যা: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    articles = []

    # Daily Star এর আর্টিকেল কার্ড খোঁজো
    cards = soup.select("article, .card, h3 a, h2 a")[:MAX_NEWS * 2]

    seen_urls = set()
    for card in cards:
        try:
            # লিংক বের করো
            link_tag = card if card.name == "a" else card.find("a")
            if not link_tag:
                continue

            href = link_tag.get("href", "")
            if not href or href in seen_urls:
                continue

            # পূর্ণ URL বানাও
            if href.startswith("/"):
                href = "https://www.thedailystar.net" + href
            if "thedailystar.net" not in href:
                continue

            seen_urls.add(href)

            # শিরোনাম
            title = link_tag.get_text(strip=True)
            if len(title) < 10:
                continue

            articles.append({"title": title, "url": href})

            if len(articles) >= MAX_NEWS:
                break

        except Exception:
            continue

    print(f"✅ {len(articles)} টি নিউজ পাওয়া গেছে।")
    return articles


# ================================
# ২. আর্টিকেলের মূল লেখা বের করো
# ================================
def get_article_text(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        # মূল কন্টেন্ট এলাকা
        content_div = (
            soup.find("div", class_=re.compile(r"article|content|body|story", re.I))
            or soup.find("article")
        )

        if content_div:
            paragraphs = content_div.find_all("p")
        else:
            paragraphs = soup.find_all("p")

        text = " ".join(
            p.get_text(strip=True)
            for p in paragraphs
            if len(p.get_text(strip=True)) > 40
        )

        return text[:MAX_CHARS] if text else None

    except Exception as e:
        print(f"  ⚠️ লেখা পড়তে সমস্যা: {e}")
        return None


# ================================
# ৩. টেক্সট → MP3
# ================================
def make_mp3(text, filename):
    try:
        tts = gTTS(text=text, lang="en", slow=False)
        filepath = os.path.join(OUTPUT_DIR, filename)
        tts.save(filepath)
        return filepath
    except Exception as e:
        print(f"  ❌ MP3 তৈরিতে সমস্যা: {e}")
        return None


# ================================
# ৪. Intro জিঙ্গেল তৈরি
# ================================
def make_intro():
    now = datetime.utcnow().strftime("%B %d, %Y, %I %p UTC")
    intro_text = (
        f"Welcome to Daily Star Radio. "
        f"Here are the latest news headlines for {now}. "
        f"Stay informed, stay updated."
    )
    return make_mp3(intro_text, "intro.mp3")


# ================================
# মেইন ফাংশন
# ================================
def main():
    print("=" * 50)
    print("   📻 Daily Star News Radio Generator")
    print("=" * 50)

    # পুরনো MP3 মুছে দাও
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith(".mp3"):
            os.remove(os.path.join(OUTPUT_DIR, f))

    playlist = []

    # Intro বানাও
    intro_path = make_intro()
    if intro_path:
        playlist.append({
            "title": "Welcome to Daily Star Radio",
            "file": "audio/intro.mp3",
            "type": "intro"
        })

    # নিউজ স্ক্র্যাপ করো
    articles = scrape_daily_star()

    if not articles:
        # Fallback: শুধু হেডলাইন পড়ো
        print("⚠️  আর্টিকেল ডিটেইল নেই, শুধু শিরোনাম পড়া হবে।")
        fallback_text = "No detailed articles found. Please check back later."
        make_mp3(fallback_text, "fallback.mp3")
        playlist.append({"title": "Update", "file": "audio/fallback.mp3", "type": "news"})
    else:
        for i, article in enumerate(articles, 1):
            print(f"\n[{i}/{len(articles)}] {article['title'][:60]}...")

            # আর্টিকেলের লেখা আনো
            body = get_article_text(article["url"])

            if body:
                read_text = f"News {i}. {article['title']}. {body}"
            else:
                read_text = f"News {i}. {article['title']}."

            filename = f"news_{i:02d}.mp3"
            filepath = make_mp3(read_text, filename)

            if filepath:
                playlist.append({
                    "title": article["title"],
                    "file": f"audio/{filename}",
                    "url": article["url"],
                    "type": "news"
                })
                print(f"  ✅ MP3 তৈরি: {filename}")

    # Outro বানাও
    outro_text = (
        "That's all for this hour's news bulletin from Daily Star Radio. "
        "We will be back with more updates. Thank you for listening."
    )
    outro_path = make_mp3(outro_text, "outro.mp3")
    if outro_path:
        playlist.append({
            "title": "End of Bulletin",
            "file": "audio/outro.mp3",
            "type": "outro"
        })

    # Playlist JSON সেভ করো
    playlist_data = {
        "updated": datetime.utcnow().isoformat() + "Z",
        "total": len(playlist),
        "items": playlist
    }

    with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(playlist_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Playlist সেভ হয়েছে: {PLAYLIST_FILE}")
    print(f"🎵 মোট {len(playlist)} টি অডিও তৈরি হয়েছে।")
    print("=" * 50)


if __name__ == "__main__":
    main()

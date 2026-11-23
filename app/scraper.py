import re
import requests
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,id;q=0.8',
}

SHINIGAMI_API_HEADERS = {
    **HEADERS,
    'Origin': 'https://s1.shinigami.mx',
    'Referer': 'https://s1.shinigami.mx/'
}

def extract_uuid(text: str) -> str | None:
    match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', text, re.IGNORECASE)
    return match.group(1) if match else None

def is_shinigami_url(url: str) -> bool:
    netloc = urlparse(url).netloc.lower()
    return 'shinigami' in netloc or 'chapter/' in url

def fetch_shinigami_chapter_by_id(chapter_id: str) -> Dict[str, Any]:
    api_url = f"https://api.shinigami.io/v1/chapter/detail/{chapter_id}"
    resp = requests.get(api_url, headers=SHINIGAMI_API_HEADERS, timeout=20)
    if resp.status_code != 200:
        raise ValueError(f"Gagal memuat API Shinigami untuk chapter {chapter_id} (Status {resp.status_code}).")

    data_json = resp.json()
    if data_json.get('retcode') != 0:
        raise ValueError(f"API Shinigami mengembalikan error: {data_json.get('message', 'Unknown error')}")

    data = data_json.get('data', {})
    chapter_num = data.get('chapter_number', '')
    chapter_title = data.get('chapter_title', '')
    manga_id = data.get('manga_id', '')
    base_url = data.get('base_url') or 'https://cdn.shinigami.gg'
    chapter_data = data.get('chapter', {})
    path = chapter_data.get('path', '')
    filenames = chapter_data.get('data', [])

    if not filenames:
        raise ValueError(f"Chapter {chapter_num} tidak memiliki gambar atau belum tersedia.")

    image_urls = [f"{base_url}{path}{fn}" for fn in filenames]

    title = f"Chapter {chapter_num}"
    if chapter_title:
        title += f" - {chapter_title}"

    return {
        "title": title,
        "chapter_number": chapter_num,
        "chapter_id": chapter_id,
        "manga_id": manga_id,
        "source": "Shinigami",
        "total_images": len(image_urls),
        "image_urls": image_urls
    }

def detect_manga_series(url: str) -> Dict[str, Any]:
    """
    Detects manga title, current chapter number, and full available chapter range.
    """
    chapter_id = extract_uuid(url)
    if not chapter_id or not is_shinigami_url(url):
        # Fallback for non-Shinigami or generic URL
        return {
            "is_series": False,
            "manga_title": "Manhwa Chapter",
            "current_chapter": 1,
            "min_chapter": 1,
            "max_chapter": 1,
            "chapters": []
        }

    # 1. Fetch current chapter detail
    current_ch = fetch_shinigami_chapter_by_id(chapter_id)
    manga_id = current_ch.get("manga_id")
    current_num = current_ch.get("chapter_number")

    manga_title = "Manhwa Series"
    chapters_list = []

    # 2. Fetch manga metadata & title
    if manga_id:
        try:
            m_resp = requests.get(f"https://api.shinigami.io/v1/manga/detail/{manga_id}", headers=SHINIGAMI_API_HEADERS, timeout=15)
            if m_resp.status_code == 200:
                m_data = m_resp.json().get("data", {})
                manga_title = m_data.get("title") or manga_title
        except Exception:
            pass

        # 3. Fetch chapter list
        try:
            list_url = f"https://api.shinigami.io/v1/chapter/{manga_id}/list?limit=500&sort_by=chapter_number&sort_order=asc"
            l_resp = requests.get(list_url, headers=SHINIGAMI_API_HEADERS, timeout=15)
            if l_resp.status_code == 200:
                raw_list = l_resp.json().get("data", [])
                for item in raw_list:
                    ch_num = item.get("chapter_number")
                    ch_id = item.get("chapter_id")
                    if ch_num is not None and ch_id:
                        chapters_list.append({
                            "chapter_number": ch_num,
                            "chapter_id": ch_id,
                            "chapter_title": item.get("chapter_title", "")
                        })
        except Exception:
            pass

    if not chapters_list:
        # Fallback if list fetch failed
        chapters_list = [{
            "chapter_number": current_num or 1,
            "chapter_id": chapter_id,
            "chapter_title": current_ch.get("title", "")
        }]

    # Sort chapters by number
    chapters_list.sort(key=lambda x: x["chapter_number"])
    nums = [c["chapter_number"] for c in chapters_list]
    min_num = min(nums) if nums else (current_num or 1)
    max_num = max(nums) if nums else (current_num or 1)

    return {
        "is_series": True,
        "manga_id": manga_id,
        "manga_title": manga_title,
        "current_chapter": current_num,
        "min_chapter": min_num,
        "max_chapter": max_num,
        "chapters": chapters_list
    }

def fetch_generic_chapter(url: str) -> Dict[str, Any]:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        raise ValueError(f"Gagal membuka website (Status {resp.status_code}).")

    soup = BeautifulSoup(resp.text, 'html.parser')
    title = soup.title.string.strip() if soup.title and soup.title.string else "Manhwa Chapter"

    selectors = [
        '#readerarea', '.reader-area', '.reading-content', '#chapter-images',
        '.entry-content', '.chapter-content', '.wp-manga-chapter-img'
    ]
    container = None
    for sel in selectors:
        found = soup.select_one(sel)
        if found:
            container = found
            break

    search_scope = container if container else soup
    img_tags = search_scope.find_all('img')

    image_urls: List[str] = []
    for img in img_tags:
        src = (
            img.get('data-src') or 
            img.get('data-lazy-src') or 
            img.get('src') or 
            img.get('data-original')
        )
        if not src:
            continue
        src = src.strip()
        full_url = urljoin(url, src)

        lower = full_url.lower()
        if any(bad in lower for bad in ['logo', 'avatar', 'icon', 'ad.', 'ads.', 'banner_top', 'share']):
            continue

        if full_url not in image_urls:
            image_urls.append(full_url)

    if not image_urls:
        raise ValueError("Tidak ditemukan gambar chapter pada link yang diberikan.")

    return {
        "title": title,
        "chapter_number": 1,
        "source": "Generic Reader",
        "total_images": len(image_urls),
        "image_urls": image_urls
    }

def fetch_chapter_info(url: str) -> Dict[str, Any]:
    chapter_id = extract_uuid(url)
    if chapter_id and is_shinigami_url(url):
        return fetch_shinigami_chapter_by_id(chapter_id)
    return fetch_generic_chapter(url)

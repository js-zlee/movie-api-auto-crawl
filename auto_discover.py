# auto_discover.py
import requests
import re
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse, quote_plus

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://www.baidu.com/'
}

# === 新增：预设种子站点（可手动维护）===
SEED_SITES = [
    "https://hhzyapi.com/api.php/provide/vod/",
    "https://api.wujinapi.me/api.php/provide/vod/",
    "https://api.kudian70.com/api.php/provide/vod/",
    "https://api.1080zyku.com/inc/apijson_vod.php",
]

# === 新增：百度搜索关键词 ===
BAIDU_KEYWORDS = [
    'site:github.com "api.php/provide/vod"',
    '"免费影视接口" "api.php"',
    '"苹果CMS" api 接口',
    'm3u8 api 影视'
]

# === 新增：正则匹配更强大 ===
def extract_apis_from_text(text: str):
    patterns = [
        r'https?://[^\s\'"<>\)]*?api\.php/provide/vod/',
        r'https?://[^\s\'"<>\)]*?api\.php\?mod=vod',
        r'https?://[^\s\'"<>\)]*?api\.php/vod/',
        r'https?://[^\s\'"<>\)]*?api\.php/provide/vod/index\.php',
        r'https?://[^\s\'"<>\)]*?inc/apijson_vod\.php',
        r'https?://[^\s\'"<>\)]*?api\.php\?ac=list',
        # 宽松匹配（包含 vod 的 PHP 接口）
        r'https?://[^\s\'"<>\)]+\.php\?[^"\s]*vod[^"\s]*',
    ]
    
    all_urls = set()
    for pattern in patterns:
        urls = re.findall(pattern, text, re.IGNORECASE)
        for u in urls:
            u = u.rstrip('/').rstrip(')').rstrip('"').rstrip("'").split()[0]
            if u.startswith(('http://', 'https://')):
                all_urls.add(u + ('' if u.endswith('/') else '/'))
    return list(all_urls)

# === 保留：从 GitHub 搜索 ===
def discover_apis_from_github():
    found = set()
    GITHUB_QUERIES = [
        '影视资源 in:readme,description language:zh',
        '"api.php/provide/vod" in:file',
        'm3u8 api site:github.com',
        '免费影视接口 in:name,description',
        '苹果CMS api'
    ]
    for query in GITHUB_QUERIES:
        print(f"🔍 GitHub: {query}")
        url = "https://api.github.com/search/repositories"
        params = {"q": query, "sort": "updated", "order": "desc", "per_page": 10}
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            repos = resp.json().get('items', [])
            for repo in repos[:5]:
                raw_url = f"https://raw.githubusercontent.com/{repo['owner']['login']}/{repo['name']}/main/README.md"
                try:
                    readme = requests.get(raw_url, headers=HEADERS, timeout=8).text
                    apis = extract_apis_from_text(readme)
                    found.update(apis)
                except:
                    pass
        except Exception as e:
            print(f"⚠️ GitHub error: {e}")
    return found

# === 新增：从百度搜索 ===
def discover_apis_from_baidu():
    found = set()
    for keyword in BAIDU_KEYWORDS:
        print(f"🔍 Baidu: {keyword}")
        encoded_kw = quote_plus(keyword)
        search_url = f"https://www.baidu.com/s?wd={encoded_kw}&pn=0"
        try:
            resp = requests.get(search_url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                # 提取搜索结果中的链接（简化版）
                links = re.findall(r'<a[^>]*href="(https?://[^"]+)"', resp.text)
                for link in links[:5]:  # 只取前5个结果
                    try:
                        page = requests.get(link, headers=HEADERS, timeout=8)
                        apis = extract_apis_from_text(page.text)
                        found.update(apis)
                    except:
                        pass
        except Exception as e:
            print(f"⚠️ Baidu error: {e}")
    return found

# === 新增：从预设站点直接验证 ===
def get_seed_apis():
    return SEED_SITES

# === 验证函数（放宽条件）===
def validate_movie_api(url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return {"is_valid": False, "reason": f"HTTP {resp.status_code}"}

        data = resp.json()
        if not isinstance(data, dict):
            return {"is_valid": False, "reason": "Root not dict"}

        # 检查是否包含视频相关字段（更宽松）
        def has_video_fields(obj):
            if isinstance(obj, dict):
                keys = [str(k).lower() for k in obj.keys()]
                return any("vod" in k or "title" in k or "name" in k or "url" in k for k in keys)
            elif isinstance(obj, list) and obj:
                return has_video_fields(obj[0])
            return False

        if has_video_fields(data):
            return {"is_valid": True, "reason": "OK"}
        else:
            return {"is_valid": False, "reason": "No video fields"}

    except Exception as e:
        return {"is_valid": False, "reason": str(e)}

# === 主函数 ===
def main():
    all_apis = set()

    # 1. 种子站点
    all_apis.update(get_seed_apis())
    print(f"🌱 Added {len(SEED_SITES)} seed APIs")

    # 2. GitHub
    github_apis = discover_apis_from_github()
    all_apis.update(github_apis)
    print(f"🐙 Found {len(github_apis)} from GitHub")

    # 3. 百度搜索（谨慎使用）
    baidu_apis = discover_apis_from_baidu()
    all_apis.update(baidu_apis)
    print(f"🌐 Found {len(baidu_apis)} from Baidu")

    print(f"🎯 Total candidate APIs: {len(all_apis)}")

    sites = []
    current_time = datetime.now(timezone.utc).astimezone().isoformat()

    for api in sorted(all_apis):
        print(f"🧪 Validating: {api}")
        result = validate_movie_api(api)
        domain = urlparse(api).netloc
        name = domain.replace('www.', '').split('.')[0].title()

        site = {
            "id": str(uuid.uuid4()),
            "key": name,
            "name": name,
            "api": api,
            "type": 2,
            "isActive": 1 if result["is_valid"] else 0,
            "time": current_time,
            "isDefault": 0,
            "remark": result["reason"],
            "tags": ["自动发现"] if result["is_valid"] else ["失效"],
            "priority": 1 if result["is_valid"] else 0,
            "proxyMode": "none",
            "customProxy": ""
        }
        sites.append(site)

    # 保存为 JSON
    with open('movie_api_list.json', 'w', encoding='utf-8') as f:
        json.dump({"sites": sites}, f, ensure_ascii=False, indent=2)
    
    valid_count = sum(1 for s in sites if s['isActive'])
    print(f"✅ Done. {valid_count} valid out of {len(sites)}.")
    print(f"📁 File saved to movie_api_list.json")

if __name__ == "__main__":
    main()

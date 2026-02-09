# auto_discover.py
import requests
import re
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

# === 配置区 ===
GITHUB_QUERIES = [
    '影视资源 in:readme,description language:zh',
    '"api.php/provide/vod" in:file',
    'm3u8 api site:github.com',
    '免费影视接口 in:name,description'
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; MovieAPIBot/1.0)'
}

def extract_apis_from_text(text: str):
    pattern = r'https?://[a-zA-Z0-9._\-/:%~&=\+]+?api\.php/provide/vod/?'
    urls = re.findall(pattern, text, re.IGNORECASE)
    clean_urls = []
    for u in urls:
        u = u.rstrip('/').rstrip(')').rstrip('"').rstrip("'")
        if u.startswith(('http://', 'https://')):
            clean_urls.append(u + '/')
    return list(set(clean_urls))

def get_github_readme(owner, repo):
    for branch in ['main', 'master']:
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
        try:
            resp = requests.get(raw_url, headers=HEADERS, timeout=8)
            if resp.status_code == 200:
                return resp.text
        except:
            continue
    return ""

def discover_apis_from_github():
    found = set()
    for query in GITHUB_QUERIES:
        print(f"🔍 Searching GitHub: {query}")
        url = "https://api.github.com/search/repositories"
        params = {"q": query, "sort": "updated", "order": "desc", "per_page": 20}
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
            repos = resp.json().get('items', [])
            for repo in repos[:10]:
                readme = get_github_readme(repo['owner']['login'], repo['name'])
                apis = extract_apis_from_text(readme)
                found.update(apis)
        except Exception as e:
            print(f"⚠️ Error: {e}")
    return found

def validate_movie_api(url: str) -> dict:
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return {"is_valid": False, "reason": f"HTTP {resp.status_code}"}

        data = resp.json()
        if not isinstance(data, dict):
            return {"is_valid": False, "reason": "Root not dict"}

        has_list = "list" in data and isinstance(data["list"], list)
        has_data = "data" in data and isinstance(data["data"], (dict, list))
        has_vod = any("vod_" in str(k).lower() for k in (data.get("list") or data.get("data") or {}))

        if not (has_list or has_data or has_vod):
            return {"is_valid": False, "reason": "No vod fields"}

        return {"is_valid": True, "reason": "OK"}
    except Exception as e:
        return {"is_valid": False, "reason": str(e)}

def main():
    all_apis = discover_apis_from_github()
    print(f"🎯 Found {len(all_apis)} candidate APIs")

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

if __name__ == "__main__":
    main()

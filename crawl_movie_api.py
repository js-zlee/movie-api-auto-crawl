import requests
import re
import json
from datetime import datetime, timedelta
import time
from urllib.parse import quote

# ---------------------- 核心配置（新手可改，注释已标清） ----------------------
# 1. 影视接口核心搜索关键词（越多，找到的1年内资源越多）
SEARCH_KEYWORDS = [
    "影视接口站 api.php/provide/vod/ 可用 2026",
    "zyapi 影视资源接口 免费 最新",
    "lziapi caiji 影视接口 有效",
    "影视API 资源站 公开 2026",
    "自动采集 影视接口配置 JSON 可用",
    "最新影视资源站 API 接口 2026"
]
# 2. 国内可访问的搜索引擎入口列表（带1年时间筛选）
# 格式：(引擎名称, 搜索URL模板, 时间筛选参数)
SEARCH_ENGINES = [
    # 必应：ez7 代表近1年
    ("必应", "https://cn.bing.com/search?q={}&first={}", "&filters=ex1:\"ez7\""),
    # 百度：cr=0_513 代表近1年
    ("百度", "https://www.baidu.com/s?wd={}&pn={}", "&cr=0_513"),
    # 360搜索：t=1y 代表近1年
    ("360搜索", "https://www.so.com/s?q={}&pn={}", "&t=1y"),
    # 搜狗搜索：stime=1y 代表近1年
    ("搜狗搜索", "https://fanyi.sogou.com/websearch/searchList.jsp?query={}&page={}", "&stime=1y")
]
# 3. 爬取深度：每个关键词搜前3页（新手建议2-3，避免被封）
CRAWL_PAGE = 3
# 4. 接口网址匹配规则（覆盖核心标识）
API_PATTERN = re.compile(r'https?://[^\s)+?]+?(zy|api|lzi|caiji|cj)[^\s)*?]+?(api\.php/provide/vod/|api/json)')
# 5. 请求头（模拟浏览器，降低反爬）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.baidu.com/",
    "Accept-Language": "zh-CN,zh;q=0.9"
}
# 6. 输出JSON文件名
OUTPUT_FILE = "movie_api_list.json"
# 7. 防反爬间隔（秒）
SLEEP_TIME = 1.5
# 8. 接口验活配置（严格筛选可用接口）
VERIFY_TIMEOUT = 10  # 接口响应超时时间（10秒内没反应=无效）
VERIFY_MIN_LENGTH = 50  # 接口返回JSON最小长度（放宽限制）

# ---------------------- 工具函数：时间校验（兜底过滤1年内资源） ----------------------
def is_within_1_year(date_str):
    """校验日期字符串是否在近1年内，兜底过滤漏网的过期资源"""
    try:
        # 适配常见日期格式：2025-12-24 / 2025/12/24 / 2025.12.24
        date_formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]
        for fmt in date_formats:
            try:
                post_date = datetime.strptime(date_str.strip(), fmt)
                break
            except:
                continue
        # 计算1年前的日期
        one_year_ago = datetime.now() - timedelta(days=365)
        return post_date >= one_year_ago
    except:
        # 解析失败则默认保留（交给后续验活过滤）
        return True

# ---------------------- 核心函数1：搜索1年内的疑似渠道链接 ----------------------
def get_recent_channel_urls():
    channel_urls = set()
    print(f"===== 开始使用 {len(SEARCH_ENGINES)} 个国内搜索引擎，搜索近1年影视接口渠道 =====")
    
    for engine_name, search_url_template, time_param in SEARCH_ENGINES:
        print(f"\n🔍 使用 {engine_name} 搜索：")
        for keyword in SEARCH_KEYWORDS:
            # 对关键词URL编码（避免中文/特殊字符报错）
            encoded_keyword = quote(keyword)
            print(f"  关键词：{keyword}")
            for page in range(1, CRAWL_PAGE + 1):
                # 适配不同引擎的分页参数
                if engine_name == "必应":
                    page_param = (page - 1) * 10 + 1  # 必应分页：1、11、21...
                elif engine_name == "百度":
                    page_param = (page - 1) * 10  # 百度分页：0、10、20...（pn=0是第1页）
                elif engine_name == "360搜索":
                    page_param = page  # 360分页：1、2、3...
                elif engine_name == "搜狗搜索":
                    page_param = page  # 搜狗分页：1、2、3...
                
                # 拼接完整搜索URL（关键词+分页+1年时间筛选）
                search_url = f"{search_url_template.format(encoded_keyword, page_param)}{time_param}"
                
                try:
                    time.sleep(SLEEP_TIME)  # 防反爬，暂停1.5秒
                    response = requests.get(search_url, headers=HEADERS, timeout=10)
                    response.encoding = response.apparent_encoding
                    
                    # 提取搜索结果链接+发布时间（二次过滤）
                    date_pattern = re.compile(r'<cite class="sb_csi_date">([\d\-/.]+)</cite>')
                    if engine_name == "百度":
                        # 百度的发布时间在<span class="c-color-gray2">标签里
                        date_pattern = re.compile(r'<span class="c-color-gray2">([\d\-/.]+)</span>')
                    
                    link_pattern = re.compile(r'<a href="(https?://[^\s"]+)" target="_blank"')
                    # 匹配发布时间和链接
                    post_dates = date_pattern.findall(response.text)
                    all_links = link_pattern.findall(response.text)
                    
                    # 遍历链接，只保留1年内的
                    for idx, link in enumerate(all_links):
                        # 过滤核心标识+二次时间过滤
                        if any(word in link for word in ["zy", "api", "lzi", "caiji", "cj"]):
                            # 有发布时间则校验，无则默认保留（交给验活）
                            if idx < len(post_dates) and not is_within_1_year(post_dates[idx]):
                                print(f"  第{page}页：跳过过期链接 [{link[:30]}...]")
                                continue
                            channel_urls.add(link)
                    print(f"    第{page}页：过滤后保留 {len(channel_urls)} 个1年内的渠道")
                except Exception as e:
                    print(f"    第{page}页爬取失败：{str(e)}")
                    continue
    print(f"\n===== 搜索完成，共获取 {len(channel_urls)} 个1年内的疑似渠道 =====")
    return list(channel_urls)

# ---------------------- 核心函数2：从渠道爬取接口网址 ----------------------
def crawl_api_from_channels(channel_urls):
    all_api_urls = set()
    print(f"\n===== 开始从 {len(channel_urls)} 个渠道爬取接口网址 =====")
    for idx, channel in enumerate(channel_urls, 1):
        try:
            time.sleep(SLEEP_TIME)  # 防反爬，暂停1.5秒
            response = requests.get(channel, headers=HEADERS, timeout=10)
            response.encoding = response.apparent_encoding
            # 匹配接口网址
            api_matches = API_PATTERN.findall(response.text)
            api_urls = [match[0] + match[1] for match in api_matches]
            # 去重添加+简单清洗
            for url in api_urls:
                # 简单清洗：去掉多余字符（如括号、空格）
                clean_url = url.strip().replace(")", "").replace("(", "")
                all_api_urls.add(clean_url)
            print(f"  渠道{idx}/{len(channel_urls)} [{channel[:30]}...]：爬取到 {len(api_urls)} 个接口")
        except Exception as e:
            print(f"  渠道{idx}/{len(channel_urls)} [{channel[:30]}...]：爬取失败 {str(e)}")
            continue
    print(f"\n===== 渠道爬取完成，共发现 {len(all_api_urls)} 个原始接口网址 =====")
    return list(all_api_urls)

# ---------------------- 核心函数3：严格验活（仅保留真可用接口） ----------------------
def strict_verify_api_urls(api_urls):
    valid_urls = []
    print(f"\n===== 开始严格验证 {len(api_urls)} 个接口的可用性 =====")
    for idx, url in enumerate(api_urls, 1):
        try:
            # 严格验活条件：10秒内响应 + 200状态码 + 返回JSON + 响应内容非空
            res = requests.get(
                url, 
                headers=HEADERS, 
                timeout=VERIFY_TIMEOUT,
                allow_redirects=True  # 允许重定向（部分接口会跳转）
            )
            # 条件1：状态码200
            if res.status_code != 200:
                print(f"  {idx}/{len(api_urls)} ❌ 无效（状态码{res.status_code}）：{url}")
                continue
            # 条件2：返回JSON格式
            content_type = res.headers.get('Content-Type', '')
            if 'application/json' not in content_type and 'text/json' not in content_type:
                print(f"  {idx}/{len(api_urls)} ❌ 无效（非JSON响应）：{url}")
                continue
            # 条件3：响应内容非空且长度达标
            res_text = res.text.strip()
            if len(res_text) < VERIFY_MIN_LENGTH or res_text == "{}" or res_text == "[]":
                print(f"  {idx}/{len(api_urls)} ❌ 无效（空JSON响应）：{url}")
                continue
            # 所有条件满足，保留
            valid_urls.append(url)
            print(f"  {idx}/{len(api_urls)} ✅ 有效：{url}")
        except requests.exceptions.Timeout:
            print(f"  {idx}/{len(api_urls)} ❌ 无效（超时{VERIFY_TIMEOUT}秒）：{url}")
        except requests.exceptions.ConnectionError:
            print(f"  {idx}/{len(api_urls)} ❌ 无效（连接失败）：{url}")
        except Exception as e:
            print(f"  {idx}/{len(api_urls)} ❌ 无效（未知错误：{str(e)}）：{url}")
    print(f"\n===== 验活完成，仅保留 {len(valid_urls)} 个可用接口 =====")
    return valid_urls

# ---------------------- 核心函数4：保存可用接口到JSON ----------------------
def save_valid_api_to_json(valid_urls):
    # 构造标准JSON结构（和你之前的配置一致）
    result = {
        "sites": [
            {
                "id": f"auto-{idx}",
                "key": f"1年内有效-{idx}",
                "name": f"1年内有效-{idx}",
                "api": url,
                "type": 2,
                "isActive": 1,
                "time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+08:00",
                "isDefault": 0,
                "remark": f"GitHub Actions自动采集（近1年资源+验活通过）",
                "tags": ["1年内有效", "自动验活", "可用"],
                "priority": 0,
                "proxyMode": "none",
                "customProxy": ""
            }
            for idx, url in enumerate(valid_urls, 1)
        ],
        "exportTime": datetime.now().isoformat(),
        "total": len(valid_urls),
        "filters": {"search": None, "tags": None, "status": None}
    }
    # 写入JSON文件（覆盖旧文件，只保留最新可用接口）
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 最终结果：{len(valid_urls)} 个1年内发布且当前可用的接口已保存到 {OUTPUT_FILE}")

# ---------------------- 主函数：串联全流程 ----------------------
if __name__ == '__main__':
    start_time = datetime.now()
    print("===== 开始【1年内资源+多引擎+自动验活】影视接口采集全流程 =====")
    # 步骤1：获取1年内的渠道链接
    channel_urls = get_recent_channel_urls()
    if not channel_urls:
        print("❌ 未发现任何1年内的渠道，流程终止")
        # 生成空JSON，避免GitHub Actions提交报错
        save_valid_api_to_json([])
        exit()
    # 步骤2：从渠道爬取接口
    raw_api_urls = crawl_api_from_channels(channel_urls)
    if not raw_api_urls:
        print("❌ 未从渠道爬取到任何接口网址，流程终止")
        save_valid_api_to_json([])
        exit()
    # 步骤3：严格验活
    valid_api_urls = strict_verify_api_urls(raw_api_urls)
    # 步骤4：保存结果
    save_valid_api_to_json(valid_api_urls)
    # 结束统计
    end_time = datetime.now()
    cost_time = (end_time - start_time).total_seconds()
    print(f"\n===== 全流程完成！耗时 {cost_time:.1f} 秒，最终获取 {len(valid_api_urls)} 个有效影视接口 =====")

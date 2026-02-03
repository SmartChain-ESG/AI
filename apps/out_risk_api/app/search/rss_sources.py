# AI/apps/out_risk_api/app/search/rss_sources.py

# 20260201 이종헌 신규: RSS 후보 수집용 feed 목록(팀이 확정해서 채워 넣기)
RSS_FEEDS = [
    "https://www.khan.co.kr/rss/rssdata/total_news.xml",
    # "https://www.khan.co.kr/rss/rssdata/total_news.xml",  # 신규: 뉴스 전체 RSS
    # "https://www.hani.co.kr/rss/",                        # 신규: 한겨레 RSS(내부 채널 선택 필요할 수 있음)
    # "https://www.hani.co.kr/rss/society/",                # 수정: 한겨레 채널 RSS (예시: 사회)
    # "https://www.hani.co.kr/rss/economy/",                # 신규: 한겨레 채널 RSS (예시: 경제)
]

import re
import time
import json
from typing import Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from .models import ReviewData, ReviewSentiment
from .utils import fetch_page, get_session, save_json
from .config import REVIEWS_DIR, SCRAPING_CONFIG
from .brands import ECOMMERCE_SITES, REVIEW_SOURCES


class ReviewScraper:
    def __init__(self):
        self.session = get_session()
        self.all_reviews: list[ReviewData] = []

    def scrape_product(self, brand: str, perfume_name: str) -> list[ReviewData]:
        print(f"  Scraping reviews for {brand} - {perfume_name}...")
        query = f"{brand} {perfume_name} perfume"
        self.all_reviews = []

        for source_key, source_config in REVIEW_SOURCES.items():
            try:
                results = self._scrape_source(source_key, source_config, query)
                self.all_reviews.extend(results)
                time.sleep(SCRAPING_CONFIG["request_delay"] / 2)
            except Exception as e:
                print(f"    [WARN] {source_key} failed: {e}")

        return self.all_reviews

    def _scrape_source(self, source_key: str, config: dict, query: str) -> list[ReviewData]:
        search_url = config["search_url"].format(query=quote(query))
        print(f"    Fetching {source_key}: {search_url}")
        html = fetch_page(search_url, self.session)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")

        parsers = {
            "fragrantica": self._parse_fragrantica,
            "parfumo": self._parse_parfumo,
            "reddit": self._parse_reddit,
            "youtube": self._parse_youtube,
        }
        parser = parsers.get(source_key)
        if parser:
            return parser(soup, config["url"])
        return []

    def _parse_fragrantica(self, soup: BeautifulSoup, base_url: str) -> list[ReviewData]:
        reviews = []
        cards = soup.select(
            ".review-card, .review-box, [class*='review']"
        ) or soup.find_all("div", class_=re.compile(r"review", re.I))[:15]

        for card in cards:
            try:
                body = card.select_one(".review-text, .text, p")
                rating_el = card.select_one("[class*='rating'], [class*='rate']")
                author_el = card.select_one(".author, .username, .user")
                date_el = card.select_one(".date, .time, time")

                reviews.append(ReviewData(
                    source="fragrantica",
                    body=body.get_text(strip=True) if body else "",
                    rating=self._parse_rating(rating_el),
                    author=author_el.get_text(strip=True) if author_el else "",
                    date=date_el.get_text(strip=True) if date_el else None,
                ))
            except Exception:
                continue
        return reviews

    def _parse_parfumo(self, soup: BeautifulSoup, base_url: str) -> list[ReviewData]:
        reviews = []
        cards = soup.select(".review, .comment, [class*='review']")
        for card in cards[:10]:
            try:
                body = card.select_one(".text, .content, p")
                rating_el = card.select_one("[class*='rating'], [class*='star']")
                author_el = card.select_one(".author, .username")

                reviews.append(ReviewData(
                    source="parfumo",
                    body=body.get_text(strip=True) if body else "",
                    rating=self._parse_rating(rating_el),
                    author=author_el.get_text(strip=True) if author_el else "",
                ))
            except Exception:
                continue
        return reviews

    def _parse_reddit(self, soup: BeautifulSoup, base_url: str) -> list[ReviewData]:
        reviews = []
        posts = soup.select(
            "div[data-testid='post-container'], .Post, search-result"
        ) or soup.find_all("div", class_=re.compile(r"post|search-result", re.I))[:10]

        for post in posts:
            try:
                title_el = post.select_one("h3, a[data-testid='post-title'], ._eYtD")
                body_el = post.select_one("p, ._1qeIA, [data-testid='post-content']")
                votes_el = post.select_one("[data-testid='upvote-count'], ._1rZYc")

                title = title_el.get_text(strip=True) if title_el else ""
                body = body_el.get_text(strip=True) if body_el else ""

                combined = f"{title}. {body}" if title and body else (title or body)
                if len(combined) > 20:
                    votes = 0
                    if votes_el:
                        try:
                            votes = int(re.sub(r"[^\d]", "", votes_el.get_text(strip=True)))
                        except ValueError:
                            pass

                    reviews.append(ReviewData(
                        source="reddit",
                        body=combined[:1000],
                        votes_helpful=votes,
                    ))
            except Exception:
                continue
        return reviews

    def _parse_youtube(self, soup: BeautifulSoup, base_url: str) -> list[ReviewData]:
        reviews = []
        results = soup.select("ytd-video-renderer, .yt-simple-endpoint, a#video-title")
        for result in results[:8]:
            try:
                title = result.get("title", "") or result.get_text(strip=True)
                if title and len(title) > 10:
                    reviews.append(ReviewData(
                        source="youtube",
                        title=title.strip(),
                        body=f"YouTube video: {title.strip()}",
                    ))
            except Exception:
                continue
        return reviews

    def _parse_rating(self, el) -> Optional[float]:
        if not el:
            return None
        raw = el.get("content", "") or el.get("data-rating", "") or el.get_text(strip=True)
        try:
            val = float(re.sub(r"[^\d.]", "", raw))
            return round(val / 10 if val > 10 else val, 1)
        except (ValueError, TypeError):
            return None


def analyze_sentiment(reviews: list[ReviewData]) -> ReviewSentiment:
    positive_kw = {
        "amazing", "excellent", "love", "great", "fantastic", "wonderful",
        "best", "beautiful", "incredible", "perfect", "stunning", "gorgeous",
        "impressive", "outstanding", "superb", "phenomenal", "awesome",
        "compliment", "compliments", "long lasting", "beast mode", "projection beast",
        "value", "affordable", "budget", "underrated", "banger", "sleeper",
    }
    negative_kw = {
        "terrible", "awful", "bad", "worst", "poor", "disappointing",
        "hate", "horrible", "disgusting", "chemical", "synthetic",
        "weak", "fades", "no projection", "overpriced", "expensive",
        "fake", "copy", "cheap", "alcohol", "headache", "gives headache",
        "garbage", "waste", "regret",
    }

    sentiment = ReviewSentiment()
    for review in reviews:
        body = review.body.lower()
        pos = sum(1 for w in positive_kw if w in body)
        neg = sum(1 for w in negative_kw if w in body)

        if pos > neg:
            sentiment.positive += 1
        elif neg > pos:
            sentiment.negative += 1
        else:
            sentiment.neutral += 1

    return sentiment


def extract_review_insights(reviews: list[ReviewData]) -> dict:
    insights = {
        "avg_rating": 0.0,
        "total_reviews": len(reviews),
        "longevity_mentions": [],
        "projection_mentioned": None,
        "opening_descriptions": [],
        "drydown_descriptions": [],
        "most_mentioned_notes": {},
        "compliment_count": 0,
        "negative_highlights": [],
        "value_mentions": 0,
        "season_mentions": [],
        "occasion_mentions": [],
    }

    if not reviews:
        return insights

    ratings = [r.rating for r in reviews if r.rating is not None]
    if ratings:
        insights["avg_rating"] = round(sum(ratings) / len(ratings), 2)

    all_text = " ".join(r.body for r in reviews).lower()

    longevity_pat = re.findall(r"(\d+[\s-]*\+?\s*(?:hours?|hrs?))", all_text)
    if longevity_pat:
        insights["longevity_mentions"] = longevity_pat[:5]

    for kw in ["beast mode", "strong projection", "moderate", "intimate", "soft projection"]:
        if kw in all_text:
            insights["projection_mentioned"] = kw.title()
            break

    season_kws = ["summer", "winter", "monsoon", "spring", "autumn", "year-round", "all weather"]
    insights["season_mentions"] = [s for s in season_kws if s in all_text]

    occ_kws = ["office", "date", "party", "wedding", "club", "daily", "formal", "casual"]
    insights["occasion_mentions"] = [o for o in occ_kws if o in all_text]

    insights["value_mentions"] = sum(all_text.count(w) for w in ["value", "affordable", "budget"])
    insights["sentiment"] = analyze_sentiment(reviews).model_dump()

    return insights


def scrape_product_reviews(brand: str, perfume_name: str) -> dict:
    scraper = ReviewScraper()
    reviews = scraper.scrape_product(brand, perfume_name)
    insights = extract_review_insights(reviews)

    output = {
        "brand": brand,
        "perfume": perfume_name,
        "reviews_count": len(reviews),
        "reviews": [r.model_dump() for r in reviews],
        "insights": insights,
    }

    safe = f"{brand}_{perfume_name}".replace(" ", "_").lower()
    safe = re.sub(r"[^a-z0-9_]", "", safe)
    save_json(output, REVIEWS_DIR / f"{safe}.json")

    return output

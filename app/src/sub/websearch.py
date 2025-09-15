import aiohttp
import asyncio
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
from bs4 import BeautifulSoup
import urllib.parse
import time
from sub.utils import logger


class SearchResult(Enum):
    OK = 0
    ERROR = 1
    NO_RESULTS = 2


@dataclass
class SearchData:
    status: SearchResult
    results: Optional[List[Dict[str, str]]]
    error_message: Optional[str]


async def perform_web_search(query: str, max_results: int = 5) -> SearchData:
    """
    Perform a web search using DuckDuckGo Instant Answer API (no API key required)
    and Google custom search as fallback.
    """
    try:
        start = time.perf_counter()
        logger.info(f"[websearch] start query='{query[:80]}' max={max_results}")

        # First try DuckDuckGo Instant Answer API
        ddg_results = await _search_duckduckgo(query, max_results)
        if ddg_results.status == SearchResult.OK and ddg_results.results:
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"[websearch] ddg_ok results={len(ddg_results.results)} elapsed_ms={elapsed:.1f}")
            return ddg_results

        # Fallback to simple Google search scraping (be respectful with rate limiting)
        google_results = await _search_google_scrape(query, max_results)
        elapsed_mid = (time.perf_counter() - start) * 1000
        logger.info(
            f"[websearch] google_done status={google_results.status.name} results={0 if not google_results.results else len(google_results.results)} elapsed_ms={elapsed_mid:.1f}"
        )

        # If both fail due to network issues, return a helpful message
        if (
            ddg_results.status == SearchResult.ERROR
            and google_results.status == SearchResult.ERROR
            and (
                "No address associated with hostname" in str(ddg_results.error_message)
                or "No address associated with hostname" in str(google_results.error_message)
            )
        ):
            return SearchData(
                status=SearchResult.ERROR,
                results=None,
                error_message="インターネットアクセスが制限されています。現在ウェブ検索機能は利用できません。",
            )

        elapsed_end = (time.perf_counter() - start) * 1000
        logger.info(
            f"[websearch] end final_status={google_results.status.name} total_elapsed_ms={elapsed_end:.1f}"
        )
        return google_results

    except Exception as e:
        elapsed_err = (time.perf_counter() - start) * 1000
        logger.exception(f"[websearch] error elapsed_ms={elapsed_err:.1f} error={e}")
        return SearchData(
            status=SearchResult.ERROR, results=None, error_message=str(e)
        )


async def _search_duckduckgo(query: str, max_results: int) -> SearchData:
    """
    Search using DuckDuckGo Instant Answer API
    """
    try:
        # DuckDuckGo Instant Answer API
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp:
                resp.raise_for_status()
                ctype = resp.headers.get('Content-Type','')
                if 'json' not in ctype.lower():
                    # Unexpected content-type -> treat as no-results rather than ERROR (will fallback)
                    return SearchData(
                        status=SearchResult.ERROR,
                        results=None,
                        error_message=f"DuckDuckGo unexpected content-type: {ctype}"
                    )
                data = await resp.json(content_type=None)
        results = []
        
        # Extract instant answer if available
        if data.get('Abstract'):
            results.append({
                'title': data.get('Heading', 'DuckDuckGo Answer'),
                'snippet': data.get('Abstract', ''),
                'url': data.get('AbstractURL', 'https://duckduckgo.com')
            })
        
        # Extract related topics
        for topic in data.get('RelatedTopics', [])[:max_results-len(results)]:
            if isinstance(topic, dict) and topic.get('Text'):
                results.append({
                    'title': topic.get('FirstURL', '').split('/')[-1].replace('_', ' ') or 'Related Topic',
                    'snippet': topic.get('Text', ''),
                    'url': topic.get('FirstURL', 'https://duckduckgo.com')
                })
        
        if results:
            return SearchData(
                status=SearchResult.OK,
                results=results[:max_results],
                error_message=None
            )
        else:
            return SearchData(
                status=SearchResult.NO_RESULTS,
                results=None,
                error_message="No results found from DuckDuckGo"
            )
            
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")
        return SearchData(
            status=SearchResult.ERROR,
            results=None,
            error_message=str(e)
        )


async def _search_google_scrape(query: str, max_results: int) -> SearchData:
    """
    Simple Google search scraping as fallback (use sparingly to respect rate limits)
    """
    try:
        encoded_query = urllib.parse.quote_plus(query)
        # Add localization parameters (Japanese)
        url = f"https://www.google.com/search?q={encoded_query}&num={max_results}&hl=ja&gl=JP&pws=0"  # pws=0 to reduce personalization
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp:
                resp.raise_for_status()
                content = await resp.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        results = []
        
        # Find search result containers
        search_results = soup.find_all('div', class_='g')
        
        for result in search_results[:max_results]:
            try:
                # Extract title
                title_elem = result.find('h3')
                title = title_elem.get_text() if title_elem else "No title"
                
                # Extract link
                link_elem = result.find('a')
                link = link_elem.get('href') if link_elem else "No link"
                
                # Extract snippet
                snippet_elem = result.find('div', class_='VwiC3b')
                if not snippet_elem:
                    snippet_elem = result.find('span', class_='aCOpRe')
                snippet = snippet_elem.get_text() if snippet_elem else "No description available"
                
                if title and link.startswith('http'):
                    results.append({
                        'title': title,
                        'snippet': snippet[:200] + "..." if len(snippet) > 200 else snippet,
                        'url': link
                    })
                    
            except Exception as e:
                logger.warning(f"Error parsing search result: {e}")
                continue
        
        if results:
            return SearchData(
                status=SearchResult.OK,
                results=results,
                error_message=None
            )
        else:
            return SearchData(
                status=SearchResult.NO_RESULTS,
                results=None,
                error_message="No search results found"
            )
            
    except Exception as e:
        logger.warning(f"Google search scraping failed: {e}")
        return SearchData(
            status=SearchResult.ERROR,
            results=None,
            error_message=str(e)
        )


def format_search_results(search_data: SearchData, query: str) -> str:
    """
    Format search results for Discord display
    """
    if search_data.status == SearchResult.ERROR:
        return f"❌ **検索エラー**: {search_data.error_message}"
    
    if search_data.status == SearchResult.NO_RESULTS:
        return f"🔍 **検索結果なし**: 「{query}」に関する情報が見つかりませんでした。"
    
    if not search_data.results:
        return f"🔍 **検索結果なし**: 「{query}」に関する情報が見つかりませんでした。"
    
    # Format results
    formatted_results = [f"🔍 **「{query}」の検索結果:**\n"]
    
    for i, result in enumerate(search_data.results, 1):
        title = result.get('title', 'No title')
        snippet = result.get('snippet', 'No description')
        url = result.get('url', 'No URL')
        
        # Truncate long snippets
        if len(snippet) > 150:
            snippet = snippet[:150] + "..."
            
        formatted_results.append(
            f"**{i}. {title}**\n"
            f"{snippet}\n"
            f"🔗 {url}\n"
        )
    
    return "\n".join(formatted_results)
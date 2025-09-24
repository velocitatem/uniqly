import requests
import json
from typing import List, Dict
from dataclasses import dataclass
import time
import re


@dataclass
class CompetitorInfo:
    name: str
    website: str
    description: str
    industry: str


class CompetitorDiscovery:
    def __init__(self):
        self.search_engines = {
            'duckduckgo': self._search_duckduckgo,
            'serp': self._search_serp_api
        }

    def discover_competitors(self, business_idea: str, max_results: int = 10) -> List[CompetitorInfo]:
        """
        Discover competitors based on a business idea description
        """
        # Extract key terms and generate search queries
        search_queries = self._generate_search_queries(business_idea)

        competitors = []
        seen_domains = set()

        for query in search_queries:
            try:
                results = self._search_duckduckgo(query, max_results//len(search_queries))
                for result in results:
                    domain = self._extract_domain(result.website)
                    if domain not in seen_domains and len(competitors) < max_results:
                        competitors.append(result)
                        seen_domains.add(domain)

                time.sleep(1)  # Rate limiting

            except Exception as e:
                print(f"Error searching for '{query}': {e}")
                continue

        return competitors[:max_results]

    def _generate_search_queries(self, business_idea: str) -> List[str]:
        """
        Generate relevant search queries from business idea
        """
        # Clean and extract keywords
        idea_lower = business_idea.lower()

        # Remove common stop words and extract key concepts
        stop_words = {'for', 'using', 'with', 'the', 'a', 'an', 'and', 'or', 'but'}
        words = [w for w in re.findall(r'\w+', idea_lower) if w not in stop_words]

        queries = []

        # Direct search
        queries.append(f"{business_idea} competitors")
        queries.append(f"{business_idea} alternative")

        # Industry-specific searches
        if len(words) >= 2:
            main_concept = words[0]
            target_market = words[-1] if words[-1] != words[0] else words[1] if len(words) > 1 else words[0]

            queries.extend([
                f"{main_concept} {target_market} companies",
                f"{main_concept} {target_market} startups",
                f"{target_market} {main_concept} platform",
                f"best {main_concept} {target_market} apps"
            ])

        return queries[:5]  # Limit to 5 queries

    def _search_duckduckgo(self, query: str, max_results: int = 5) -> List[CompetitorInfo]:
        """
        Search using DuckDuckGo Instant Answer API (limited but free)
        """
        try:
            # Use DuckDuckGo's instant answer API
            url = "https://api.duckduckgo.com/"
            params = {
                'q': query,
                'format': 'json',
                'no_html': '1',
                'skip_disambig': '1'
            }

            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            competitors = []

            # Parse related topics and results
            related_topics = data.get('RelatedTopics', [])

            for topic in related_topics[:max_results]:
                if isinstance(topic, dict) and 'FirstURL' in topic:
                    text = topic.get('Text', '')
                    url = topic.get('FirstURL', '')

                    if url and text:
                        name = self._extract_company_name(text, url)
                        competitors.append(CompetitorInfo(
                            name=name,
                            website=url,
                            description=text[:200],
                            industry=self._guess_industry(text)
                        ))

            # Fallback: create mock competitors for testing
            if not competitors:
                print(f"No results from API, using mock competitors for query: {query}")
                competitors = self._create_mock_competitors(query, max_results)

            return competitors

        except Exception as e:
            print(f"DuckDuckGo search failed: {e}")
            return self._create_mock_competitors(query, max_results)

    def _search_serp_api(self, query: str, max_results: int = 5) -> List[CompetitorInfo]:
        """
        Placeholder for SERP API integration (requires API key)
        """
        # This would integrate with SerpAPI, Google Custom Search, etc.
        # For now, return mock data
        return self._create_mock_competitors(query, max_results)

    def _create_mock_competitors(self, query: str, max_results: int) -> List[CompetitorInfo]:
        """
        Create mock competitors for testing purposes
        """
        mock_companies = [
            {"name": "Uber", "domain": "uber.com", "desc": "Ride-sharing platform"},
            {"name": "Lyft", "domain": "lyft.com", "desc": "Transportation network company"},
            {"name": "DoorDash", "domain": "doordash.com", "desc": "Food delivery service"},
            {"name": "Airbnb", "domain": "airbnb.com", "desc": "Home-sharing marketplace"},
            {"name": "TaskRabbit", "domain": "taskrabbit.com", "desc": "On-demand services platform"},
            {"name": "Fiverr", "domain": "fiverr.com", "desc": "Freelance services marketplace"},
            {"name": "Rover", "domain": "rover.com", "desc": "Pet care services platform"},
            {"name": "Wag", "domain": "wagwalking.com", "desc": "Dog walking services"},
            {"name": "Fetch", "domain": "fetch.com", "desc": "Pet insurance and services"},
            {"name": "PetSmart", "domain": "petsmart.com", "desc": "Pet retail and services"}
        ]

        # Filter based on query context
        relevant_companies = []
        query_words = query.lower().split()

        for company in mock_companies:
            relevance_score = sum(1 for word in query_words
                                if word in company["desc"].lower() or word in company["name"].lower())
            if relevance_score > 0:
                relevant_companies.append((relevance_score, company))

        # Sort by relevance and take top results
        relevant_companies.sort(key=lambda x: x[0], reverse=True)

        result = []
        for _, company in relevant_companies[:max_results]:
            result.append(CompetitorInfo(
                name=company["name"],
                website=f"https://{company['domain']}",
                description=company["desc"],
                industry=self._guess_industry(company["desc"])
            ))

        return result

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        import re
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        return match.group(1) if match else url

    def _extract_company_name(self, text: str, url: str) -> str:
        """Extract company name from text or URL"""
        # Try to extract from URL domain
        domain = self._extract_domain(url)
        if domain:
            name = domain.split('.')[0].title()
            if len(name) > 2:
                return name

        # Extract from text (first few words, capitalized)
        words = text.split()[:3]
        return ' '.join(word.title() for word in words if word.isalpha())

    def _guess_industry(self, description: str) -> str:
        """Guess industry based on description keywords"""
        desc_lower = description.lower()

        industry_keywords = {
            'technology': ['app', 'platform', 'software', 'tech', 'digital'],
            'transportation': ['ride', 'transport', 'delivery', 'logistics'],
            'marketplace': ['marketplace', 'platform', 'connect', 'network'],
            'services': ['service', 'care', 'assistance', 'help'],
            'retail': ['retail', 'store', 'shop', 'sell'],
            'fintech': ['payment', 'finance', 'money', 'blockchain', 'crypto'],
            'healthcare': ['health', 'medical', 'care', 'wellness'],
            'food': ['food', 'restaurant', 'dining', 'meal'],
            'pets': ['pet', 'dog', 'cat', 'animal']
        }

        for industry, keywords in industry_keywords.items():
            if any(keyword in desc_lower for keyword in keywords):
                return industry

        return 'general'


if __name__ == "__main__":
    # Test the competitor discovery
    discovery = CompetitorDiscovery()

    test_ideas = [
        "uber for dogs using blockchain",
        "food delivery app",
        "pet care marketplace"
    ]

    for idea in test_ideas:
        print(f"\nTesting: {idea}")
        competitors = discovery.discover_competitors(idea, max_results=5)

        for comp in competitors:
            print(f"  - {comp.name} ({comp.website})")
            print(f"    {comp.description}")
            print(f"    Industry: {comp.industry}")
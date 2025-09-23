import requests
from PIL import Image
import numpy as np
from sklearn.cluster import KMeans
from collections import Counter
import io
import re
from typing import List, Tuple, Dict
from dataclasses import dataclass
import colorsys
from bs4 import BeautifulSoup
import time


@dataclass
class ColorInfo:
    hex: str
    rgb: Tuple[int, int, int]
    hsl: Tuple[float, float, float]
    frequency: float
    source: str  # 'logo', 'dominant', 'css', 'brand_guide'


class BrandColorExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def extract_brand_colors(self, website_url: str, company_name: str) -> List[ColorInfo]:
        """
        Extract brand colors from a company's website
        """
        colors = []

        try:
            # 1. Extract colors from homepage
            homepage_colors = self._extract_colors_from_webpage(website_url)
            colors.extend(homepage_colors)

            # 2. Try to find and extract logo colors
            logo_colors = self._extract_logo_colors(website_url, company_name)
            colors.extend(logo_colors)

            # 3. Extract CSS-defined brand colors
            css_colors = self._extract_css_colors(website_url)
            colors.extend(css_colors)

            # 4. Remove duplicates and rank by frequency
            colors = self._deduplicate_and_rank_colors(colors)

        except Exception as e:
            print(f"Error extracting colors from {website_url}: {e}")
            # Fallback to predefined brand colors if available
            colors = self._get_fallback_colors(company_name)

        return colors[:10]  # Return top 10 colors

    def _extract_colors_from_webpage(self, url: str) -> List[ColorInfo]:
        """Extract dominant colors from webpage screenshot/content"""
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')

            colors = []

            # Extract colors from inline styles
            for element in soup.find_all(style=True):
                style_colors = self._parse_css_colors(element['style'])
                colors.extend([ColorInfo(
                    hex=color,
                    rgb=self._hex_to_rgb(color),
                    hsl=self._rgb_to_hsl(self._hex_to_rgb(color)),
                    frequency=1.0,
                    source='inline_css'
                ) for color in style_colors])

            # Extract background colors and text colors
            bg_elements = soup.find_all(['div', 'section', 'header', 'nav'], class_=True)
            for element in bg_elements[:20]:  # Limit to first 20 elements
                classes = ' '.join(element.get('class', []))
                if any(keyword in classes.lower() for keyword in ['bg-', 'background', 'color', 'brand']):
                    # This is a simplified approach - in practice, you'd need to load CSS
                    pass

            return colors

        except Exception as e:
            print(f"Error extracting webpage colors: {e}")
            return []

    def _extract_logo_colors(self, website_url: str, company_name: str) -> List[ColorInfo]:
        """Extract colors from company logo"""
        try:
            response = self.session.get(website_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for logo images
            logo_selectors = [
                'img[alt*="logo" i]',
                'img[src*="logo" i]',
                'img[class*="logo" i]',
                '.logo img',
                '.brand img',
                'header img',
                '.navbar img'
            ]

            logo_urls = []
            for selector in logo_selectors:
                elements = soup.select(selector)
                for img in elements[:3]:  # Limit to first 3 matches
                    src = img.get('src')
                    if src:
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = website_url.rstrip('/') + src
                        elif not src.startswith('http'):
                            src = website_url.rstrip('/') + '/' + src

                        logo_urls.append(src)

            # Extract colors from logo images
            colors = []
            for logo_url in logo_urls[:2]:  # Process max 2 logos
                try:
                    logo_colors = self._extract_colors_from_image(logo_url)
                    colors.extend(logo_colors)
                except Exception as e:
                    print(f"Error processing logo {logo_url}: {e}")
                    continue

            return colors

        except Exception as e:
            print(f"Error extracting logo colors: {e}")
            return []

    def _extract_colors_from_image(self, image_url: str) -> List[ColorInfo]:
        """Extract dominant colors from an image using K-means clustering"""
        try:
            response = self.session.get(image_url, timeout=10)
            img = Image.open(io.BytesIO(response.content))

            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Resize image for faster processing
            img.thumbnail((150, 150))

            # Convert to numpy array
            img_array = np.array(img)
            pixels = img_array.reshape(-1, 3)

            # Remove white and very light colors (background)
            pixels = pixels[np.sum(pixels, axis=1) < 700]  # Remove very light pixels

            if len(pixels) < 10:
                return []

            # Use K-means to find dominant colors
            n_colors = min(5, len(pixels) // 50)
            if n_colors < 2:
                n_colors = 2

            kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10)
            kmeans.fit(pixels)

            colors = []
            for i, center in enumerate(kmeans.cluster_centers_):
                rgb = tuple(map(int, center))
                hex_color = '#{:02x}{:02x}{:02x}'.format(*rgb)

                # Calculate frequency based on cluster size
                labels = kmeans.labels_
                frequency = np.sum(labels == i) / len(labels)

                colors.append(ColorInfo(
                    hex=hex_color,
                    rgb=rgb,
                    hsl=self._rgb_to_hsl(rgb),
                    frequency=frequency,
                    source='logo'
                ))

            return sorted(colors, key=lambda x: x.frequency, reverse=True)

        except Exception as e:
            print(f"Error extracting colors from image: {e}")
            return []

    def _extract_css_colors(self, website_url: str) -> List[ColorInfo]:
        """Extract colors from CSS files"""
        try:
            response = self.session.get(website_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')

            colors = []

            # Find CSS links
            css_links = soup.find_all('link', rel='stylesheet')
            for link in css_links[:5]:  # Limit to first 5 CSS files
                href = link.get('href')
                if href:
                    try:
                        if href.startswith('//'):
                            href = 'https:' + href
                        elif href.startswith('/'):
                            href = website_url.rstrip('/') + href
                        elif not href.startswith('http'):
                            href = website_url.rstrip('/') + '/' + href

                        css_response = self.session.get(href, timeout=5)
                        css_colors = self._parse_css_colors(css_response.text)

                        colors.extend([ColorInfo(
                            hex=color,
                            rgb=self._hex_to_rgb(color),
                            hsl=self._rgb_to_hsl(self._hex_to_rgb(color)),
                            frequency=1.0,
                            source='css'
                        ) for color in css_colors])

                    except Exception as e:
                        continue

            return colors

        except Exception as e:
            print(f"Error extracting CSS colors: {e}")
            return []

    def _parse_css_colors(self, css_text: str) -> List[str]:
        """Parse hex colors from CSS text"""
        # Find hex colors
        hex_pattern = r'#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b'
        hex_colors = re.findall(hex_pattern, css_text)

        # Normalize 3-digit hex to 6-digit
        normalized_colors = []
        for color in hex_colors:
            if len(color) == 4:  # #abc -> #aabbcc
                normalized_colors.append(f"#{color[1]*2}{color[2]*2}{color[3]*2}")
            else:
                normalized_colors.append(color.lower())

        return list(set(normalized_colors))  # Remove duplicates

    def _deduplicate_and_rank_colors(self, colors: List[ColorInfo]) -> List[ColorInfo]:
        """Remove similar colors and rank by frequency and source importance"""
        if not colors:
            return []

        # Group similar colors (within threshold)
        grouped_colors = {}
        threshold = 30  # Color similarity threshold

        for color in colors:
            found_group = False
            for existing_color in grouped_colors:
                if self._color_distance(color.rgb, existing_color.rgb) < threshold:
                    # Merge with existing group
                    existing_group = grouped_colors[existing_color]
                    existing_group.append(color)
                    found_group = True
                    break

            if not found_group:
                grouped_colors[color] = [color]

        # Select best representative from each group
        final_colors = []
        for group in grouped_colors.values():
            # Sort by source importance and frequency
            source_weights = {'logo': 3, 'dominant': 2, 'css': 1, 'inline_css': 1}

            best_color = max(group, key=lambda c: (
                source_weights.get(c.source, 1) * c.frequency
            ))

            # Update frequency to be average of group
            best_color.frequency = sum(c.frequency for c in group) / len(group)
            final_colors.append(best_color)

        # Sort by weighted score
        return sorted(final_colors, key=lambda c: (
            source_weights.get(c.source, 1) * c.frequency
        ), reverse=True)

    def _color_distance(self, rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
        """Calculate Euclidean distance between two RGB colors"""
        return np.sqrt(sum((a - b) ** 2 for a, b in zip(rgb1, rgb2)))

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _rgb_to_hsl(self, rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """Convert RGB to HSL"""
        r, g, b = [x/255.0 for x in rgb]
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        return (h*360, s*100, l*100)

    def _get_fallback_colors(self, company_name: str) -> List[ColorInfo]:
        """Get fallback colors for well-known companies"""
        fallback_colors = {
            'uber': ['#000000', '#ffffff'],
            'lyft': ['#ff00bf', '#ffffff'],
            'airbnb': ['#ff5a5f', '#00a699'],
            'doordash': ['#ff3008', '#ffffff'],
            'taskrabbit': ['#00b6ad', '#ffffff'],
            'fiverr': ['#1dbf73', '#404145'],
            'rover': ['#00b4a6', '#ffffff'],
            'wag': ['#00c896', '#ffffff'],
            'petsmart': ['#003da5', '#ff6900'],
            'fetch': ['#ff6b35', '#004e92']
        }

        company_key = company_name.lower()
        if company_key in fallback_colors:
            colors = []
            for i, hex_color in enumerate(fallback_colors[company_key]):
                rgb = self._hex_to_rgb(hex_color)
                colors.append(ColorInfo(
                    hex=hex_color,
                    rgb=rgb,
                    hsl=self._rgb_to_hsl(rgb),
                    frequency=1.0 - (i * 0.1),  # Decreasing frequency
                    source='fallback'
                ))
            return colors

        return []


if __name__ == "__main__":
    # Test the color extractor
    extractor = BrandColorExtractor()

    test_companies = [
        ("https://uber.com", "Uber"),
        ("https://airbnb.com", "Airbnb"),
        ("https://rover.com", "Rover")
    ]

    for website, company in test_companies:
        print(f"\nExtracting colors for {company} ({website}):")
        colors = extractor.extract_brand_colors(website, company)

        for color in colors[:5]:  # Show top 5 colors
            print(f"  {color.hex} (RGB: {color.rgb}) - {color.source} - {color.frequency:.2f}")
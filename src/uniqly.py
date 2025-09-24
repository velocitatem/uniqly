#!/usr/bin/env python3
"""
Uniqly - Generate unique color palettes by analyzing competitor brands

Main orchestrator that ties together competitor discovery, color extraction,
and unique palette generation.
"""

import json
import argparse
from typing import List, Dict, Optional
from dataclasses import asdict
import time
from datetime import datetime

from competitor_discovery import CompetitorDiscovery, CompetitorInfo
from color_extractor import BrandColorExtractor, ColorInfo
from palette_generator import UniqueColorPaletteGenerator, ColorPalette


class UniqlyEngine:
    def __init__(self, cache_results: bool = True):
        self.competitor_discovery = CompetitorDiscovery()
        self.color_extractor = BrandColorExtractor()
        self.palette_generator = UniqueColorPaletteGenerator()
        self.cache_results = cache_results
        self.cache = {}

    def generate_unique_palette(self,
                               business_idea: str,
                               theme: str = 'modern',
                               palette_size: int = 5,
                               max_competitors: int = 8) -> Dict:
        """
        Main method to generate a unique color palette

        Args:
            business_idea: Description of the business idea (e.g., "uber for dogs using blockchain")
            theme: Palette theme ('modern', 'vibrant', 'professional', 'muted')
            palette_size: Number of colors in the final palette
            max_competitors: Maximum number of competitors to analyze

        Returns:
            Dictionary containing the complete analysis and generated palette
        """
        print(f"🚀 Generating unique palette for: '{business_idea}'")
        print(f"📊 Theme: {theme}, Palette size: {palette_size}")

        # Step 1: Discover competitors
        print("\n🔍 Step 1: Discovering competitors...")
        competitors = self.competitor_discovery.discover_competitors(
            business_idea, max_results=max_competitors
        )

        if not competitors:
            print("⚠️  No competitors found, generating palette without competitor analysis")
            return self._generate_fallback_result(business_idea, theme, palette_size)

        print(f"✅ Found {len(competitors)} competitors:")
        for comp in competitors:
            print(f"   • {comp.name} - {comp.website}")

        # Step 2: Extract colors from competitor brands
        print("\n🎨 Step 2: Extracting competitor brand colors...")
        competitor_colors = []
        successful_extractions = 0

        for i, competitor in enumerate(competitors):
            print(f"   Analyzing {competitor.name} ({i+1}/{len(competitors)})...")
            try:
                colors = self.color_extractor.extract_brand_colors(
                    competitor.website, competitor.name
                )
                if colors:
                    competitor_colors.append(colors)
                    successful_extractions += 1
                    print(f"   ✅ Found {len(colors)} colors for {competitor.name}")
                else:
                    print(f"   ⚠️  No colors found for {competitor.name}")

                # Rate limiting
                time.sleep(0.5)

            except Exception as e:
                print(f"   ❌ Error analyzing {competitor.name}: {e}")
                continue

        print(f"✅ Successfully extracted colors from {successful_extractions}/{len(competitors)} competitors")

        # Step 3: Generate unique palette
        print(f"\n🌈 Step 3: Generating unique {theme} palette...")
        if competitor_colors:
            palette = self.palette_generator.generate_unique_palette(
                competitor_colors, theme, palette_size
            )
        else:
            print("⚠️  No competitor colors available, generating palette without constraints")
            palette = self.palette_generator._generate_fallback_palette(
                theme, palette_size, []
            )

        # Compile results
        result = {
            'input': {
                'business_idea': business_idea,
                'theme': theme,
                'palette_size': palette_size,
                'max_competitors': max_competitors
            },
            'analysis': {
                'competitors_found': len(competitors),
                'competitors_analyzed': successful_extractions,
                'total_colors_extracted': sum(len(colors) for colors in competitor_colors),
                'analysis_timestamp': datetime.now().isoformat()
            },
            'competitors': [asdict(comp) for comp in competitors],
            'competitor_colors': [
                [asdict(color) for color in colors]
                for colors in competitor_colors
            ],
            'generated_palette': asdict(palette),
            'recommendations': self._generate_recommendations(palette, competitor_colors)
        }

        print(f"\n✨ Generated unique palette with {len(palette.colors)} colors")
        print(f"📈 Uniqueness Score: {palette.uniqueness_score:.2f}/1.0")
        print(f"🎵 Harmony Score: {palette.harmony_score:.2f}/1.0")
        print(f"♿ Accessibility Score: {palette.accessibility_score:.2f}/1.0")

        return result

    def _generate_fallback_result(self, business_idea: str, theme: str, palette_size: int) -> Dict:
        """Generate a result when no competitors are found"""
        palette = self.palette_generator._generate_fallback_palette(theme, palette_size, [])

        return {
            'input': {
                'business_idea': business_idea,
                'theme': theme,
                'palette_size': palette_size,
                'max_competitors': 0
            },
            'analysis': {
                'competitors_found': 0,
                'competitors_analyzed': 0,
                'total_colors_extracted': 0,
                'analysis_timestamp': datetime.now().isoformat()
            },
            'competitors': [],
            'competitor_colors': [],
            'generated_palette': asdict(palette),
            'recommendations': self._generate_recommendations(palette, [])
        }

    def _generate_recommendations(self, palette: ColorPalette, competitor_colors: List[List[ColorInfo]]) -> Dict:
        """Generate usage recommendations for the palette"""
        primary_color = next((c for c in palette.colors if c.role == 'primary'), palette.colors[0])
        secondary_color = next((c for c in palette.colors if c.role == 'secondary'), palette.colors[1] if len(palette.colors) > 1 else primary_color)

        recommendations = {
            'usage_guide': {
                'primary_color': {
                    'hex': primary_color.hex,
                    'usage': 'Use for main brand elements, buttons, headers',
                    'accessibility_note': f"Accessibility score: {primary_color.accessibility_score:.2f}"
                },
                'secondary_color': {
                    'hex': secondary_color.hex,
                    'usage': 'Use for secondary buttons, borders, accents',
                    'accessibility_note': f"Accessibility score: {secondary_color.accessibility_score:.2f}"
                }
            },
            'differentiation_strategy': self._analyze_differentiation(palette, competitor_colors),
            'accessibility_notes': self._generate_accessibility_notes(palette),
            'theme_variations': {
                'lighter': 'Consider lighter variations for backgrounds',
                'darker': 'Consider darker variations for text and emphasis',
                'saturated': 'More saturated versions for highlights and CTAs'
            }
        }

        return recommendations

    def _analyze_differentiation(self, palette: ColorPalette, competitor_colors: List[List[ColorInfo]]) -> str:
        """Analyze how the palette differentiates from competitors"""
        if not competitor_colors:
            return "No competitor analysis available - palette generated independently"

        total_competitor_colors = sum(len(colors) for colors in competitor_colors)

        if palette.uniqueness_score > 0.8:
            return f"Excellent differentiation from {total_competitor_colors} competitor colors analyzed"
        elif palette.uniqueness_score > 0.6:
            return f"Good differentiation from competitors with some strategic overlaps"
        elif palette.uniqueness_score > 0.4:
            return f"Moderate differentiation - consider adjusting primary colors for stronger brand distinction"
        else:
            return f"Low differentiation detected - recommend exploring alternative color directions"

    def _generate_accessibility_notes(self, palette: ColorPalette) -> List[str]:
        """Generate accessibility recommendations"""
        notes = []

        if palette.accessibility_score < 0.5:
            notes.append("⚠️  Low overall accessibility - ensure sufficient contrast in final implementation")

        for color in palette.colors:
            if color.accessibility_score < 0.3:
                notes.append(f"⚠️  {color.hex} ({color.role}) may need contrast adjustments")

        if palette.accessibility_score > 0.8:
            notes.append("✅ Excellent accessibility scores across the palette")

        notes.append("💡 Always test final color combinations with WCAG contrast checkers")

        return notes

    def print_palette_preview(self, result: Dict):
        """Print a text-based preview of the generated palette"""
        palette_data = result['generated_palette']

        print(f"\n🎨 Generated Palette Preview")
        print(f"=" * 50)
        print(f"Theme: {palette_data['theme']}")
        print(f"Overall Scores:")
        print(f"  Uniqueness: {palette_data['uniqueness_score']:.2f}/1.0")
        print(f"  Harmony: {palette_data['harmony_score']:.2f}/1.0")
        print(f"  Accessibility: {palette_data['accessibility_score']:.2f}/1.0")
        print(f"\nColors:")

        for color_data in palette_data['colors']:
            hsl = color_data['hsl']
            print(f"  {color_data['hex']} - {color_data['role']}")
            print(f"    HSL: {hsl[0]:.0f}°, {hsl[1]:.0f}%, {hsl[2]:.0f}%")
            print(f"    Accessibility: {color_data['accessibility_score']:.2f}")

        print(f"\n💡 Recommendations:")
        for note in result['recommendations']['accessibility_notes']:
            print(f"  {note}")


def main():
    parser = argparse.ArgumentParser(description='Generate unique color palettes by analyzing competitors')
    parser.add_argument('business_idea', help='Business idea description (e.g., "uber for dogs using blockchain")')
    parser.add_argument('--theme', choices=['modern', 'vibrant', 'professional', 'muted', 'warm', 'cool'],
                       default='modern', help='Palette theme')
    parser.add_argument('--size', type=int, default=5, help='Number of colors in palette')
    parser.add_argument('--competitors', type=int, default=8, help='Maximum competitors to analyze')
    parser.add_argument('--output', help='Output JSON file path')
    parser.add_argument('--preview', action='store_true', help='Show text preview of palette')

    args = parser.parse_args()

    # Initialize engine
    engine = UniqlyEngine()

    # Generate palette
    result = engine.generate_unique_palette(
        business_idea=args.business_idea,
        theme=args.theme,
        palette_size=args.size,
        max_competitors=args.competitors
    )

    # Show preview if requested
    if args.preview:
        engine.print_palette_preview(result)

    # Save to file if specified
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {args.output}")
    else:
        # Print JSON to stdout
        print(f"\n📄 Complete Results:")
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
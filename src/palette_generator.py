import numpy as np
import colorsys
from typing import List, Tuple, Dict, Set
from dataclasses import dataclass
from color_extractor import ColorInfo
import random
from itertools import combinations
import math


@dataclass
class PaletteColor:
    hex: str
    rgb: Tuple[int, int, int]
    hsl: Tuple[float, float, float]
    role: str  # 'primary', 'secondary', 'accent', 'neutral'
    accessibility_score: float


@dataclass
class ColorPalette:
    colors: List[PaletteColor]
    theme: str  # 'modern', 'vibrant', 'muted', 'professional'
    uniqueness_score: float  # How different from competitor colors
    harmony_score: float     # How well colors work together
    accessibility_score: float


class UniqueColorPaletteGenerator:
    def __init__(self):
        self.color_harmony_rules = {
            'complementary': self._generate_complementary,
            'triadic': self._generate_triadic,
            'analogous': self._generate_analogous,
            'split_complementary': self._generate_split_complementary,
            'tetradic': self._generate_tetradic,
            'monochromatic': self._generate_monochromatic
        }

    def generate_unique_palette(self,
                               competitor_colors: List[List[ColorInfo]],
                               theme: str = 'modern',
                               palette_size: int = 5) -> ColorPalette:
        """
        Generate a unique color palette that avoids competitor colors
        """
        # Flatten all competitor colors
        all_competitor_colors = []
        for company_colors in competitor_colors:
            all_competitor_colors.extend(company_colors)

        # Create forbidden color regions
        forbidden_regions = self._create_forbidden_regions(all_competitor_colors)

        # Generate multiple palette candidates
        candidates = []
        for harmony_rule in self.color_harmony_rules:
            for attempt in range(5):  # 5 attempts per rule
                try:
                    palette = self._generate_palette_candidate(
                        harmony_rule, theme, palette_size, forbidden_regions
                    )
                    if palette:
                        candidates.append(palette)
                except Exception as e:
                    continue

        # Score and select best palette
        if not candidates:
            # Fallback: generate random palette
            return self._generate_fallback_palette(theme, palette_size, forbidden_regions)

        best_palette = max(candidates, key=lambda p: (
            p.uniqueness_score * 0.4 +
            p.harmony_score * 0.3 +
            p.accessibility_score * 0.3
        ))

        return best_palette

    def _create_forbidden_regions(self, competitor_colors: List[ColorInfo]) -> List[Tuple[float, float, float]]:
        """Create HSL regions to avoid based on competitor colors"""
        forbidden_regions = []

        for color in competitor_colors:
            h, s, l = color.hsl
            # Create a region around each competitor color
            # Larger region for more frequent/important colors
            region_size = 30 + (color.frequency * 20)  # 30-50 degree range

            forbidden_regions.append((h, s, l, region_size))

        return forbidden_regions

    def _is_color_forbidden(self, hsl: Tuple[float, float, float],
                           forbidden_regions: List[Tuple[float, float, float, float]]) -> bool:
        """Check if a color is too close to competitor colors"""
        h, s, l = hsl

        for fh, fs, fl, region_size in forbidden_regions:
            # Calculate distance in HSL space
            h_diff = min(abs(h - fh), 360 - abs(h - fh))  # Handle hue wraparound
            s_diff = abs(s - fs)
            l_diff = abs(l - fl)

            # Weighted distance (hue is most important for brand differentiation)
            distance = math.sqrt((h_diff * 2) ** 2 + s_diff ** 2 + l_diff ** 2)

            if distance < region_size:
                return True

        return False

    def _generate_palette_candidate(self,
                                   harmony_rule: str,
                                   theme: str,
                                   palette_size: int,
                                   forbidden_regions: List) -> ColorPalette:
        """Generate a single palette candidate using a specific harmony rule"""

        # Start with a base color that's not forbidden
        base_color = self._generate_base_color(theme, forbidden_regions)
        if not base_color:
            return None

        # Generate harmonious colors
        harmony_colors = self.color_harmony_rules[harmony_rule](base_color, palette_size - 1)

        # Filter out forbidden colors and replace if needed
        final_colors = [base_color]
        for color in harmony_colors:
            if not self._is_color_forbidden(color, forbidden_regions):
                final_colors.append(color)

        # If we don't have enough colors, generate additional ones
        while len(final_colors) < palette_size:
            new_color = self._generate_safe_color(forbidden_regions, final_colors)
            if new_color:
                final_colors.append(new_color)
            else:
                break

        # Convert to PaletteColor objects with roles
        palette_colors = self._assign_color_roles(final_colors, theme)

        # Calculate scores
        uniqueness_score = self._calculate_uniqueness_score(palette_colors, forbidden_regions)
        harmony_score = self._calculate_harmony_score(palette_colors)
        accessibility_score = self._calculate_accessibility_score(palette_colors)

        return ColorPalette(
            colors=palette_colors,
            theme=theme,
            uniqueness_score=uniqueness_score,
            harmony_score=harmony_score,
            accessibility_score=accessibility_score
        )

    def _generate_base_color(self, theme: str, forbidden_regions: List) -> Tuple[float, float, float]:
        """Generate a base color that fits the theme and avoids forbidden regions"""
        theme_ranges = {
            'modern': {'h': (180, 240), 's': (40, 80), 'l': (40, 70)},
            'vibrant': {'h': (0, 360), 's': (70, 100), 'l': (50, 80)},
            'muted': {'h': (0, 360), 's': (20, 50), 'l': (30, 70)},
            'professional': {'h': (200, 260), 's': (30, 60), 'l': (20, 50)},
            'warm': {'h': (0, 60), 's': (50, 90), 'l': (40, 80)},
            'cool': {'h': (180, 300), 's': (50, 90), 'l': (40, 80)}
        }

        ranges = theme_ranges.get(theme, theme_ranges['modern'])

        for attempt in range(100):  # Max 100 attempts
            h = random.uniform(*ranges['h']) % 360
            s = random.uniform(*ranges['s'])
            l = random.uniform(*ranges['l'])

            if not self._is_color_forbidden((h, s, l), forbidden_regions):
                return (h, s, l)

        return None

    def _generate_safe_color(self, forbidden_regions: List, existing_colors: List) -> Tuple[float, float, float]:
        """Generate a color that's safe from forbidden regions and complements existing colors"""
        for attempt in range(50):
            h = random.uniform(0, 360)
            s = random.uniform(30, 80)
            l = random.uniform(30, 80)

            if not self._is_color_forbidden((h, s, l), forbidden_regions):
                # Check if it's not too similar to existing colors
                is_unique = True
                for existing_hsl in existing_colors:
                    if self._color_distance_hsl((h, s, l), existing_hsl) < 50:
                        is_unique = False
                        break

                if is_unique:
                    return (h, s, l)

        return None

    # Harmony rule implementations
    def _generate_complementary(self, base_hsl: Tuple[float, float, float], count: int) -> List[Tuple[float, float, float]]:
        """Generate complementary color scheme"""
        h, s, l = base_hsl
        colors = []

        if count >= 1:
            comp_h = (h + 180) % 360
            colors.append((comp_h, s * 0.8, l * 0.9))

        # Add variations
        for i in range(1, count):
            variation_h = h + random.uniform(-30, 30)
            variation_s = max(20, s + random.uniform(-20, 20))
            variation_l = max(20, min(80, l + random.uniform(-20, 20)))
            colors.append((variation_h % 360, variation_s, variation_l))

        return colors

    def _generate_triadic(self, base_hsl: Tuple[float, float, float], count: int) -> List[Tuple[float, float, float]]:
        """Generate triadic color scheme"""
        h, s, l = base_hsl
        colors = []

        if count >= 1:
            colors.append(((h + 120) % 360, s * 0.9, l * 0.95))
        if count >= 2:
            colors.append(((h + 240) % 360, s * 0.9, l * 0.95))

        # Add variations
        for i in range(2, count):
            base_triadic = colors[i % 2]
            variation_h = base_triadic[0] + random.uniform(-20, 20)
            variation_s = max(20, base_triadic[1] + random.uniform(-15, 15))
            variation_l = max(20, min(80, base_triadic[2] + random.uniform(-15, 15)))
            colors.append((variation_h % 360, variation_s, variation_l))

        return colors

    def _generate_analogous(self, base_hsl: Tuple[float, float, float], count: int) -> List[Tuple[float, float, float]]:
        """Generate analogous color scheme"""
        h, s, l = base_hsl
        colors = []

        step = 30
        for i in range(count):
            new_h = (h + (i + 1) * step) % 360
            new_s = max(20, s + random.uniform(-10, 10))
            new_l = max(20, min(80, l + random.uniform(-10, 10)))
            colors.append((new_h, new_s, new_l))

        return colors

    def _generate_split_complementary(self, base_hsl: Tuple[float, float, float], count: int) -> List[Tuple[float, float, float]]:
        """Generate split complementary color scheme"""
        h, s, l = base_hsl
        colors = []

        if count >= 1:
            colors.append(((h + 150) % 360, s * 0.9, l * 0.9))
        if count >= 2:
            colors.append(((h + 210) % 360, s * 0.9, l * 0.9))

        # Add variations
        for i in range(2, count):
            base_color = colors[i % 2]
            variation_h = base_color[0] + random.uniform(-15, 15)
            variation_s = max(20, base_color[1] + random.uniform(-10, 10))
            variation_l = max(20, min(80, base_color[2] + random.uniform(-10, 10)))
            colors.append((variation_h % 360, variation_s, variation_l))

        return colors

    def _generate_tetradic(self, base_hsl: Tuple[float, float, float], count: int) -> List[Tuple[float, float, float]]:
        """Generate tetradic (square) color scheme"""
        h, s, l = base_hsl
        colors = []

        offsets = [90, 180, 270]
        for i, offset in enumerate(offsets):
            if i < count:
                new_h = (h + offset) % 360
                new_s = max(20, s + random.uniform(-15, 15))
                new_l = max(20, min(80, l + random.uniform(-15, 15)))
                colors.append((new_h, new_s, new_l))

        return colors[:count]

    def _generate_monochromatic(self, base_hsl: Tuple[float, float, float], count: int) -> List[Tuple[float, float, float]]:
        """Generate monochromatic color scheme"""
        h, s, l = base_hsl
        colors = []

        for i in range(count):
            new_s = max(20, min(100, s + random.uniform(-30, 30)))
            new_l = max(20, min(80, l + (i + 1) * 15))
            colors.append((h, new_s, new_l))

        return colors

    def _assign_color_roles(self, hsl_colors: List[Tuple[float, float, float]], theme: str) -> List[PaletteColor]:
        """Assign roles to colors (primary, secondary, etc.)"""
        roles = ['primary', 'secondary', 'accent', 'neutral', 'highlight']
        palette_colors = []

        for i, hsl in enumerate(hsl_colors):
            role = roles[i] if i < len(roles) else 'additional'
            rgb = self._hsl_to_rgb(hsl)
            hex_color = '#{:02x}{:02x}{:02x}'.format(*rgb)

            # Calculate accessibility score for this color
            accessibility_score = self._calculate_color_accessibility(rgb)

            palette_colors.append(PaletteColor(
                hex=hex_color,
                rgb=rgb,
                hsl=hsl,
                role=role,
                accessibility_score=accessibility_score
            ))

        return palette_colors

    def _calculate_uniqueness_score(self, palette_colors: List[PaletteColor],
                                   forbidden_regions: List) -> float:
        """Calculate how unique the palette is compared to competitors"""
        total_distance = 0
        count = 0

        for color in palette_colors:
            min_distance = float('inf')
            for fh, fs, fl, region_size in forbidden_regions:
                distance = self._color_distance_hsl(color.hsl, (fh, fs, fl))
                min_distance = min(min_distance, distance)

            total_distance += min_distance
            count += 1

        return min(1.0, total_distance / (count * 100)) if count > 0 else 1.0

    def _calculate_harmony_score(self, palette_colors: List[PaletteColor]) -> float:
        """Calculate how harmonious the colors are together"""
        if len(palette_colors) < 2:
            return 1.0

        harmony_scores = []

        # Check color relationships
        for i, color1 in enumerate(palette_colors):
            for j, color2 in enumerate(palette_colors[i+1:], i+1):
                h1, s1, l1 = color1.hsl
                h2, s2, l2 = color2.hsl

                # Hue difference
                hue_diff = min(abs(h1 - h2), 360 - abs(h1 - h2))

                # Good relationships: complementary (~180), triadic (~120, ~240), analogous (~30)
                ideal_diffs = [30, 60, 90, 120, 150, 180]
                closest_ideal = min(ideal_diffs, key=lambda x: abs(x - hue_diff))
                hue_score = 1.0 - abs(closest_ideal - hue_diff) / 180

                # Saturation and lightness should be somewhat balanced
                sat_balance = 1.0 - abs(s1 - s2) / 100
                light_balance = 1.0 - abs(l1 - l2) / 100

                relationship_score = (hue_score * 0.6 + sat_balance * 0.2 + light_balance * 0.2)
                harmony_scores.append(relationship_score)

        return sum(harmony_scores) / len(harmony_scores) if harmony_scores else 1.0

    def _calculate_accessibility_score(self, palette_colors: List[PaletteColor]) -> float:
        """Calculate accessibility score based on contrast ratios"""
        if len(palette_colors) < 2:
            return 1.0

        contrast_scores = []

        # Check contrast between all color pairs
        for i, color1 in enumerate(palette_colors):
            for color2 in palette_colors[i+1:]:
                contrast_ratio = self._calculate_contrast_ratio(color1.rgb, color2.rgb)
                # WCAG AA standard is 4.5:1 for normal text
                score = min(1.0, contrast_ratio / 4.5)
                contrast_scores.append(score)

        return sum(contrast_scores) / len(contrast_scores) if contrast_scores else 1.0

    def _calculate_color_accessibility(self, rgb: Tuple[int, int, int]) -> float:
        """Calculate accessibility score for a single color"""
        # Check contrast with white and black
        white_contrast = self._calculate_contrast_ratio(rgb, (255, 255, 255))
        black_contrast = self._calculate_contrast_ratio(rgb, (0, 0, 0))

        # Return the better contrast score
        return max(
            min(1.0, white_contrast / 4.5),
            min(1.0, black_contrast / 4.5)
        )

    def _calculate_contrast_ratio(self, rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
        """Calculate WCAG contrast ratio between two RGB colors"""
        def luminance(rgb):
            r, g, b = [x / 255.0 for x in rgb]
            r = r / 12.92 if r <= 0.03928 else pow((r + 0.055) / 1.055, 2.4)
            g = g / 12.92 if g <= 0.03928 else pow((g + 0.055) / 1.055, 2.4)
            b = b / 12.92 if b <= 0.03928 else pow((b + 0.055) / 1.055, 2.4)
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        l1 = luminance(rgb1)
        l2 = luminance(rgb2)

        if l1 > l2:
            return (l1 + 0.05) / (l2 + 0.05)
        else:
            return (l2 + 0.05) / (l1 + 0.05)

    def _color_distance_hsl(self, hsl1: Tuple[float, float, float], hsl2: Tuple[float, float, float]) -> float:
        """Calculate distance between two colors in HSL space"""
        h1, s1, l1 = hsl1
        h2, s2, l2 = hsl2

        # Handle hue wraparound
        h_diff = min(abs(h1 - h2), 360 - abs(h1 - h2))
        s_diff = abs(s1 - s2)
        l_diff = abs(l1 - l2)

        # Weighted distance (hue is most important for brand differentiation)
        return math.sqrt((h_diff * 2) ** 2 + s_diff ** 2 + l_diff ** 2)

    def _hsl_to_rgb(self, hsl: Tuple[float, float, float]) -> Tuple[int, int, int]:
        """Convert HSL to RGB"""
        h, s, l = hsl[0] / 360, hsl[1] / 100, hsl[2] / 100
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return (int(r * 255), int(g * 255), int(b * 255))

    def _generate_fallback_palette(self, theme: str, palette_size: int, forbidden_regions: List) -> ColorPalette:
        """Generate a fallback palette when all other methods fail"""
        colors = []

        # Generate random colors that avoid forbidden regions
        for i in range(palette_size):
            for attempt in range(20):
                h = random.uniform(0, 360)
                s = random.uniform(40, 80)
                l = random.uniform(40, 70)

                if not self._is_color_forbidden((h, s, l), forbidden_regions):
                    colors.append((h, s, l))
                    break

        # If we still don't have enough, just generate any colors
        while len(colors) < palette_size:
            h = random.uniform(0, 360)
            s = random.uniform(40, 80)
            l = random.uniform(40, 70)
            colors.append((h, s, l))

        palette_colors = self._assign_color_roles(colors, theme)

        return ColorPalette(
            colors=palette_colors,
            theme=theme,
            uniqueness_score=0.5,  # Average score for fallback
            harmony_score=0.5,
            accessibility_score=0.5
        )


if __name__ == "__main__":
    # Test the palette generator
    generator = UniqueColorPaletteGenerator()

    # Mock competitor colors for testing
    from color_extractor import ColorInfo

    mock_competitor_colors = [
        [  # Uber-like colors
            ColorInfo("#000000", (0, 0, 0), (0, 0, 0), 0.8, "primary"),
            ColorInfo("#ffffff", (255, 255, 255), (0, 0, 100), 0.6, "secondary")
        ],
        [  # Lyft-like colors
            ColorInfo("#ff00bf", (255, 0, 191), (312, 100, 50), 0.9, "primary"),
            ColorInfo("#ffffff", (255, 255, 255), (0, 0, 100), 0.5, "secondary")
        ]
    ]

    themes = ['modern', 'vibrant', 'professional', 'muted']

    for theme in themes:
        print(f"\nGenerating {theme} palette:")
        palette = generator.generate_unique_palette(mock_competitor_colors, theme, 5)

        print(f"Theme: {palette.theme}")
        print(f"Uniqueness: {palette.uniqueness_score:.2f}")
        print(f"Harmony: {palette.harmony_score:.2f}")
        print(f"Accessibility: {palette.accessibility_score:.2f}")
        print("Colors:")

        for color in palette.colors:
            print(f"  {color.hex} ({color.role}) - HSL: {color.hsl[0]:.0f}°, {color.hsl[1]:.0f}%, {color.hsl[2]:.0f}%")
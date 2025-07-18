import pandas as pd
import re

EXCEL_FILE = 'Z0MATERIAL_ATTRB_REP01_00000.xlsx'
OUTPUT_FILE = 'device_alias_mapping.csv'

# Helper to generate aliases

def generate_aliases(device_name):
    aliases = set()
    # Always include the original
    aliases.add(device_name)
    # Lower, title, and upper case
    aliases.add(device_name.lower())
    aliases.add(device_name.title())
    aliases.add(device_name.upper())
    # Remove memory size
    no_mem = re.sub(r'\b(\d+G|\d+GB|\d+T|\d+TB)\b', '', device_name, flags=re.IGNORECASE)
    # Remove color words (common ones)
    no_color = re.sub(r'\b(BLACK|WHITE|SILVER|GOLD|BLUE|RED|GREEN|PINK|PURPLE|GRAY|GREY|YELLOW|ORANGE|BROWN|MIDNIGHT|GRAPHITE|SPACE|CORAL|LAVENDER|VIOLET|TITANIUM|NATURAL|CREAM|MINT|LIME|OLIVE|BRONZE|COPPER|PEACH|SAND|SKY|SUNSET|OCEAN|AQUA|TEAL|ROSE|BURGUNDY|BEIGE|CHARCOAL|PLATINUM|PEARL|IVORY|CHAMPAGNE|MOCHA|ONYX|SAPPHIRE|EMERALD|AMBER|CLOUD|FROST|ICE|SNOW|STORM|SHADOW|SLATE|STONE|STEEL|ALPINE|PACIFIC|FOREST|CLOUD|DAWN|DUSK|TWILIGHT|STARDUST|MOON|STAR|NIGHT|DAY|DAWN|DUSK|MORNING|EVENING|SUN|MOON|STAR|GALAXY|COSMIC|ASTRO|LUNAR|SOLAR|METEOR|COMET|NEBULA|ORBIT|AURORA|POLAR|ARCTIC|DESERT|TUNDRA|GLACIER|VOLCANO|LAVA|MAGMA|FIRE|EMBER|ASH|COAL|CARBON|GRAPHITE|IRON|LEAD|ZINC|TIN|COPPER|BRASS|BRONZE|GOLD|SILVER|PLATINUM|DIAMOND|PEARL|RUBY|SAPPHIRE|EMERALD|AMETHYST|TOPAZ|OPAL|JADE|ONYX|QUARTZ|TURQUOISE|CORAL|IVORY|JET|OBSIDIAN|PEARL|SAND|SHELL|STONE|WOOD|BAMBOO|MAPLE|OAK|PINE|WALNUT|CHERRY|MAHOGANY|TEAK|EBONY|ASH|BIRCH|CEDAR|FIR|HEMLOCK|LARCH|POPLAR|REDWOOD|SEQUOIA|SPRUCE|SYCAMORE|WILLOW|YELLOW|ZEBRA|ZIRCON)\b', '', no_mem, flags=re.IGNORECASE)
    # Remove extra spaces
    cleaned = re.sub(r'\s+', ' ', no_color).strip()
    # Add cleaned, lower, title, upper
    aliases.add(cleaned)
    aliases.add(cleaned.lower())
    aliases.add(cleaned.title())
    aliases.add(cleaned.upper())
    # Add marketing style (no spaces, dashes)
    aliases.add(cleaned.replace(' ', ''))
    aliases.add(cleaned.replace(' ', '-'))
    # Add short forms (remove brand prefix)
    for prefix in ['TMO ', 'MOT ', 'GGL ', 'SAM ', 'APL ', 'LG ', 'NOK ', 'HUA ', 'HTC ', 'SONY ', 'MSFT ', 'ZTE ', 'OP ', 'ONEPLUS ', 'GOOGLE ', 'APPLE ', 'SAMSUNG ']:
        if cleaned.upper().startswith(prefix):
            short = cleaned[len(prefix):].strip()
            aliases.add(short)
            aliases.add(short.lower())
            aliases.add(short.title())
            aliases.add(short.upper())
            aliases.add(short.replace(' ', ''))
            aliases.add(short.replace(' ', '-'))
    # Remove duplicates and short/empty
    return [a for a in set(aliases) if len(a) > 2]

def main():
    df = pd.read_excel(EXCEL_FILE, header=7)
    df.columns = [str(c).strip() for c in df.columns]
    device_col = 'Model(External)'
    unique_names = sorted(df[device_col].dropna().unique())
    rows = []
    for name in unique_names:
        for alias in generate_aliases(name):
            rows.append({'marketing_alias': alias, 'manufacturer_name': name})
    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_FILE, index=False)
    print(f"Wrote {len(out)} alias mappings for {len(unique_names)} devices to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

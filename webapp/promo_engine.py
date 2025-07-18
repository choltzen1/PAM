import argparse
import sys
from promo.parsers     import parse_pdt_line
from promo.builders    import generate_eligibility_insert

def main():
    parser = argparse.ArgumentParser(
        description="Convert a raw PDT line into a PROMO_ELIGIBILITY_RULES INSERT"
    )
    # Existing flag
    parser.add_argument(
        "--pdt-line",
        help="The exact tab-separated line from PDT (wrap in quotes)"
    )
    # New flag for file input
    parser.add_argument(
        "--pdt-file",
        type=argparse.FileType('r'),
        help="Path to a file containing the raw PDT line"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print SQL without executing"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show debug information during parsing"
    )
    args = parser.parse_args()

    # Decide where to read the PDT line from
    if args.pdt_file:
        raw_line = args.pdt_file.read().strip()
    elif args.pdt_line:
        raw_line = args.pdt_line
    else:
        parser.error("You must provide either --pdt-line or --pdt-file")

    # 1. Parse it into a structured dict
    data = parse_pdt_line(raw_line)
    
    # Show debug info if requested
    if args.debug:
        print("=== PARSED DATA ===")
        for key, value in data.items():
            print(f"{key}: {value}")
        print("=== END DEBUG ===\n")

    # 2. Generate the full INSERT statement
    sql = generate_eligibility_insert(data)

    # 3. Print to stdout (or later, execute if not dry-run)
    print(sql)

if __name__ == "__main__":
    main()
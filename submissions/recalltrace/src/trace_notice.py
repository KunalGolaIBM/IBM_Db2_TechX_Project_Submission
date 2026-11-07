"""Verify quoted identifiers and look up reviewed inventory lots."""

import argparse
import json
import re
from pathlib import Path


def identifier_pattern(code):
    return rf"(?<![\w-]){re.escape(code)}(?![\w-])"


def check_identifier(notice, entry):
    if not isinstance(entry, dict):
        raise ValueError("Each selected identifier needs a code and a source quote.")
    code, quote = entry.get("code"), entry.get("quote")
    if not isinstance(code, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,31}", code):
        raise ValueError("Use the exact uppercase product or lot code.")
    if not isinstance(quote, str) or not quote.strip() or len(quote) > 280 or quote not in notice:
        raise ValueError(f"The quote for {code} must appear verbatim in the notice.")
    if not re.search(identifier_pattern(code), quote):
        raise ValueError(f"The quote does not contain the exact identifier {code}.")
    return code


def validate_selection(notice, selection):
    if not isinstance(notice, str) or not notice.strip() or len(notice) > 12_000:
        raise ValueError("Provide a notice between 1 and 12,000 characters.")
    if not isinstance(selection, dict):
        raise ValueError("The selection must be a JSON object.")
    lots = selection.get("lots")
    if not isinstance(lots, list) or not 1 <= len(lots) <= 20:
        raise ValueError("Select between one and twenty lots.")
    product_code = check_identifier(notice, selection.get("product"))
    lot_codes = [check_identifier(notice, lot) for lot in lots]
    if len(set(lot_codes)) != len(lot_codes):
        raise ValueError("Each lot must appear once in the selection.")
    return product_code, lot_codes


def review_notice(notice, selection, *, lookup=False):
    product_code, lot_codes = validate_selection(notice, selection)
    result = {"product_code": product_code, "lot_codes": lot_codes, "evidence": selection}
    if lookup:
        from db import find_matches

        matches = find_matches(product_code, lot_codes)
        result["inventory"] = matches
        result["total_units"] = sum(row["quantity"] for row in matches)
        result["unmatched_lots"] = sorted(set(lot_codes) - {row["lot_code"] for row in matches})
    return result


def main():
    from db import Db2Error

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notice", type=Path)
    parser.add_argument("selection", type=Path)
    parser.add_argument("--lookup", action="store_true", help="Query Db2 after reviewing the selected identifiers and their scope.")
    args = parser.parse_args()
    try:
        notice = args.notice.read_text(encoding="utf-8")
        selection = json.loads(args.selection.read_text(encoding="utf-8"))
        result = review_notice(notice, selection, lookup=args.lookup)
    except (OSError, ValueError) as error:
        parser.exit(2, f"{error}\n")
    except Db2Error as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

"""Khata AI - command line version.   Run:  python app.py"""
from db import (
    get_history,
    get_pending,
    get_total_outstanding,
    load_demo_data,
    reset_data,
    setup_schema,
    add_entry,
)
from llm import ai_available, parse_entry, write_reminder


def do_add_entry():
    text = input("\nEntry likho (e.g. Sharma ji ne 200 ka udhaar liya, doodh aur bread): ").strip()
    if not text:
        return
    try:
        entry, source = parse_entry(text)
    except ValueError as err:
        print("Samajh nahi aaya:", err)
        return
    print(f"\nSamjha ({source}):")
    print(f"  Naam   : {entry.name}")
    print(f"  Type   : {entry.entry_type}")
    print(f"  Amount : Rs {entry.amount:.2f}")
    print(f"  Note   : {entry.note or '-'}")
    if input("Save karun? (y/n): ").strip().lower() == "y":
        add_entry(entry.name, entry.amount, entry.entry_type, entry.note)
        print("Saved ✔")
    else:
        print("Cancel kiya.")


def do_pending():
    rows = get_pending()
    if not rows:
        print("\nKoi udhaar baaki nahi 🎉")
        return
    print(f"\n{'Naam':<20}{'Baaki (Rs)':>12}{'Din purana':>14}")
    print("-" * 46)
    for name, balance, days in rows:
        print(f"{name:<20}{balance:>12.2f}{days:>14}")
    print("-" * 46)
    print(f"{'Total baaki':<20}{get_total_outstanding():>12.2f}")


def do_history():
    name = input("\nCustomer ka naam (ya naam ka hissa): ").strip()
    if not name:
        return
    rows = get_history(name)
    if not rows:
        print("Koi entry nahi mili.")
        return
    print(f"\n{'Naam':<16}{'Date':<12}{'Type':<9}{'Amount':>10}  Note")
    print("-" * 62)
    for cname, d, etype, amount, note in rows:
        print(f"{cname:<16}{str(d):<12}{etype:<9}{amount:>10.2f}  {note or ''}")


def do_reminders():
    rows = get_pending()
    if not rows:
        print("\nKisi ko reminder bhejne ki zaroorat nahi 🎉")
        return
    for name, balance, days in rows:
        print(f"\n--- {name} (Rs {balance:.0f}, {days} din) ---")
        print(write_reminder(name, balance, days))


def main():
    print("=" * 46)
    print("  KHATA AI  -  dukaan ka smart udhaar khata")
    print("=" * 46)
    print("AI mode:", "ON (Gemini)" if ai_available() else "OFF (offline parser; set GOOGLE_API_KEY)")
    try:
        setup_schema()
    except Exception as err:  # noqa: BLE001
        print("\nDb2 se connect nahi ho paya:", err)
        print("Check karo: Db2 container chal raha hai? .env ki details sahi hain?")
        return

    while True:
        print(
            "\n1) Nayi entry   2) Pending report   3) Customer history\n"
            "4) Reminders    5) Demo data load   6) Sab data delete   7) Exit"
        )
        choice = input("Choose: ").strip()
        try:
            if choice == "1":
                do_add_entry()
            elif choice == "2":
                do_pending()
            elif choice == "3":
                do_history()
            elif choice == "4":
                do_reminders()
            elif choice == "5":
                print(f"{load_demo_data()} demo entries add ho gayi.")
            elif choice == "6":
                if input("Pakka SAB data delete karna hai? (yes/no): ").strip().lower() == "yes":
                    reset_data()
                    print("Data delete ho gaya.")
            elif choice == "7":
                print("Bye!")
                break
        except Exception as err:  # noqa: BLE001
            print("Error:", err)


if __name__ == "__main__":
    main()

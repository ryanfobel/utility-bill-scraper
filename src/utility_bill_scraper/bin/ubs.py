import argparse
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.join("..", ".."))


def update(utility_name, user, password, history_path, statement_path, max_downloads):
    if utility_name == "Kitchener Utilities":
        import utility_bill_scraper.kitchener_utilities as ku

        api = ku.KitchenerUtilitiesAPI(user, password, history_path, statement_path)
    else:
        print(f"Unsupported utility: {utility_name}")

    updates = api.update(max_downloads=max_downloads)
    if updates is not None:
        print(f"Downloaded {len(updates)} new statements")
    else:
        print("No new updates")


def export(utility_name, history_path, output=None):
    if utility_name == "Kitchener Utilities":
        import utility_bill_scraper.kitchener_utilities as ku

        api = ku.KitchenerUtilitiesAPI(history_path=history_path)
    else:
        print(f"Unsupported utility: {utility_name}")

    df = api.cached_history()
    ext = os.path.splitext(output.lower())[-1]
    if ext == ".csv":
        df.to_csv(output)
    elif ext == ".xlsx":
        df.to_excel(output)


def main():
    parser = argparse.ArgumentParser(description="ubs (Utility bill scraper)")
    parser.add_argument("-e", "--env", help="path to .env file.")
    parser.add_argument("--history-path", help=".xls,.csv, or url of the history file.")
    parser.add_argument("--utility-name", help="Name of the utility.")

    subparsers = parser.add_subparsers(
        title="subcommands", dest="subcommand", help="available sub-commands."
    )
    subparsers.required = True
    parser_update = subparsers.add_parser("update")
    parser_update.add_argument("-u", "--user", help="user name")
    parser_update.add_argument("-p", "--password", help="password")
    parser_update.add_argument(
        "--statement-path", help="path to save downloaded statements"
    )
    parser_update.add_argument(
        "-m", "--max-downloads", help="maximum number of statements to download"
    )

    parser_export = subparsers.add_parser("export")
    parser_export.add_argument("-o", "--output", help="export file path.")

    args = parser.parse_args(sys.argv[1:])

    # If the user passed a .env path, load the environment.
    if args.env:
        load_dotenv(args.env, override=True)

    utility_name = args.utility_name or os.getenv("UTILITY_NAME")
    history_path = args.history_path or os.getenv("HISTORY_PATH")

    def missing_required_arg(arg):
        sys.stderr.write(f"Error: no `{arg}` set.\n")
        parser.print_help()
        sys.exit(2)

    if utility_name is None:
        missing_required_arg("utility-name")

    if args.subcommand == "update":
        user = args.user or os.getenv("USER")
        password = args.password or os.getenv("PASSWORD")
        statement_path = args.statement_path or os.getenv("STATEMENT_PATH")
        max_downloads = int(args.max_downloads or os.getenv("MAX_DOWNLOADS"))
        if user is None:
            missing_required_arg("user")
        if password is None:
            missing_required_arg("password")
        update(
            utility_name, user, password, history_path, statement_path, max_downloads
        )
    elif args.subcommand == "export":
        output = args.output or os.getenv("OUTPUT")
        if output is None:
            missing_required_arg("output")
        export(utility_name, history_path, output)


if __name__ == "__main__":
    main()

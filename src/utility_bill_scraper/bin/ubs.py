import argparse
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.join("..", ".."))


def update(
    utility_name,
    user,
    password,
    data_path,
    save_statements,
    max_downloads,
    google_sa_credentials,
):
    if utility_name == "Kitchener Utilities":
        import utility_bill_scraper.canada.on.kitchener_utilities as ku

        api = ku.KitchenerUtilitiesAPI(
            user,
            password,
            data_path=data_path,
            save_statements=save_statements,
            google_sa_credentials=google_sa_credentials,
        )
    else:
        print(f"Unsupported utility: {utility_name}")

    updates = api.update(max_downloads=max_downloads)
    if updates is not None:
        print(f"Downloaded {len(updates)} new statements")
    else:
        print("No new updates")


def export(utility_name, data_path, output, google_sa_credentials):
    if utility_name == "Kitchener Utilities":
        import utility_bill_scraper.canada.on.kitchener_utilities as ku

        api = ku.KitchenerUtilitiesAPI(data_path=data_path)
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
    parser.add_argument("-e", "--env", help="path to .env file")
    parser.add_argument("--data-path", help="folder containing the history file")
    parser.add_argument("--utility-name", help="name of the utility")
    parser.add_argument(
        "--google-sa-credentials", help="google service account credentials"
    )

    subparsers = parser.add_subparsers(
        title="subcommands", dest="subcommand", help="available sub-commands"
    )
    subparsers.required = True
    parser_update = subparsers.add_parser("update")
    parser_update.add_argument("-u", "--user", help="user name")
    parser_update.add_argument("-p", "--password", help="password")
    parser_update.add_argument(
        "--save-statements", help="save downloaded statements (default=True)"
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
    data_path = args.data_path or os.getenv("DATA_PATH")
    google_sa_credentials = args.google_sa_credentials or os.getenv(
        "GOOGLE_SA_CREDENTIALS"
    )

    from utility_bill_scraper import is_gdrive_path

    def missing_required_arg(arg):
        sys.stderr.write(f"Error: no `{arg}` set.\n")
        parser.print_help()
        sys.exit(2)

    if is_gdrive_path(data_path) and google_sa_credentials:
        missing_required_arg("google-sa-credentials")

    if utility_name is None:
        missing_required_arg("utility-name")

    if args.subcommand == "update":
        user = args.user or os.getenv("USER")
        password = args.password or os.getenv("PASSWORD")

        # Default for save statements is True
        save_statements = os.getenv("SAVE_STATEMENTS", True)
        # Override with command line argument.
        if args.save_statements:
            save_statements = args.save_statements.lower() in ("true", "1")

        max_downloads = args.max_downloads or os.getenv("MAX_DOWNLOADS")
        if max_downloads:
            max_downloads = int(max_downloads)
        if user is None:
            missing_required_arg("user")
        if password is None:
            missing_required_arg("password")
        update(
            utility_name,
            user,
            password,
            data_path,
            save_statements,
            max_downloads,
            google_sa_credentials,
        )
    elif args.subcommand == "export":
        output = args.output or os.getenv("OUTPUT")
        if output is None:
            missing_required_arg("output")
        export(utility_name, data_path, output, google_sa_credentials)


if __name__ == "__main__":
    main()

"""Read-only PythonAnywhere task inventory. Never creates tasks or sends email.

Run on PythonAnywhere after generating an API token in Account > API Token.
The host supplies API_TOKEN in newly opened consoles. A successful listing does
not prove an unused Always-on quota slot; confirm that on Account and Tasks.
"""
import argparse
import getpass
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default=getpass.getuser())
    parser.add_argument("--host", choices=["www.pythonanywhere.com", "eu.pythonanywhere.com"], default="www.pythonanywhere.com")
    args = parser.parse_args()
    token = os.getenv("API_TOKEN")
    if not token:
        sys.exit("API_TOKEN unavailable. Check Account > API Token and open a new console, or inspect Account/Tasks manually.")
    for endpoint in ("always_on", "schedule"):
        url = f"https://{args.host}/api/v0/user/{quote(args.username, safe='')}/{endpoint}/"
        request = Request(url, headers={"Authorization": f"Token {token}"})
        try:
            with urlopen(request, timeout=20) as response:
                data = json.load(response)
        except HTTPError as exc:
            sys.exit(f"{endpoint}: HTTP {exc.code}; account capability not verified. Inspect Account/Tasks.")
        except URLError:
            sys.exit(f"{endpoint}: connection failed; account capability not verified.")
        print(f"{endpoint}: API access verified")
        if isinstance(data, list):
            print(json.dumps([{k: row.get(k) for k in ("id", "enabled", "state") if k in row} for row in data]))
    print("Confirm a paid plan and an available Always-on slot on Account/Tasks before enabling the 30-second worker.")


if __name__ == "__main__":
    main()

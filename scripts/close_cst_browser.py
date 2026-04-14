#!/usr/bin/env python3
import argparse
import sys

from browser_session import browser_choices, close_browser_instance


def main():
    parser = argparse.ArgumentParser(description="关闭 finance.ERP 专用自动化浏览器并验证结果")
    parser.add_argument(
        "--browser",
        choices=["auto", "edge", "chrome"],
        default="auto",
        help="关闭哪个浏览器；默认 auto",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="关闭后校验秒数，默认 5",
    )
    args = parser.parse_args()

    messages = []
    all_ok = True
    for browser in browser_choices(args.browser):
        ok, message = close_browser_instance(browser, timeout=max(args.timeout, 0.5))
        messages.append(message)
        all_ok = all_ok and ok

    for message in messages:
        print(message)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

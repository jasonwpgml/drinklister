#!/usr/bin/env python3
"""Discord 음료 주문 추출기

- Discord에서 복사한 메시지를 붙여넣어 주문자/메뉴/온도/사이즈/수량/옵션을 추출
- CSV 저장, 요약 복사 지원
- 외부 패키지 없이 Python 표준 라이브러리만 사용

실행:
    python discord_drink_order_extractor.py
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import tkinter as tk
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk


# -----------------------------------------------------------------------------
# 1) 매장 메뉴에 맞게 이 부분을 수정하세요.
#    왼쪽은 CSV에 표시할 정식 메뉴명, 오른쪽은 사람들이 쓸 법한 별칭입니다.
# -----------------------------------------------------------------------------
DEFAULT_MENU_ALIASES: dict[str, list[str]] = {
    "에스프레소": ["에스프레소"],
    "아이스 아메리카노": [
        "아이스 아메리카노",
        "아이스아메리카노",
        "아아",
        "아메리카노 아이스",
        "아메 아이스",
    ],
    "아메리카노": ["아메리카노", "따뜻한 아메리카노"],
    "카페라떼": ["카페라떼", "카페 라떼", "라떼"],
    "바닐라빈라떼": ["바닐라라떼", "바닐라 라떼", "바닐라빈라떼", "바닐라빈 라떼"],
    "헤이즐넛라떼": ["헤이즐넛라떼", "헤이즐넛 라떼", "헤이즐럿 라떼", "헤이즐럿라떼"],
    "콜드브루": ["콜드브루"],
    "콜드브루라떼": ["콜드브루 라떼", "콜드브루라떼", "라떼 콜드브루"],
    "모카라떼": ["카페모카", "카페 모카", "모카", "모카라떼"],
    "더블초코라떼": ["더블초코라떼", "초코 라떼", "초코라떼", "핫초코"],
    "말차라떼": ["녹차라떼", "녹차 라떼", "말차라떼", "말차 라떼"],
    "곡물라떼": ["곡물라떼", "곡물 라떼", "미숫가루"],
    "딸기라떼(only iced)": ["딸기라떼", "딸기 라떼"],
    "레몬에이드": ["레몬에이드", "레몬 에이드"],
    "자몽에이드": ["자몽에이드", "자몽 에이드"],
    "청포도에이드": ["청포도에이드", "청포도 에이드"],
    "매실에이드": ["매실에이드", "매실 에이드"],
    "유자에이드": ["유자에이드", "유자 에이드"],
    "복숭아아이스티": ["복숭아아이스티", "복숭아 아이스티", "아이스티"],
    "아샷추": ["아샷추"],
    "매샷추": ["매샷추"],
}

CONFIG_PATH = Path(__file__).with_name("menu_aliases.json")
MENU_ALIASES: dict[str, list[str]] = {}


def load_menu_aliases(path: Path | None = None) -> dict[str, list[str]]:
    config_path = path or CONFIG_PATH
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                raw_data = json.load(handle)
            if isinstance(raw_data, dict):
                normalized: dict[str, list[str]] = {}
                for canonical, aliases in raw_data.items():
                    if not isinstance(aliases, list):
                        continue
                    cleaned_aliases = [
                        str(alias).strip() for alias in aliases if str(alias).strip()
                    ]
                    if cleaned_aliases:
                        normalized[str(canonical).strip()] = cleaned_aliases
                if normalized:
                    return normalized
        except (json.JSONDecodeError, OSError):
            pass

    return {
        canonical: [alias for alias in aliases if alias]
        for canonical, aliases in DEFAULT_MENU_ALIASES.items()
    }


def save_menu_aliases(
    menu_aliases: dict[str, list[str]], path: Path | None = None
) -> None:
    config_path = path or CONFIG_PATH
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(menu_aliases, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def configure_menu_aliases_from_console() -> dict[str, list[str]]:
    print("메뉴와 별칭을 콘솔에서 수정합니다.")
    print("형식: 메뉴명=별칭1,별칭2")
    print("예: 아메리카노=아메리카노,따뜻한 아메리카노")
    print("빈 줄 입력 시 저장하고 종료합니다.")
    print("메뉴명만 입력하고 별칭을 비우면 해당 메뉴를 제거합니다.")

    menu_aliases = dict(MENU_ALIASES)
    while True:
        try:
            user_input = input("설정 입력 > ").strip()
        except KeyboardInterrupt:
            print("\n입력 취소: 현재 변경 사항은 저장되지 않았습니다.")
            return menu_aliases
        except EOFError:
            print("\n입력 종료: 기본 설정을 유지합니다.")
            break

        if not user_input:
            break
        if user_input.lower() in {"q", "quit", "exit"}:
            print("입력 종료: 변경 사항을 저장합니다.")
            break
        if "=" not in user_input:
            print("형식 오류: 메뉴명=별칭1,별칭2")
            continue

        canonical, alias_text = user_input.split("=", 1)
        canonical = canonical.strip()
        aliases = [item.strip() for item in alias_text.split(",") if item.strip()]
        if not canonical:
            print("메뉴명을 입력해 주세요.")
            continue
        if aliases:
            menu_aliases[canonical] = aliases
            print(f"저장됨: {canonical} -> {aliases}")
        else:
            menu_aliases.pop(canonical, None)
            print(f"삭제됨: {canonical}")

    save_menu_aliases(menu_aliases)
    return menu_aliases


def reload_menu_aliases() -> None:
    global MENU_ALIASES, ALIAS_INDEX
    MENU_ALIASES = load_menu_aliases()
    ALIAS_INDEX = build_alias_index()


MENU_ALIASES = load_menu_aliases()


SIZE_PATTERNS: list[tuple[str, str]] = [
    ("V", r"(?<![A-Za-z])(?:벤티|venti|V)(?![A-Za-z])"),
    ("G", r"(?<![A-Za-z])(?:그란데|grande|G)(?![A-Za-z])"),
    ("L", r"(?<![A-Za-z])(?:라지|large|L)(?![A-Za-z])"),
    ("M", r"(?<![A-Za-z])(?:미디엄|미듐|medium|M)(?![A-Za-z])"),
    ("S", r"(?<![A-Za-z])(?:스몰|small|S)(?![A-Za-z])"),
    ("T", r"(?<![A-Za-z])(?:톨|tall|T)(?![A-Za-z])"),
]

KOREAN_NUMBERS: dict[str, int] = {
    "한": 1,
    "하나": 1,
    "두": 2,
    "둘": 2,
    "세": 3,
    "셋": 3,
    "네": 4,
    "넷": 4,
    "다섯": 5,
    "여섯": 6,
    "일곱": 7,
    "여덟": 8,
    "아홉": 9,
    "열": 10,
}

OPTION_PATTERNS: list[tuple[str, str]] = [
    ("샷 추가", r"(?:샷\s*추가|추가\s*샷|엑스트라\s*샷)"),
    ("샷 빼기", r"(?:샷\s*빼(?:기|고)?|샷\s*없이|노\s*샷)"),
    ("디카페인", r"(?:디카페인|decaf)"),
    ("얼음 적게", r"(?:얼음\s*(?:적게|조금|반만)|라이트\s*아이스)"),
    ("얼음 많이", r"(?:얼음\s*(?:많이|가득)|엑스트라\s*아이스)"),
    ("얼음 없이", r"(?:얼음\s*(?:없이|빼고)|노\s*아이스)"),
    ("덜 달게", r"(?:덜\s*달게|안\s*달게|당도\s*(?:0|30|삼십)\s*%?)"),
    ("더 달게", r"(?:더\s*달게|많이\s*달게)"),
    ("시럽 추가", r"(?:시럽\s*추가)"),
    ("시럽 빼기", r"(?:시럽\s*(?:빼(?:기|고)?|없이)|노\s*시럽)"),
    ("휘핑 추가", r"(?:휘핑(?:크림)?\s*(?:추가|많이))"),
    ("휘핑 빼기", r"(?:휘핑(?:크림)?\s*(?:빼(?:기|고)?|없이)|노\s*휘핑)"),
    ("우유 변경", r"(?:(?:두유|오트|저지방|무지방)\s*(?:우유)?(?:로|변경)?)"),
    ("따로 포장", r"(?:따로\s*포장|별도\s*포장)"),
]


@dataclass(slots=True)
class Message:
    user: str
    text: str


@dataclass(slots=True)
class Order:
    user: str
    menu: str
    temperature: str
    size: str
    quantity: int
    options: str
    note: str
    source: str
    decaf_count: int = 0


# 별칭이 겹칠 때 긴 표현을 먼저 선택합니다.
def build_alias_index() -> list[tuple[str, str]]:
    aliases: list[tuple[str, str]] = []
    for canonical, names in MENU_ALIASES.items():
        for alias in set([canonical, *names]):
            aliases.append((alias, canonical))
    return sorted(aliases, key=lambda row: len(row[0]), reverse=True)


ALIAS_INDEX = build_alias_index()


def parse_discord_text(text: str) -> list[Message]:
    """여러 형태의 Discord 복사 텍스트를 사용자와 본문으로 나눕니다."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    messages: list[Message] = []
    current_user: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_user, current_lines
        body = " ".join(line.strip() for line in current_lines if line.strip()).strip()
        if body:
            messages.append(Message(current_user or "알 수 없음", body))
        current_user = None
        current_lines = []

    # [오후 3:20] 제이슨: 아아 2잔
    bracket_colon = re.compile(r"^\s*\[[^\]]+\]\s*([^:]{1,50}):\s*(.+?)\s*$")

    # 제이슨: 아아 2잔
    plain_colon = re.compile(r"^\s*([^:\n]{1,50}):\s*(.+?)\s*$")

    # 제이슨 — 오후 3:20
    # 제이슨 - 2026. 7. 16. 오후 3:20
    discord_header = re.compile(
        r"^\s*(.{1,50}?)\s*[—–-]\s*"
        r"(?:(?:오늘|어제)\s*)?"
        r"(?:(?:\d{4}[./-]\s*\d{1,2}[./-]\s*\d{1,2}[.]?\s*)?)"
        r"(?:(?:오전|오후)\s*)?\d{1,2}:\d{2}(?::\d{2})?.*$"
    )

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        match = bracket_colon.match(line)
        if match:
            flush()
            messages.append(Message(match.group(1).strip(), match.group(2).strip()))
            continue

        match = discord_header.match(line)
        if match:
            flush()
            current_user = match.group(1).strip()
            continue

        match = plain_colon.match(line)
        if match:
            possible_user = match.group(1).strip()
            # URL이나 단독 시각을 사용자명으로 오인하는 경우를 방지합니다.
            if (
                not re.match(r"^(?:https?|ftp)$", possible_user, re.I)
                and not possible_user.isdigit()
            ):
                flush()
                messages.append(Message(possible_user, match.group(2).strip()))
                continue

        current_lines.append(line)

    flush()
    return messages


def find_menu_mentions(text: str) -> list[tuple[int, int, str, str]]:
    candidates: list[tuple[int, int, str, str]] = []
    for alias, canonical in ALIAS_INDEX:
        for match in re.finditer(re.escape(alias), text, re.I):
            candidates.append((match.start(), match.end(), alias, canonical))

    # 같은 위치에서는 긴 별칭 우선. 서로 겹치는 짧은 별칭은 제거합니다.
    candidates.sort(key=lambda row: (row[0], -(row[1] - row[0])))
    selected: list[tuple[int, int, str, str]] = []
    for candidate in candidates:
        start, end, _, _ = candidate
        overlaps = any(not (end <= s or start >= e) for s, e, _, _ in selected)
        if not overlaps:
            selected.append(candidate)
    return sorted(selected, key=lambda row: row[0])


def extract_quantity(text: str, default: int = 1) -> int:
    match = re.search(r"(\d+)\s*(?:잔|개|병|컵)", text)
    if match:
        return max(1, int(match.group(1)))

    match = re.search(
        r"(한|하나|두|둘|세|셋|네|넷|다섯|여섯|일곱|여덟|아홉|열)\s*(?:잔|개|병|컵)",
        text,
    )
    if match:
        return KOREAN_NUMBERS[match.group(1)]

    match = re.search(r"(?:수량|qty)\s*[:=]?\s*(\d+)", text, re.I)
    if match:
        return max(1, int(match.group(1)))

    return default


def extract_size(text: str) -> str:
    for size, pattern in SIZE_PATTERNS:
        if re.search(pattern, text, re.I):
            return size
    return ""


def extract_decaf_count(text: str) -> int:
    match = re.search(r"디카페인\s*(\d+)\s*(?:잔|개|컵|병)?", text)
    if match:
        return max(0, int(match.group(1)))

    match = re.search(r"(\d+)\s*(?:잔|개|컵|병)\s*디카페인", text)
    if match:
        return max(0, int(match.group(1)))

    if re.search(r"(?:디카페인|decaf)", text, re.I):
        return 1
    return 0


def extract_temperature(text: str, canonical_menu: str) -> str:
    if canonical_menu.startswith("아이스 ") or canonical_menu.endswith("아이스티"):
        return "ICE"
    if re.search(r"(?:핫|따뜻|뜨겁|hot)", text, re.I):
        return "HOT"
    if re.search(r"(?:아이스|차갑게|iced|ice)", text, re.I):
        return "ICE"
    return "ICE"


def extract_options(text: str, decaf_count: int = 0) -> str:
    found: list[str] = []

    # 일부 수량에만 옵션이 적용되는 흔한 표현
    if re.search(r"(?:하나는|한\s*잔은|1\s*잔은|한\s*잔만)\s*샷\s*추가", text):
        found.append("1잔만 샷 추가")

    for label, pattern in OPTION_PATTERNS:
        if re.search(pattern, text, re.I):
            if label == "샷 추가" and "1잔만 샷 추가" in found:
                continue
            if label == "디카페인" and decaf_count > 0:
                continue
            found.append(label)

    match = re.search(r"샷\s*(\d+)\s*(?:개|번)?\s*추가", text)
    if match:
        found = [item for item in found if item != "샷 추가"]
        found.append(f"샷 {match.group(1)}개 추가")

    # 중복 제거, 원래 순서 보존
    return ", ".join(dict.fromkeys(found))


def clean_note(segment: str, alias: str) -> str:
    """알아낸 요소를 지운 뒤 남는 텍스트를 확인용 비고로 보존합니다."""
    cleaned = re.sub(re.escape(alias), " ", segment, count=1, flags=re.I)

    for _, pattern in SIZE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.I)

    cleaned = re.sub(r"\d+\s*(?:잔|개|병|컵)", " ", cleaned)
    cleaned = re.sub(
        r"(?:한|하나|두|둘|세|셋|네|넷|다섯|여섯|일곱|여덟|아홉|열)\s*(?:잔|개|병|컵)",
        " ",
        cleaned,
    )
    cleaned = re.sub(
        r"(?:아이스|차갑게|iced|ice|핫|따뜻하게|뜨겁게|hot)", " ", cleaned, flags=re.I
    )

    for _, pattern in OPTION_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.I)

    cleaned = re.sub(
        r"(?:주세요|주세용|부탁(?:해요|드립니다)?|으로|이랑|랑|하고|그리고|하나는|하난|하나만)",
        " ",
        cleaned,
    )
    cleaned = re.sub(r"[\s,;/+·]+", " ", cleaned).strip(" .-")
    return cleaned


def segment_start_for_mention(
    text: str, mentions: list[tuple[int, int, str, str]], index: int
) -> int:
    """메뉴 앞의 ICE/HOT 같은 정보는 포함하되 이전 메뉴 내용은 섞지 않습니다."""
    start = mentions[index][0]
    if index == 0:
        return 0

    previous_end = mentions[index - 1][1]
    between = text[previous_end:start]
    separator_matches = list(
        re.finditer(r"[,;/+·]|(?:그리고)|(?:하고)|(?:또는)|(?:및)", between)
    )
    if separator_matches:
        return previous_end + separator_matches[-1].end()

    # 구분자가 없다면 이전 주문의 수량/사이즈가 섞이지 않도록 메뉴 위치부터 시작합니다.
    return start


def parse_order_segment(
    user: str,
    segment: str,
    alias: str,
    canonical: str,
    source: str,
) -> Order:
    decaf_count = extract_decaf_count(segment)
    return Order(
        user=user,
        menu=canonical,
        temperature=extract_temperature(segment, canonical),
        size=extract_size(segment),
        quantity=extract_quantity(segment),
        options=extract_options(segment, decaf_count),
        note=clean_note(segment, alias),
        source=source,
        decaf_count=decaf_count,
    )


def extract_orders(messages: list[Message]) -> list[Order]:
    orders: list[Order] = []
    orders_by_user: dict[str, list[Order]] = defaultdict(list)
    last_batch_by_user: dict[str, list[Order]] = {}
    previous_batch: list[Order] = []

    for message in messages:
        text = message.text.strip()
        mentions = find_menu_mentions(text)

        if mentions:
            current_batch: list[Order] = []
            for index, (start, _end, alias, canonical) in enumerate(mentions):
                next_start = (
                    mentions[index + 1][0] if index + 1 < len(mentions) else len(text)
                )
                segment_start = segment_start_for_mention(text, mentions, index)
                segment = text[segment_start:next_start].strip(" ,;/+·")
                order = parse_order_segment(
                    message.user, segment, alias, canonical, message.text
                )
                orders.append(order)
                orders_by_user[message.user].append(order)
                current_batch.append(order)
            previous_batch = current_batch
            last_batch_by_user[message.user] = current_batch
            continue

        # "제이슨이랑 같은 거", "나도 위와 동일" 처리
        if re.search(r"(?:같은\s*거|똑같|동일|위와\s*같|위랑\s*같)", text):
            referenced_batch: list[Order] | None = None

            # 본문에 과거 주문자 이름이 명시되어 있으면 그 사람의 마지막 주문을 우선합니다.
            for past_user in reversed(list(orders_by_user.keys())):
                if (
                    past_user != message.user
                    and past_user in text
                    and last_batch_by_user.get(past_user)
                ):
                    referenced_batch = last_batch_by_user[past_user]
                    break

            if not referenced_batch:
                referenced_batch = previous_batch

            if referenced_batch:
                quantity_override = extract_quantity(text, default=-1)
                extra_decaf_count = extract_decaf_count(text)
                extra_options = extract_options(text, extra_decaf_count)
                copied_batch: list[Order] = []

                for source_order in referenced_batch:
                    options = ", ".join(
                        item for item in [source_order.options, extra_options] if item
                    )
                    copied = Order(
                        user=message.user,
                        menu=source_order.menu,
                        temperature=source_order.temperature,
                        size=source_order.size,
                        quantity=(
                            quantity_override
                            if quantity_override > 0
                            else source_order.quantity
                        ),
                        options=options,
                        note="참조 주문",
                        source=message.text,
                        decaf_count=(
                            extra_decaf_count
                            if extra_decaf_count > 0
                            else source_order.decaf_count
                        ),
                    )
                    orders.append(copied)
                    orders_by_user[message.user].append(copied)
                    copied_batch.append(copied)

                previous_batch = copied_batch
                last_batch_by_user[message.user] = copied_batch
                continue

        # 메뉴를 찾지 못했지만 주문 가능성이 높은 문장은 버리지 않고 확인 대상으로 남깁니다.
        if re.search(r"(?:잔|개|주문|주세요|부탁)", text):
            unresolved = Order(
                user=message.user,
                menu="확인 필요",
                temperature="",
                size="",
                quantity=extract_quantity(text),
                options=extract_options(text, extract_decaf_count(text)),
                note=text,
                source=message.text,
                decaf_count=extract_decaf_count(text),
            )
            orders.append(unresolved)
            orders_by_user[message.user].append(unresolved)
            previous_batch = [unresolved]
            last_batch_by_user[message.user] = [unresolved]

    return orders


def is_unconfirmed_order(order: Order) -> bool:
    return order.menu == "확인 필요" or (bool(order.note) and order.note != "참조 주문")


def make_summary(orders: list[Order]) -> str:
    confirmed_orders = [order for order in orders if not is_unconfirmed_order(order)]
    unconfirmed_orders = [order for order in orders if is_unconfirmed_order(order)]

    grouped: dict[tuple[str, str, str], dict[str, object]] = defaultdict(
        lambda: {"quantity": 0, "details": []}
    )

    for order in confirmed_orders:
        key = (order.menu, order.temperature, order.size)
        grouped[key]["quantity"] = int(grouped[key]["quantity"]) + order.quantity

        detail = f"{order.user} {order.quantity}잔"
        if order.decaf_count > 0:
            detail += f" [디카페인 {order.decaf_count}잔]"
        if order.options:
            detail += f" ({order.options})"
        if order.note and order.note != "참조 주문":
            detail += f" [확인: {order.note}]"
        grouped[key]["details"].append(detail)

    lines = ["[음료 주문 집계]", ""]
    total_quantity = 0

    if grouped:
        for (menu, temperature, size), data in sorted(grouped.items()):
            label = " / ".join(part for part in [menu, temperature, size] if part)
            quantity = int(data["quantity"])
            lines.append(f"- {label}: {quantity}잔")
            for detail in data["details"]:
                lines.append(f"  · {detail}")
            total_quantity += quantity
    else:
        lines.append("- 확인된 주문이 없습니다.")

    confirmed_customer_count = len({order.user for order in confirmed_orders})
    lines.extend(["", f"총 {total_quantity}잔 / 주문자 {confirmed_customer_count}명"])

    if unconfirmed_orders:
        lines.extend(["", "[미확인 주문]", ""])
        for order in unconfirmed_orders:
            line = f"- {order.user}: {order.quantity}잔 / {order.menu}"
            if order.decaf_count > 0:
                line += f" / 디카페인 {order.decaf_count}잔"
            if order.options:
                line += f" / {order.options}"
            if order.note:
                line += f" / {order.note}"
            lines.append(line)

        unconfirmed_total_quantity = sum(order.quantity for order in unconfirmed_orders)
        unconfirmed_customer_count = len({order.user for order in unconfirmed_orders})
        lines.extend(
            [
                "",
                f"미확인 총 {unconfirmed_total_quantity}잔 / 주문자 {unconfirmed_customer_count}명",
            ]
        )
    else:
        lines.extend(["", "[미확인 주문]", "", "- 없음"])

    return "\n".join(lines)


class OrderExtractorApp(tk.Tk):
    COLUMNS = (
        "user",
        "menu",
        "temperature",
        "size",
        "quantity",
        "decaf_count",
        "options",
        "note",
    )

    def __init__(self) -> None:
        super().__init__()
        self.title("Discord 음료 주문 추출기")
        self.geometry("1180x760")
        self.minsize(900, 600)
        self.orders: list[Order] = []
        self._build_ui()
        self._insert_example()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=2)
        self.rowconfigure(4, weight=3)
        self.rowconfigure(6, weight=2)

        title = ttk.Label(
            self,
            text="Discord 메시지를 붙여넣고 ‘주문 분석’을 누르세요.",
            font=("TkDefaultFont", 13, "bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        self.input_text = tk.Text(self, wrap="word", undo=True, height=12)
        self.input_text.grid(row=1, column=0, sticky="nsew", padx=12)

        button_frame = ttk.Frame(self)
        button_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=8)

        ttk.Button(button_frame, text="주문 분석", command=self.analyze).pack(
            side="left"
        )
        ttk.Button(button_frame, text="입력 지우기", command=self.clear_input).pack(
            side="left", padx=6
        )
        ttk.Button(button_frame, text="CSV 저장", command=self.save_csv).pack(
            side="left"
        )
        ttk.Button(button_frame, text="요약 복사", command=self.copy_summary).pack(
            side="left", padx=6
        )
        ttk.Button(
            button_frame, text="메뉴 설정", command=self.open_menu_config_window
        ).pack(side="left", padx=6)

        self.status_var = tk.StringVar(
            value="메뉴 별칭은 파일 상단 MENU_ALIASES에서 수정할 수 있습니다."
        )
        ttk.Label(button_frame, textvariable=self.status_var).pack(side="right")

        table_label = ttk.Label(
            self, text="추출 결과", font=("TkDefaultFont", 11, "bold")
        )
        table_label.grid(row=3, column=0, sticky="w", padx=12, pady=(3, 4))

        table_frame = ttk.Frame(self)
        table_frame.grid(row=4, column=0, sticky="nsew", padx=12)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_frame, columns=self.COLUMNS, show="headings")
        headings = {
            "user": "주문자",
            "menu": "메뉴",
            "temperature": "온도",
            "size": "사이즈",
            "quantity": "수량",
            "decaf_count": "디카페인",
            "options": "옵션",
            "note": "확인/비고",
        }
        widths = {
            "user": 100,
            "menu": 170,
            "temperature": 65,
            "size": 60,
            "quantity": 55,
            "decaf_count": 70,
            "options": 180,
            "note": 270,
        }
        for column in self.COLUMNS:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], minwidth=50, anchor="center")
        self.tree.column("options", anchor="w")
        self.tree.column("note", anchor="w")
        self.tree.column("decaf_count", anchor="center")

        vertical_scroll = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.tree.yview
        )
        horizontal_scroll = ttk.Scrollbar(
            table_frame, orient="horizontal", command=self.tree.xview
        )
        self.tree.configure(
            yscrollcommand=vertical_scroll.set, xscrollcommand=horizontal_scroll.set
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical_scroll.grid(row=0, column=1, sticky="ns")
        horizontal_scroll.grid(row=1, column=0, sticky="ew")

        summary_label = ttk.Label(
            self, text="집계 요약", font=("TkDefaultFont", 11, "bold")
        )
        summary_label.grid(row=5, column=0, sticky="w", padx=12, pady=(10, 4))

        self.summary_text = tk.Text(self, wrap="word", height=10, state="disabled")
        self.summary_text.grid(row=6, column=0, sticky="nsew", padx=12, pady=(0, 12))

    def _insert_example(self) -> None:
        example = (
            "[오후 3:20] 제이슨: 아아 라지 2잔, 하나는 샷추가\n"
            "민수 — 오후 3:21\n"
            "딸기라떼 M 얼음 적게 한잔\n"
            "수진: 제이슨이랑 똑같이 1잔\n"
            "영희: 바닐라라떼 톨 1잔, 아메리카노 핫 2잔 디카페인"
        )
        self.input_text.insert("1.0", example)

    def analyze(self) -> None:
        raw_text = self.input_text.get("1.0", "end").strip()
        if not raw_text:
            messagebox.showinfo("입력 필요", "Discord 메시지를 먼저 붙여넣어 주세요.")
            return

        messages = parse_discord_text(raw_text)
        self.orders = extract_orders(messages)
        confirmed_orders = [
            order for order in self.orders if not is_unconfirmed_order(order)
        ]
        unconfirmed_orders = [
            order for order in self.orders if is_unconfirmed_order(order)
        ]

        for item in self.tree.get_children():
            self.tree.delete(item)

        for order in confirmed_orders:
            try:
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        order.user,
                        order.menu,
                        order.temperature,
                        order.size,
                        order.quantity,
                        order.decaf_count,
                        order.options,
                        order.note,
                    ),
                )
            except tk.TclError:
                continue

        summary = (
            make_summary(self.orders) if self.orders else "추출된 주문이 없습니다."
        )
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", summary)
        self.summary_text.configure(state="disabled")

        unresolved = len(unconfirmed_orders)
        self.status_var.set(
            f"메시지 {len(messages)}개 → 주문 {len(self.orders)}건 추출 / 확인됨 {len(confirmed_orders)}건 / 미확인 {unresolved}건"
        )

    def clear_input(self) -> None:
        self.input_text.delete("1.0", "end")
        self.orders = []
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.configure(state="disabled")
        self.status_var.set("입력란을 비웠습니다.")

    def open_menu_config_window(self) -> None:
        window = tk.Toplevel(self)
        window.title("메뉴/별칭 설정")
        window.geometry("900x560")
        window.transient(self)
        window.grab_set()

        ttk.Label(
            window,
            text="각 메뉴마다 별칭을 바로 입력할 수 있도록 정리했습니다.",
            font=("TkDefaultFont", 10),
            wraplength=860,
        ).pack(anchor="w", padx=12, pady=(12, 6))

        frame = ttk.Frame(window)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        columns = ("menu", "aliases")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=16)
        tree.heading("menu", text="메뉴")
        tree.heading("aliases", text="별칭")
        tree.column("menu", width=260, anchor="w")
        tree.column("aliases", width=520, anchor="w")
        tree.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)

        for canonical, aliases in MENU_ALIASES.items():
            tree.insert("", "end", values=(canonical, ", ".join(aliases)))

        def edit_selected_cell(event: tk.Event | None = None) -> None:
            if not tree.selection():
                return
            item_id = tree.selection()[0]
            column_id = tree.identify_column(event.x) if event else "#1"
            if column_id not in {"#1", "#2"}:
                return
            values = list(tree.item(item_id, "values"))
            index = 0 if column_id == "#1" else 1
            current_value = values[index]
            label = "메뉴" if index == 0 else "별칭"
            new_value = simpledialog.askstring(
                f"{label} 수정",
                f"{label}을(를) 입력하세요.",
                initialvalue=current_value,
            )
            if new_value is None:
                return
            values[index] = new_value
            tree.item(item_id, values=values)

        tree.bind("<Double-1>", edit_selected_cell)

        def save_config() -> None:
            try:
                updated: dict[str, list[str]] = {}
                for item_id in tree.get_children():
                    menu_name = tree.item(item_id, "values")[0].strip()
                    alias_text = tree.item(item_id, "values")[1].strip()
                    if not menu_name:
                        continue
                    aliases = [
                        alias.strip()
                        for alias in alias_text.split(",")
                        if alias.strip()
                    ]
                    if aliases:
                        updated[menu_name] = aliases
                save_menu_aliases(updated)
                reload_menu_aliases()
                self.status_var.set("메뉴/별칭 설정을 저장했습니다.")
            except Exception:
                self.status_var.set("설정 저장 중 오류가 발생했습니다.")
            finally:
                window.destroy()

        button_frame = ttk.Frame(window)
        button_frame.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(button_frame, text="저장", command=save_config).pack(side="right")
        ttk.Button(button_frame, text="취소", command=window.destroy).pack(
            side="right", padx=6
        )

    def save_csv(self) -> None:
        if not self.orders:
            messagebox.showinfo("저장할 내용 없음", "먼저 주문을 분석해 주세요.")
            return

        path = filedialog.asksaveasfilename(
            title="주문 CSV 저장",
            defaultextension=".csv",
            filetypes=[("CSV 파일", "*.csv"), ("모든 파일", "*.*")],
            initialfile="drink_orders.csv",
        )
        if not path:
            return

        # utf-8-sig는 Excel에서 한글이 깨지는 것을 막아줍니다.
        with open(path, "w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(
                [
                    "주문자",
                    "메뉴",
                    "온도",
                    "사이즈",
                    "수량",
                    "디카페인",
                    "옵션",
                    "확인/비고",
                    "원문",
                ]
            )
            for order in self.orders:
                writer.writerow(
                    [
                        order.user,
                        order.menu,
                        order.temperature,
                        order.size,
                        order.quantity,
                        order.decaf_count,
                        order.options,
                        order.note,
                        order.source,
                    ]
                )

        self.status_var.set(f"CSV 저장 완료: {path}")

    def copy_summary(self) -> None:
        summary = self.summary_text.get("1.0", "end").strip()
        if not summary:
            messagebox.showinfo("복사할 내용 없음", "먼저 주문을 분석해 주세요.")
            return
        self.clipboard_clear()
        self.clipboard_append(summary)
        self.update()
        self.status_var.set("집계 요약을 클립보드에 복사했습니다.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discord 음료 주문 추출기")
    parser.add_argument(
        "--configure",
        action="store_true",
        help="콘솔에서 메뉴와 별칭을 수정합니다.",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="현재 메뉴와 별칭 설정을 콘솔에 출력합니다.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.configure:
        updated_aliases = configure_menu_aliases_from_console()
        reload_menu_aliases()
        print("설정 저장 완료")
        print("현재 메뉴/별칭:")
        for canonical, aliases in updated_aliases.items():
            print(f"- {canonical}: {', '.join(aliases)}")
        return

    if args.show_config:
        reload_menu_aliases()
        print("현재 메뉴/별칭:")
        for canonical, aliases in MENU_ALIASES.items():
            print(f"- {canonical}: {', '.join(aliases)}")
        return

    app = OrderExtractorApp()
    app.mainloop()


if __name__ == "__main__":
    main()

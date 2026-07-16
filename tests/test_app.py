from app import extract_orders, parse_discord_text
from drinklister import is_unconfirmed_order


def test_extract_orders_from_sample_message() -> None:
    text = """[오후 3:20] 제이슨: 아아 라지 2잔, 하나는 샷추가
민수 — 오후 3:21
딸기라떼 M 얼음 적게 한잔
수진: 제이슨이랑 똑같이 1잔
영희: 바닐라라떼 톨 1잔, 아메리카노 핫 2잔 디카페인"""

    messages = parse_discord_text(text)
    orders = extract_orders(messages)

    assert len(orders) >= 5
    assert any(order.menu == "아이스 아메리카노" for order in orders)
    assert any(order.menu == "딸기라떼(only iced)" for order in orders)


def test_polite_messages_are_not_marked_unconfirmed() -> None:
    text = """[오전 10:54]Agent_김태훈: 아이스아메리카노 부탁드립니다
[오전 10:55]Agent_이태경: 아샷추 감사합니다!
[오전 10:55]Agent_손제희: 매실에이드
[오전 10:56]Agent_최영현: 더블초코라떼 부탁드립니다.
[오전 10:58]Agent_이도연: 헤이즐넛 라떼 디카페인 부탁드립니다.
[오전 11:41]Agent_고우석: 자몽에이드 감사합니다!
"""

    messages = parse_discord_text(text)
    orders = extract_orders(messages)

    assert orders
    assert sum(1 for order in orders if not is_unconfirmed_order(order)) >= 5

"""Viewer-Friendly Title Generator

시청자용 제목 자동 생성 모듈.
규칙 기반 + AI 생성 하이브리드 방식.

Usage:
    from archive_analyzer.title_generator import TitleGenerator

    gen = TitleGenerator()

    # 파일 제목 생성
    title = gen.generate_file_title(filename, metadata)

    # 핸드 제목 생성
    title = gen.generate_hand_title(hand_data)
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class GeneratedTitle:
    """생성된 제목 결과"""

    title: str
    subtitle: Optional[str] = None
    source: str = "rule_based"  # 'rule_based', 'ai_generated', 'manual'
    confidence: float = 1.0


class TitleGenerator:
    """시청자용 제목 생성기"""

    # 약어 → 전체 표현
    ABBREVIATIONS = {
        # 이벤트 타입
        "ME": "Main Event",
        "FT": "Final Table",
        "HU": "Heads-Up",
        "SE": "Side Event",
        "HR": "High Roller",
        "SHR": "Super High Roller",
        "PLO": "Pot-Limit Omaha",
        "NLH": "No-Limit Hold'em",
        "6M": "6-Max",
        "6MAX": "6-Max",
        # Day/Session
        "D1": "Day 1",
        "D1A": "Day 1A",
        "D1B": "Day 1B",
        "D1C": "Day 1C",
        "D2": "Day 2",
        "D3": "Day 3",
        "D4": "Day 4",
        "D5": "Day 5",
        "D6": "Day 6",
        "D7": "Day 7",
        # 기타
        "EP": "Episode",
        "P1": "Part 1",
        "P2": "Part 2",
        "P3": "Part 3",
        "PT1": "Part 1",
        "PT2": "Part 2",
    }

    # 바이인 금액 패턴
    BUYIN_PATTERNS = {
        r"(\d+)K": lambda m: f"${int(m.group(1))}K",
        r"(\d+)M": lambda m: f"${int(m.group(1))}M",
        r"\$(\d+),?(\d{3})": lambda m: f"${m.group(1)},{m.group(2)}",
    }

    # 시리즈 풀네임
    SERIES_NAMES = {
        "WSOP": "World Series of Poker",
        "WSOP-BR": "WSOP Bracelet Series",
        "WSOP-C": "WSOP Circuit",
        "WSOP-SC": "WSOP Super Circuit",
        "HCL": "Hustler Casino Live",
        "PAD": "Poker After Dark",
        "MPP": "Mediterranean Poker Party",
        "WPT": "World Poker Tour",
    }

    # 지역 이름
    LOCATION_NAMES = {
        "EUROPE": "Europe",
        "PARADISE": "Paradise",
        "LAS VEGAS": "Las Vegas",
        "LV": "Las Vegas",
        "VEGAS": "Las Vegas",
        "LA": "Los Angeles",
    }

    def __init__(self):
        pass

    def generate_catalog_title(self, catalog_id: str, name: str) -> GeneratedTitle:
        """카탈로그 표시 제목 생성"""
        display = self.SERIES_NAMES.get(catalog_id.upper(), name)
        return GeneratedTitle(title=display, source="rule_based")

    def generate_subcatalog_title(
        self,
        catalog_id: str,
        sub1: Optional[str],
        sub2: Optional[str],
        sub3: Optional[str],
    ) -> GeneratedTitle:
        """서브카탈로그 표시 제목 생성

        예시:
            WSOP, WSOP-BR, Europe, 2024 → "2024 WSOP Europe"
            HCL, 2025, None, None → "Hustler Casino Live 2025"
        """
        parts = []

        # 연도 추출 (sub3 또는 sub2 또는 sub1에서)
        year = None
        for sub in [sub3, sub2, sub1]:
            if sub and re.match(r"^\d{4}$", sub.strip()):
                year = sub.strip()
                break

        # 지역/이벤트 이름 (sub1, sub2에서)
        location = None
        for sub in [sub2, sub1]:
            if sub:
                for key, val in self.LOCATION_NAMES.items():
                    if key in sub.upper():
                        location = val
                        break
                if location:
                    break

        # 제목 조합: "2024 WSOP Europe" 형태
        if year:
            parts.append(year)

        # 시리즈 약어 (WSOP, HCL 등)
        short_series = catalog_id.upper()
        parts.append(short_series)

        if location:
            parts.append(location)

        title = " ".join(parts)

        return GeneratedTitle(title=title, source="rule_based")

    def generate_file_title(
        self,
        filename: str,
        nas_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GeneratedTitle:
        """파일 표시 제목 생성

        시청자 친화적인 제목으로 변환:
        - 불필요한 접두사 제거 ($5M GTD 등)
        - 시리즈명 + 이벤트명 + Day 정보 추출
        - 연도 정보 포함
        """
        # 확장자 제거
        name = re.sub(r"\.[^.]+$", "", filename)

        # 파일 번호 패턴 제거 (-001, -002 등)
        name = re.sub(r"-\d{3}$", "", name)

        # 구분자 정리
        name = name.replace("_", " ")

        # 시리즈/이벤트 패턴 매칭
        title = None
        subtitle = None

        # WSOP 연도 패턴 먼저 체크 "WSOP - 1973" 또는 "WSOP 2024"
        year_match = re.search(r"WSOP\s*[-–]\s*(\d{4})", name, re.IGNORECASE)
        if year_match:
            year = year_match.group(1)
            # 괄호 안 번호 추출 (1), (2) 등
            part_match = re.search(r"\((\d+)\)", name)
            if part_match:
                title = f"WSOP {year} Part {part_match.group(1)}"
            else:
                title = f"WSOP {year}"

        # WSOP 이벤트 패턴들
        # "WSOP Super Circuit Cyprus Main Event - Day 1A" 형태
        if not title:
            wsop_match = re.search(
                r"WSOP\s*(Super Circuit|Circuit|Europe|Paradise|Las Vegas|Brazil)?\s*"
                r"([A-Za-z\s]+)?\s*"
                r"(Main Event|High Roller|Super High Roller|Side Event)?\s*"
                r"[-–]?\s*(Day\s*\d+[A-C]?|Final\s*(?:Table|Day))?",
                name,
                re.IGNORECASE,
            )
            if wsop_match and (wsop_match.group(1) or wsop_match.group(3) or wsop_match.group(4)):
                parts = ["WSOP"]
                if wsop_match.group(1):  # Circuit type
                    parts.append(wsop_match.group(1).strip())
                if wsop_match.group(2) and wsop_match.group(2).strip():  # Location
                    loc = wsop_match.group(2).strip()
                    if loc.lower() not in ["main", "high", "super", "side", ""]:
                        parts.append(loc)
                if wsop_match.group(3):  # Event type
                    parts.append(wsop_match.group(3).strip())
                if wsop_match.group(4):  # Day info
                    day = wsop_match.group(4).strip()
                    day = re.sub(r"Day\s*", "Day ", day, flags=re.IGNORECASE)
                    parts.append(day)
                title = " ".join(parts)

        # HCL 패턴 "20250611 - Nik Airball, Sashimi..."
        if not title:
            hcl_match = re.search(
                r"(\d{8})\s*[-–]?\s*(.+?)(?:\s+Commentary.*)?$", name, re.IGNORECASE
            )
            if hcl_match and nas_path and "HCL" in nas_path.upper():
                date_str = hcl_match.group(1)
                # 20250611 -> 2025-06-11
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                players_desc = hcl_match.group(2).strip()
                # 너무 길면 줄이기
                if len(players_desc) > 60:
                    players_desc = players_desc[:57] + "..."
                title = f"HCL {formatted_date}"
                subtitle = players_desc

        # PAD 패턴 "PAD Season 12 Episode 5"
        if not title:
            pad_match = re.search(
                r"PAD\s*(?:Season\s*)?(\d+)\s*(?:EP|Episode)?\s*(\d+)?", name, re.IGNORECASE
            )
            if pad_match:
                season = pad_match.group(1)
                episode = pad_match.group(2)
                title = f"Poker After Dark S{season}"
                if episode:
                    title += f" EP{episode}"

        # MPP 패턴 "$1M GTD $1K PokerOK..."
        if not title:
            mpp_match = re.search(
                r"\$(\d+[KMB])\s*GTD\s*\$?(\d+[KMB]?)\s*(.+)", name, re.IGNORECASE
            )
            if mpp_match:
                guarantee = mpp_match.group(1)
                buyin = mpp_match.group(2)
                event_name = mpp_match.group(3).strip()
                # 이벤트명 정리
                event_name = re.sub(r"\s*[-–]\s*Day.*$", "", event_name, flags=re.IGNORECASE)
                title = f"MILLIONS ${guarantee} GTD - ${buyin} {event_name}"

        # 기본: 파일명 정리
        if not title:
            title = self._clean_filename(filename)
            # 앞의 금액 패턴 제거
            title = re.sub(r"^\$\d+[KMB]?\s*GTD\s*", "", title, flags=re.IGNORECASE)
            title = re.sub(r"^\$\d+[KMB]?\s+", "", title)

        return GeneratedTitle(
            title=title.strip() if title else self._clean_filename(filename),
            subtitle=subtitle,
            source="rule_based",
        )

    def generate_hand_title(
        self,
        players: Optional[list] = None,
        winner: Optional[str] = None,
        pot_size_bb: Optional[float] = None,
        is_all_in: bool = False,
        is_showdown: bool = False,
        cards_shown: Optional[dict] = None,
        board: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> GeneratedTitle:
        """핸드 표시 제목 생성

        맥락적으로 가장 흥미로운 요소를 강조:
        - 유명 플레이어가 있으면 플레이어 중심
        - 올인이면 올인 상황 강조
        - 큰 팟이면 금액 강조
        - 특별 태그가 있으면 태그 활용

        예시:
            "Phil Ivey's Legendary Bluff"
            "AA vs KK - $2.1M All-In"
            "Hero Call on the River"
        """
        parts = []

        # 유명 플레이어 체크
        famous_players = self._get_famous_players(players or [])

        # 카드 정보
        hole_cards = self._format_hole_cards(cards_shown) if cards_shown else None

        # 제목 생성 우선순위
        if tags and "bluff" in [t.lower() for t in tags]:
            if famous_players:
                parts.append(f"{famous_players[0]}'s Bluff")
            else:
                parts.append("Amazing Bluff")

        elif tags and "hero_call" in [t.lower() for t in tags]:
            parts.append("Hero Call")
            if famous_players:
                parts.append(f"by {famous_players[0]}")

        elif is_all_in and hole_cards:
            parts.append(hole_cards)
            parts.append("All-In")

        elif famous_players and winner:
            if winner in famous_players:
                parts.append(f"{winner} Wins")
            else:
                parts.append(f"{famous_players[0]} vs {winner}")

        elif pot_size_bb and pot_size_bb > 500:
            parts.append(f"{int(pot_size_bb)} BB Pot")
            if is_all_in:
                parts.append("All-In")

        else:
            # 기본 제목
            if winner:
                parts.append(f"{winner} Takes It")
            elif is_showdown:
                parts.append("Showdown")
            else:
                parts.append("Big Hand")

        title = " - ".join(parts) if len(parts) > 1 else parts[0] if parts else "Poker Hand"

        return GeneratedTitle(
            title=title,
            source="rule_based",
            confidence=0.7 if not famous_players else 0.9,
        )

    def _clean_filename(self, filename: str) -> str:
        """파일명 정리"""
        name = re.sub(r"\.[^.]+$", "", filename)
        name = name.replace("_", " ").replace("-", " ")
        name = re.sub(r"\s+", " ", name).strip()
        return name

    def _get_famous_players(self, players: list) -> list:
        """유명 플레이어 필터링"""
        famous = [
            "Phil Ivey",
            "Daniel Negreanu",
            "Phil Hellmuth",
            "Doyle Brunson",
            "Tom Dwan",
            "Doug Polk",
            "Garrett Adelstein",
            "Eric Persson",
            "Rampage",
            "Antonio Esfandiari",
            "Patrik Antonius",
        ]
        return [p for p in players if any(f.lower() in p.lower() for f in famous)]

    def _format_hole_cards(self, cards_shown: dict) -> Optional[str]:
        """홀카드 포맷팅"""
        if not cards_shown:
            return None

        # AA, KK 같은 프리미엄 핸드 감지
        premium_hands = ["AA", "KK", "QQ", "JJ", "AK"]

        for player, cards in cards_shown.items():
            if isinstance(cards, str):
                for hand in premium_hands:
                    if hand in cards.upper().replace(" ", ""):
                        return hand

        return None


# 테스트
if __name__ == "__main__":
    gen = TitleGenerator()

    print("=== File Titles ===")
    tests = [
        "WSOP 2024 ME D1A Part1.mp4",
        "FT_HU_Final.mp4",
        "25K_High_Roller_D2.mp4",
        "HCL_2025_01_15_Session1.mp4",
    ]
    for f in tests:
        result = gen.generate_file_title(f)
        print(f"  {f}")
        print(f"    → {result.title}")
        if result.subtitle:
            print(f"    → {result.subtitle}")
        print()

    print("=== Hand Titles ===")
    result = gen.generate_hand_title(
        players=["Phil Ivey", "Tom Dwan"],
        winner="Phil Ivey",
        is_all_in=True,
        cards_shown={"Phil Ivey": "AA"},
    )
    print(f"  → {result.title}")

    result = gen.generate_hand_title(
        players=["Player1", "Player2"],
        pot_size_bb=1200,
        is_all_in=True,
        tags=["bluff"],
    )
    print(f"  → {result.title}")

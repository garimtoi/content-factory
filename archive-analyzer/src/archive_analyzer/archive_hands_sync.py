"""Archive Team Hands Sync

아카이브 팀 구글 시트 → pokervod.db hands 테이블 동기화.

Usage:
    python -m archive_analyzer.archive_hands_sync --sync
    python -m archive_analyzer.archive_hands_sync --dry-run
    python -m archive_analyzer.archive_hands_sync --daemon            # 1시간 간격
    python -m archive_analyzer.archive_hands_sync --daemon --interval 1800  # 30분 간격
"""

import time
from datetime import datetime

import os
import re
import sqlite3
import json
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

import gspread
from google.oauth2.service_account import Credentials


# =============================================
# Configuration
# =============================================

@dataclass
class ArchiveSyncConfig:
    """아카이브 동기화 설정"""
    credentials_path: str = None
    archive_spreadsheet_id: str = "1_RN_W_ZQclSZA0Iez6XniCXVtjkkd5HNZwiT6l-z6d4"
    db_path: str = None
    sync_interval_seconds: int = 3600  # 기본 1시간

    def __post_init__(self):
        if self.credentials_path is None:
            self.credentials_path = os.environ.get(
                "CREDENTIALS_PATH",
                "D:/AI/claude01/archive-analyzer/config/gcp-service-account.json"
            )
        if self.db_path is None:
            self.db_path = os.environ.get(
                "DB_PATH",
                "D:/AI/claude01/qwen_hand_analysis/data/pokervod.db"
            )


# =============================================
# Tag Normalization
# =============================================

# 태그 정규화 매핑
TAG_NORMALIZATION = {
    # Poker Play tags
    "preflop all-in": "preflop_allin",
    "preflop allin": "preflop_allin",
    "preflop all in": "preflop_allin",
    "4-way all-in": "multiway_allin",
    "3-way all-in": "multiway_allin",
    "hero fold": "hero_fold",
    "nice fold": "nice_fold",
    "hero call": "hero_call",
    "cooler": "cooler",
    "badbeat": "badbeat",
    "bad beat": "badbeat",
    "suckout": "suckout",
    "bluff": "bluff",
    "epic hand": "epic_hand",
    "crazy runout": "crazy_runout",
    "reversal over reversal": "reversal",
    "quads": "quads",
    "straight flush": "straight_flush",
    "royal flush": "royal_flush",
    "flush vs flush": "flush_vs_flush",
    "set over set": "set_over_set",
    "kk vs qq": "premium_vs_premium",
    "aa vs kk": "premium_vs_premium",

    # Emotion tags
    "absurd": "absurd",
    "luckbox": "luckbox",
    "insane": "insane",
    "brutal": "brutal",
}


def normalize_tag(tag: str) -> str:
    """태그 정규화"""
    if not tag:
        return ""
    tag_lower = tag.strip().lower()
    return TAG_NORMALIZATION.get(tag_lower, tag_lower.replace(" ", "_").replace("-", "_"))


def parse_timecode(timecode: str) -> Optional[float]:
    """타임코드를 초 단위로 변환

    "6:58:55" -> 25135.0
    "0:12:47" -> 767.0
    """
    if not timecode:
        return None

    parts = timecode.strip().split(":")
    try:
        if len(parts) == 3:
            hours, mins, secs = parts
            return int(hours) * 3600 + int(mins) * 60 + float(secs)
        elif len(parts) == 2:
            mins, secs = parts
            return int(mins) * 60 + float(secs)
        else:
            return float(parts[0])
    except (ValueError, IndexError):
        return None


def parse_hand_grade(grade: str) -> int:
    """Hand Grade를 숫자로 변환

    "★" -> 1
    "★★" -> 2
    "★★★" -> 3
    """
    if not grade:
        return 0
    return grade.count("★")


def normalize_nas_path(path: str) -> str:
    """NAS 경로 정규화"""
    if not path:
        return ""
    # 백슬래시를 슬래시로 변환
    normalized = path.replace("\\", "/")
    # 앞의 // 제거
    if normalized.startswith("//"):
        normalized = normalized[2:]
    return normalized.lower()


# =============================================
# Archive Hands Sync Service
# =============================================

class ArchiveHandsSync:
    """아카이브 팀 시트 ↔ hands 테이블 양방향 동기화"""

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",  # 읽기/쓰기
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(self, config: ArchiveSyncConfig = None):
        self.config = config or ArchiveSyncConfig()
        self._connect_sheets()
        self._connect_db()
        self._load_file_mapping()

    def _connect_sheets(self):
        """Google Sheets 연결"""
        creds = Credentials.from_service_account_file(
            self.config.credentials_path,
            scopes=self.SCOPES,
        )
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(self.config.archive_spreadsheet_id)

    def _connect_db(self):
        """SQLite 연결"""
        self.conn = sqlite3.connect(self.config.db_path)
        self.conn.row_factory = sqlite3.Row

    def _load_file_mapping(self):
        """파일 경로 → file_id 매핑 로드"""
        cursor = self.conn.execute("SELECT id, nas_path FROM files WHERE nas_path IS NOT NULL")
        self.file_mapping = {}
        for row in cursor:
            if row["nas_path"]:
                normalized = normalize_nas_path(row["nas_path"])
                self.file_mapping[normalized] = row["id"]
        print(f"Loaded {len(self.file_mapping)} file mappings")

    def find_file_id(self, nas_path: str, filename: str) -> Optional[str]:
        """NAS 경로 또는 파일명으로 file_id 찾기"""
        if nas_path:
            normalized = normalize_nas_path(nas_path)
            # 정확히 매칭
            if normalized in self.file_mapping:
                return self.file_mapping[normalized]
            # 부분 매칭 (폴더 경로)
            for path, file_id in self.file_mapping.items():
                if normalized in path or path in normalized:
                    return file_id

        # 파일명으로 검색
        if filename:
            filename_normalized = filename.lower()
            cursor = self.conn.execute(
                "SELECT id FROM files WHERE LOWER(filename) LIKE ?",
                (f"%{filename_normalized}%",)
            )
            row = cursor.fetchone()
            if row:
                return row["id"]

        return None

    def parse_sheet_row(self, headers: List[str], row: List[str]) -> Optional[Dict[str, Any]]:
        """시트 행을 hands 레코드로 변환"""
        if not any(row):
            return None

        # 행 데이터를 헤더 길이에 맞춤
        row_padded = row + [""] * (len(headers) - len(row))

        # 헤더-값 쌍 리스트 (중복 헤더 지원)
        pairs = list(zip(headers, row_padded))

        # 단일 값 필드는 첫 번째 매칭 사용
        def get_first(key: str) -> str:
            for h, v in pairs:
                if h == key:
                    return v.strip()
            return ""

        # 필수 필드 확인
        file_no = get_first("File No.")
        if not file_no:
            return None

        # 파일 매칭
        nas_path = get_first("Nas Folder Link")
        filename = get_first("File Name")
        file_id = self.find_file_id(nas_path, filename)

        # 타임코드 파싱
        start_sec = parse_timecode(get_first("In"))
        end_sec = parse_timecode(get_first("Out"))

        # Hand Grade
        highlight_score = parse_hand_grade(get_first("Hand Grade"))

        # 카드 정보
        cards_shown = get_first("Hands")

        # 플레이어 추출 (Tag (Player) 컬럼들 - 여러 개)
        players = []
        for h, v in pairs:
            if h == "Tag (Player)" and v.strip():
                players.append(v.strip())

        # 태그 추출 (Tag (Poker Play), Tag (Emotion) 컬럼들 - 여러 개)
        tags = []
        for h, v in pairs:
            if h in ["Tag (Poker Play)", "Tag (Emotion)"] and v.strip():
                normalized = normalize_tag(v)
                if normalized and normalized not in tags:
                    tags.append(normalized)

        return {
            "file_id": file_id,
            "hand_number": int(file_no) if file_no.isdigit() else 0,
            "start_sec": start_sec,
            "end_sec": end_sec,
            "highlight_score": highlight_score,
            "cards_shown": json.dumps({"raw": cards_shown}) if cards_shown else None,
            "players": json.dumps(players) if players else None,
            "tags": json.dumps(tags) if tags else None,
            "title_source": "archive_team",
            # 원본 정보 (디버깅용)
            "_source_file": filename,
            "_source_path": nas_path,
        }

    def sync_worksheet(self, worksheet_name: str, dry_run: bool = False) -> Dict[str, int]:
        """단일 워크시트 동기화"""
        stats = {"inserted": 0, "updated": 0, "skipped": 0, "no_file": 0}

        try:
            ws = self.spreadsheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            print(f"  Worksheet not found: {worksheet_name}")
            return stats

        all_values = ws.get_all_values()
        if len(all_values) < 4:
            return stats

        headers = all_values[2]  # 3행이 헤더
        data_rows = all_values[3:]  # 4행부터 데이터

        for row in data_rows:
            record = self.parse_sheet_row(headers, row)
            if not record:
                continue

            if not record["file_id"]:
                stats["no_file"] += 1
                if dry_run:
                    print(f"    [NO FILE] {record['_source_file'][:50]}...")
                continue

            if dry_run:
                print(f"    [OK] file_id={record['file_id']}, hand={record['hand_number']}, "
                      f"time={record['start_sec']}-{record['end_sec']}, "
                      f"tags={record['tags']}")
                stats["inserted"] += 1
            else:
                # DB에 upsert
                self._upsert_hand(record)
                stats["inserted"] += 1

        if not dry_run:
            self.conn.commit()

        return stats

    def _upsert_hand(self, record: Dict[str, Any]):
        """hands 테이블에 upsert + 정규화 테이블 업데이트"""
        # file_id + hand_number로 중복 체크
        cursor = self.conn.execute(
            "SELECT id FROM hands WHERE file_id = ? AND hand_number = ?",
            (record["file_id"], record["hand_number"])
        )
        existing = cursor.fetchone()

        if existing:
            hand_id = existing["id"]
            # UPDATE hands (players, tags JSON 컬럼은 하위 호환성 유지)
            self.conn.execute("""
                UPDATE hands SET
                    start_sec = ?,
                    end_sec = ?,
                    highlight_score = ?,
                    cards_shown = ?,
                    players = ?,
                    tags = ?,
                    title_source = ?
                WHERE id = ?
            """, (
                record["start_sec"],
                record["end_sec"],
                record["highlight_score"],
                record["cards_shown"],
                record["players"],
                record["tags"],
                record["title_source"],
                hand_id,
            ))
        else:
            # INSERT hands
            cursor = self.conn.execute("""
                INSERT INTO hands (
                    file_id, hand_number, start_sec, end_sec,
                    highlight_score, cards_shown, players, tags, title_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record["file_id"],
                record["hand_number"],
                record["start_sec"],
                record["end_sec"],
                record["highlight_score"],
                record["cards_shown"],
                record["players"],
                record["tags"],
                record["title_source"],
            ))
            hand_id = cursor.lastrowid

        # 정규화 테이블 업데이트 (hand_players, hand_tags)
        self._sync_normalized_tables(hand_id, record)

    def _sync_normalized_tables(self, hand_id: int, record: Dict[str, Any]):
        """정규화 테이블 (hand_players, hand_tags) 동기화"""
        # 1. hand_players 동기화
        if record.get("players"):
            try:
                players = json.loads(record["players"])
                if isinstance(players, list):
                    # 기존 레코드 삭제 후 재삽입
                    self.conn.execute(
                        "DELETE FROM hand_players WHERE hand_id = ?",
                        (hand_id,)
                    )
                    for position, player_name in enumerate(players, 1):
                        if player_name and isinstance(player_name, str):
                            self.conn.execute("""
                                INSERT INTO hand_players (hand_id, player_name, position)
                                VALUES (?, ?, ?)
                            """, (hand_id, player_name.strip(), position))
            except (json.JSONDecodeError, TypeError):
                pass

        # 2. hand_tags 동기화
        if record.get("tags"):
            try:
                tags = json.loads(record["tags"])
                if isinstance(tags, list):
                    # 기존 레코드 삭제 후 재삽입
                    self.conn.execute(
                        "DELETE FROM hand_tags WHERE hand_id = ?",
                        (hand_id,)
                    )
                    for tag in tags:
                        if tag and isinstance(tag, str):
                            self.conn.execute("""
                                INSERT OR IGNORE INTO hand_tags (hand_id, tag)
                                VALUES (?, ?)
                            """, (hand_id, tag.strip()))
            except (json.JSONDecodeError, TypeError):
                pass

    def sync_all(self, dry_run: bool = False):
        """모든 워크시트 동기화"""
        print(f"Syncing archive sheets (dry_run={dry_run})...")

        total_stats = {"inserted": 0, "updated": 0, "skipped": 0, "no_file": 0}

        for ws in self.spreadsheet.worksheets():
            print(f"\n  [{ws.title}]")
            stats = self.sync_worksheet(ws.title, dry_run)
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)
            print(f"    -> inserted: {stats['inserted']}, no_file: {stats['no_file']}")

        print(f"\n=== Total ===")
        print(f"  Inserted: {total_stats['inserted']}")
        print(f"  No file match: {total_stats['no_file']}")

        return total_stats

    def close(self):
        """연결 종료"""
        self.conn.close()

    def run_daemon(self):
        """백그라운드 동기화 서비스 실행 (기본 1시간 간격)"""
        interval = self.config.sync_interval_seconds
        print(f"Starting archive hands sync daemon (interval: {interval}s = {interval//60}min)")
        print("Press Ctrl+C to stop")
        print()

        try:
            while True:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n[{now}] Running sync...")

                try:
                    stats = self.sync_all(dry_run=False)
                    print(f"[{now}] Sync completed: {stats['inserted']} hands")
                except Exception as e:
                    print(f"[{now}] Sync error: {e}")

                print(f"[{now}] Next sync in {interval//60} minutes...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nDaemon stopped.")

    # =============================================
    # Reverse Sync (DB → Sheet)
    # =============================================

    def _build_reverse_file_mapping(self) -> Dict[str, str]:
        """file_id → NAS 경로 역매핑"""
        cursor = self.conn.execute("SELECT id, nas_path, filename FROM files WHERE nas_path IS NOT NULL")
        mapping = {}
        for row in cursor:
            mapping[str(row["id"])] = {
                "nas_path": row["nas_path"],
                "filename": row["filename"],
            }
        return mapping

    def _denormalize_tag(self, tag: str) -> str:
        """정규화된 태그 → 원본 표시 형식"""
        TAG_DISPLAY = {
            "preflop_allin": "Preflop All-in",
            "multiway_allin": "Multiway All-in",
            "hero_fold": "Hero Fold",
            "nice_fold": "Nice Fold",
            "hero_call": "Hero Call",
            "cooler": "Cooler",
            "badbeat": "Badbeat",
            "suckout": "Suckout",
            "bluff": "Bluff",
            "epic_hand": "Epic Hand",
            "crazy_runout": "Crazy Runout",
            "reversal": "Reversal",
            "quads": "Quads",
            "straight_flush": "Straight Flush",
            "royal_flush": "Royal Flush",
            "flush_vs_flush": "Flush vs Flush",
            "set_over_set": "Set over Set",
            "premium_vs_premium": "Premium vs Premium",
            "absurd": "Absurd",
            "luckbox": "Luckbox",
            "insane": "Insane",
            "brutal": "Brutal",
        }
        return TAG_DISPLAY.get(tag, tag.replace("_", " ").title())

    def _seconds_to_timecode(self, seconds: float) -> str:
        """초 → 타임코드 (H:MM:SS)"""
        if seconds is None:
            return ""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h}:{m:02d}:{s:02d}"

    def _grade_to_stars(self, score: int) -> str:
        """숫자 → 별 (1 → ★)"""
        if not score or score <= 0:
            return ""
        return "★" * int(score)

    def get_worksheet_file_mapping(self, worksheet_name: str) -> Optional[Tuple[str, str]]:
        """워크시트에서 NAS 경로와 파일명 추출"""
        try:
            ws = self.spreadsheet.worksheet(worksheet_name)
            all_values = ws.get_all_values()
            if len(all_values) < 4:
                return None

            headers = all_values[2]
            first_data_row = all_values[3] if len(all_values) > 3 else []

            # 헤더-값 쌍
            row_padded = first_data_row + [""] * (len(headers) - len(first_data_row))
            pairs = list(zip(headers, row_padded))

            nas_path = ""
            filename = ""
            for h, v in pairs:
                if h == "Nas Folder Link" and v.strip():
                    nas_path = v.strip()
                elif h == "File Name" and v.strip():
                    filename = v.strip()

            return (nas_path, filename) if (nas_path or filename) else None
        except Exception:
            return None

    def reverse_sync_worksheet(self, worksheet_name: str, dry_run: bool = False) -> Dict[str, int]:
        """DB hands → 워크시트 역동기화

        워크시트의 NAS 경로로 file_id를 찾고,
        해당 file_id의 모든 hands를 시트에 업데이트
        """
        stats = {"synced": 0, "added": 0, "skipped": 0, "no_match": 0}

        try:
            ws = self.spreadsheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            print(f"  Worksheet not found: {worksheet_name}")
            return stats

        # 시트에서 파일 정보 추출
        file_info = self.get_worksheet_file_mapping(worksheet_name)
        if not file_info:
            print(f"  No file info in worksheet")
            return stats

        nas_path, filename = file_info
        file_id = self.find_file_id(nas_path, filename)

        if not file_id:
            print(f"  No file_id match for: {filename[:50]}...")
            stats["no_match"] = 1
            return stats

        # DB에서 해당 파일의 hands 조회
        cursor = self.conn.execute("""
            SELECT id, hand_number, start_sec, end_sec, highlight_score,
                   cards_shown, players, tags
            FROM hands
            WHERE file_id = ?
            ORDER BY hand_number
        """, (file_id,))

        db_hands = {row["hand_number"]: dict(row) for row in cursor}

        if not db_hands:
            print(f"  No hands in DB for file_id={file_id}")
            return stats

        # 시트 데이터 읽기
        all_values = ws.get_all_values()
        if len(all_values) < 3:
            return stats

        headers = all_values[2]

        # 헤더 인덱스 찾기
        def find_col_indices(header_name: str) -> List[int]:
            return [i for i, h in enumerate(headers) if h == header_name]

        in_idx = find_col_indices("In")
        out_idx = find_col_indices("Out")
        grade_idx = find_col_indices("Hand Grade")
        hands_idx = find_col_indices("Hands")
        player_indices = find_col_indices("Tag (Player)")
        poker_indices = find_col_indices("Tag (Poker Play)")
        emotion_indices = find_col_indices("Tag (Emotion)")

        # 각 데이터 행 업데이트
        updates = []  # (row, col, value) 리스트

        for row_idx, row in enumerate(all_values[3:], start=4):  # 4행부터 (1-indexed)
            if len(row) == 0:
                continue

            file_no = row[0].strip() if row else ""
            if not file_no or not file_no.isdigit():
                continue

            hand_number = int(file_no)
            if hand_number not in db_hands:
                continue

            hand = db_hands[hand_number]

            # In/Out 타임코드 업데이트
            if in_idx and hand.get("start_sec"):
                tc = self._seconds_to_timecode(hand["start_sec"])
                if len(row) > in_idx[0] and row[in_idx[0]] != tc:
                    updates.append((row_idx, in_idx[0] + 1, tc))

            if out_idx and hand.get("end_sec"):
                tc = self._seconds_to_timecode(hand["end_sec"])
                if len(row) > out_idx[0] and row[out_idx[0]] != tc:
                    updates.append((row_idx, out_idx[0] + 1, tc))

            # Hand Grade 업데이트
            if grade_idx and hand.get("highlight_score"):
                stars = self._grade_to_stars(hand["highlight_score"])
                if len(row) > grade_idx[0] and row[grade_idx[0]] != stars:
                    updates.append((row_idx, grade_idx[0] + 1, stars))

            # Cards 업데이트
            if hands_idx and hand.get("cards_shown"):
                try:
                    cards_data = json.loads(hand["cards_shown"])
                    cards_raw = cards_data.get("raw", "")
                    if len(row) > hands_idx[0] and row[hands_idx[0]] != cards_raw:
                        updates.append((row_idx, hands_idx[0] + 1, cards_raw))
                except (json.JSONDecodeError, TypeError):
                    pass

            # Players 업데이트
            if player_indices and hand.get("players"):
                try:
                    players = json.loads(hand["players"])
                    for i, player in enumerate(players[:len(player_indices)]):
                        col_idx = player_indices[i]
                        if len(row) > col_idx and row[col_idx] != player:
                            updates.append((row_idx, col_idx + 1, player))
                except (json.JSONDecodeError, TypeError):
                    pass

            # Tags 업데이트 (Poker Play + Emotion)
            if (poker_indices or emotion_indices) and hand.get("tags"):
                try:
                    tags = json.loads(hand["tags"])

                    # 태그 분류
                    poker_tags = []
                    emotion_tags = []
                    EMOTION_TAGS = {"absurd", "luckbox", "insane", "brutal"}

                    for tag in tags:
                        if tag in EMOTION_TAGS:
                            emotion_tags.append(self._denormalize_tag(tag))
                        else:
                            poker_tags.append(self._denormalize_tag(tag))

                    # Poker Play 태그
                    for i, tag in enumerate(poker_tags[:len(poker_indices)]):
                        col_idx = poker_indices[i]
                        if len(row) > col_idx and row[col_idx] != tag:
                            updates.append((row_idx, col_idx + 1, tag))

                    # Emotion 태그
                    for i, tag in enumerate(emotion_tags[:len(emotion_indices)]):
                        col_idx = emotion_indices[i]
                        if len(row) > col_idx and row[col_idx] != tag:
                            updates.append((row_idx, col_idx + 1, tag))

                except (json.JSONDecodeError, TypeError):
                    pass

            stats["synced"] += 1

        # 배치 업데이트
        if updates and not dry_run:
            for row, col, value in updates:
                ws.update_cell(row, col, value)
            stats["added"] = len(updates)
        elif updates:
            print(f"    [DRY-RUN] Would update {len(updates)} cells")
            stats["added"] = len(updates)

        return stats

    def reverse_sync_all(self, dry_run: bool = False):
        """모든 워크시트 역동기화 (DB → Sheet)"""
        print(f"Reverse syncing to archive sheets (dry_run={dry_run})...")

        total_stats = {"synced": 0, "added": 0, "skipped": 0, "no_match": 0}

        for ws in self.spreadsheet.worksheets():
            print(f"\n  [{ws.title}]")
            stats = self.reverse_sync_worksheet(ws.title, dry_run)
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)
            print(f"    -> synced: {stats['synced']}, cells updated: {stats['added']}")

        print(f"\n=== Total ===")
        print(f"  Hands synced: {total_stats['synced']}")
        print(f"  Cells updated: {total_stats['added']}")
        print(f"  No file match: {total_stats['no_match']}")

        return total_stats


# =============================================
# CLI
# =============================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Archive Team Hands Sync")
    parser.add_argument("--sync", action="store_true", help="Sync archive sheets to DB (forward)")
    parser.add_argument("--reverse", action="store_true", help="Sync DB to archive sheets (reverse)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--sheet", type=str, help="Sync specific worksheet only")
    parser.add_argument("--daemon", action="store_true", help="Run as background daemon")
    parser.add_argument("--interval", type=int, default=3600, help="Sync interval in seconds (default: 3600 = 1hr)")

    args = parser.parse_args()

    config = ArchiveSyncConfig(sync_interval_seconds=args.interval)
    sync = ArchiveHandsSync(config)

    try:
        if args.daemon:
            # 데몬 모드
            sync.run_daemon()
        elif args.reverse:
            # 역방향 동기화 (DB → Sheet)
            if args.sheet:
                stats = sync.reverse_sync_worksheet(args.sheet, dry_run=args.dry_run)
                print(f"Stats: {stats}")
            else:
                sync.reverse_sync_all(dry_run=args.dry_run)
        elif args.sheet:
            # 특정 시트만 정방향 동기화
            stats = sync.sync_worksheet(args.sheet, dry_run=args.dry_run)
            print(f"Stats: {stats}")
        elif args.sync or args.dry_run:
            # 전체 정방향 동기화
            sync.sync_all(dry_run=args.dry_run)
        else:
            parser.print_help()
    finally:
        sync.close()


if __name__ == "__main__":
    main()

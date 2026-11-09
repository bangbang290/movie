"""워크숍 모션 영상 의뢰 — 저장소(SQLite + 파일 폴더).

  분임(1~7)마다 의뢰서 1장 · 첨부 자료 · 결과물(영상·그림) · 수정 요청 대화를 보관합니다.
  상태 흐름: draft(작성 중) → submitted(접수) → making(제작 중) → done(완료) ⇄ revise(수정 요청)
  분임 코드는 비밀값(Secrets)으로 계산하므로 서버가 다시 켜져도 바뀌지 않습니다.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import time
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("MOTION_DATA", os.path.join(BASE, "data"))
DB_PATH = os.path.join(DATA, "motion.db")
FILES = os.path.join(DATA, "files")

N_GROUPS = 7
STATUS = {
    "draft": "작성 중",
    "submitted": "접수 완료",
    "making": "제작 중",
    "done": "완성",
    "revise": "수정 요청",
}
EDITABLE = ("draft", "submitted")

USES = ["행사 오프닝", "시작 전 대기 화면", "분임 소개", "시상·발표", "홍보", "기타"]
LENGTHS = ["15초", "30초", "1분", "직접 입력"]
RATIOS = ["가로 16:9 (프로젝터·TV)", "세로 9:16 (휴대폰)", "정사각 1:1"]
QUALITIES = ["FHD (보통)", "4K (큰 스크린)"]
LOOPS = ["한 번만 재생", "계속 반복 (끝과 처음이 자연스럽게 이어짐)"]
MOODS = ["고급스럽고 웅장하게", "밝고 경쾌하게", "레트로", "귀엽게", "차분하게", "뉴스·다큐처럼", "감동적으로", "웃기게"]
STYLES = ["글자 위주", "단순한 도형·아이콘", "일러스트(그림)", "3D 입체", "상관없음"]
FONTS = ["상관없음", "붓글씨", "명조 (붓끝 있는 글자)", "고딕 (깔끔한 글자)", "손글씨"]
YESNO_MUSIC = ["배경음악 넣기", "음악 없음"]
NARR = ["내레이션 없음", "내레이션 있음 (녹음 파일 첨부)"]

ATT_TYPES = ["png", "jpg", "jpeg", "gif", "webp", "svg", "pdf", "mp3", "wav", "m4a", "mp4", "mov"]
RES_TYPES = ["mp4", "mov", "webm", "png", "jpg", "jpeg", "gif", "webp"]
VIDEO_EXT = ("mp4", "mov", "webm")


class StoreError(Exception):
    pass


def blank_request() -> dict:
    return {
        "title": "", "use": USES[0], "use_etc": "", "length": LENGTHS[1], "length_custom": "",
        "ratio": RATIOS[0], "quality": QUALITIES[0], "loop": LOOPS[0],
        "message": "", "audience": "", "feeling": "",
        "mood": [], "style": STYLES[-1], "color": "", "font": FONTS[0], "ref": "", "avoid": "",
        "scenes": [blank_scene() for _ in range(3)],
        "music": YESNO_MUSIC[0], "music_mood": "", "sfx": "", "narration": NARR[0],
        "hold_end": 0, "cover": False, "etc": "",
    }


def blank_scene() -> dict:
    return {"sec": 5, "text": "", "look": "", "motion": ""}


def norm_request(d: dict | None) -> dict:
    out = blank_request()
    for k, v in (d or {}).items():
        if k in out:
            out[k] = v
    if not isinstance(out["mood"], list):
        out["mood"] = []
    sc = out["scenes"] if isinstance(out["scenes"], list) else []
    out["scenes"] = [dict(blank_scene(), **{k: v for k, v in s.items() if k in blank_scene()}) for s in sc if isinstance(s, dict)]
    if not out["scenes"]:
        out["scenes"] = [blank_scene()]
    for s in out["scenes"]:
        try:
            s["sec"] = max(1, min(120, int(s["sec"])))
        except (TypeError, ValueError):
            s["sec"] = 5
    try:
        out["hold_end"] = max(0, min(30, int(out["hold_end"])))
    except (TypeError, ValueError):
        out["hold_end"] = 0
    out["cover"] = bool(out["cover"])
    return out


# ───────────────────────── DB
def _connect():
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(FILES, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=15000")
    return c


@contextlib.contextmanager
def _tx():
    c = _connect()
    try:
        c.execute("BEGIN IMMEDIATE")
        yield c
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise
    finally:
        c.close()


def init():
    with _tx() as c:
        for sql in ("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT)",
                    "CREATE TABLE IF NOT EXISTS req (g INTEGER PRIMARY KEY, data TEXT, status TEXT, submitted_at REAL, updated_at REAL)",
                    "CREATE TABLE IF NOT EXISTS att (id INTEGER PRIMARY KEY AUTOINCREMENT, g INTEGER, name TEXT, path TEXT, size INTEGER, at REAL)",
                    "CREATE TABLE IF NOT EXISTS res (id INTEGER PRIMARY KEY AUTOINCREMENT, g INTEGER, name TEXT, path TEXT, size INTEGER, note TEXT, at REAL)",
                    "CREATE TABLE IF NOT EXISTS msg (id INTEGER PRIMARY KEY AUTOINCREMENT, g INTEGER, who TEXT, text TEXT, at REAL, seen INTEGER DEFAULT 0)"):
            c.execute(sql)
        for g in range(1, N_GROUPS + 1):
            c.execute("INSERT OR IGNORE INTO req(g, data, status, submitted_at, updated_at) VALUES (?,?,?,?,?)",
                      (g, json.dumps(blank_request(), ensure_ascii=False), "draft", None, time.time()))


def _kv_get(c, k, default=None):
    r = c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return json.loads(r["v"]) if r else default


def _kv_put(c, k, v):
    c.execute("INSERT INTO kv(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, json.dumps(v, ensure_ascii=False)))


# ───────────────────────── 설정
def default_settings() -> dict:
    return {
        "event": "심사2국 워크숍",
        "names": [f"{i}분임" for i in range(1, N_GROUPS + 1)],
        "notice": "의뢰서는 쓰는 대로 저장됩니다. 다 쓰면 맨 아래 [제출하기]를 눌러 주세요.",
        "public_url": "",
    }


def get_settings() -> dict:
    c = _connect()
    try:
        s = _kv_get(c, "settings", {}) or {}
    finally:
        c.close()
    out = default_settings()
    out.update({k: v for k, v in s.items() if k in out})
    names = list(out["names"])[:N_GROUPS]
    names += [f"{i}분임" for i in range(len(names) + 1, N_GROUPS + 1)]
    out["names"] = [(str(n).strip() or f"{i + 1}분임")[:16] for i, n in enumerate(names)]
    return out


def save_settings(**kw):
    with _tx() as c:
        s = _kv_get(c, "settings", {}) or {}
        s.update({k: v for k, v in kw.items() if k in default_settings()})
        _kv_put(c, "settings", s)


def gname(g: int, S: dict | None = None) -> str:
    S = S or get_settings()
    return S["names"][g - 1]


# ───────────────────────── 분임 코드 (비밀값으로 계산 → 서버가 다시 켜져도 같음)
def group_code(g: int, salt: str) -> str:
    h = hashlib.sha256(f"motion|{salt}|{g}".encode("utf-8")).hexdigest()
    return str(1000 + int(h, 16) % 9000)


def check_code(g: int, code: str, salt: str) -> bool:
    return 1 <= g <= N_GROUPS and str(code).strip() == group_code(g, salt)


# ───────────────────────── 의뢰서
def get_request(g: int) -> dict:
    c = _connect()
    try:
        r = c.execute("SELECT * FROM req WHERE g=?", (g,)).fetchone()
    finally:
        c.close()
    if not r:
        raise StoreError("분임을 찾을 수 없습니다.")
    return {"g": g, "data": norm_request(json.loads(r["data"])), "status": r["status"],
            "submitted_at": r["submitted_at"], "updated_at": r["updated_at"]}


def all_requests() -> list[dict]:
    return [get_request(g) for g in range(1, N_GROUPS + 1)]


def _load(c, g):
    r = c.execute("SELECT * FROM req WHERE g=?", (g,)).fetchone()
    if not r:
        raise StoreError("분임을 찾을 수 없습니다.")
    return norm_request(json.loads(r["data"])), r["status"]


def _save(c, g, data, status=None):
    if status:
        c.execute("UPDATE req SET data=?, status=?, updated_at=? WHERE g=?", (json.dumps(data, ensure_ascii=False), status, time.time(), g))
    else:
        c.execute("UPDATE req SET data=?, updated_at=? WHERE g=?", (json.dumps(data, ensure_ascii=False), time.time(), g))


def _editable(status):
    if status not in EDITABLE:
        raise StoreError("제작이 시작돼서 의뢰서를 고칠 수 없어요. 고칠 내용은 [수정 요청]에 남겨 주세요.")


def set_field(g: int, field: str, value):
    """의뢰서 한 칸 저장(쓰는 대로 자동 저장)."""
    if field not in blank_request() or field == "scenes":
        raise StoreError("알 수 없는 칸입니다.")
    with _tx() as c:
        d, st = _load(c, g)
        _editable(st)
        d[field] = value
        _save(c, g, norm_request(d))


def set_scene(g: int, i: int, part: str, value):
    if part not in blank_scene():
        raise StoreError("알 수 없는 칸입니다.")
    with _tx() as c:
        d, st = _load(c, g)
        _editable(st)
        if not 0 <= i < len(d["scenes"]):
            raise StoreError("장면을 찾을 수 없습니다. 화면을 새로고침해 주세요.")
        d["scenes"][i][part] = value
        _save(c, g, norm_request(d))


def add_scene(g: int):
    with _tx() as c:
        d, st = _load(c, g)
        _editable(st)
        if len(d["scenes"]) >= 15:
            raise StoreError("장면은 15개까지 넣을 수 있어요.")
        d["scenes"].append(blank_scene())
        _save(c, g, d)


def del_scene(g: int, i: int):
    with _tx() as c:
        d, st = _load(c, g)
        _editable(st)
        if len(d["scenes"]) <= 1:
            raise StoreError("장면은 하나 이상 있어야 해요.")
        if 0 <= i < len(d["scenes"]):
            d["scenes"].pop(i)
        _save(c, g, d)


def move_scene(g: int, i: int, delta: int):
    with _tx() as c:
        d, st = _load(c, g)
        _editable(st)
        j = i + delta
        if 0 <= i < len(d["scenes"]) and 0 <= j < len(d["scenes"]):
            d["scenes"][i], d["scenes"][j] = d["scenes"][j], d["scenes"][i]
        _save(c, g, d)


def missing(d: dict) -> list[str]:
    """제출 전에 꼭 채워야 하는 칸."""
    out = []
    if not str(d["title"]).strip():
        out.append("영상 제목")
    if not str(d["message"]).strip():
        out.append("전하고 싶은 한 문장")
    if not any(str(s["text"]).strip() or str(s["look"]).strip() for s in d["scenes"]):
        out.append("장면 구성 (한 장면 이상)")
    if d["length"] == "직접 입력" and not str(d["length_custom"]).strip():
        out.append("영상 길이")
    return out


def submit(g: int):
    with _tx() as c:
        d, st = _load(c, g)
        _editable(st)
        m = missing(d)
        if m:
            raise StoreError("아직 비어 있는 칸이 있어요: " + ", ".join(m))
        c.execute("UPDATE req SET status='submitted', submitted_at=?, updated_at=? WHERE g=?", (time.time(), time.time(), g))


def set_status(g: int, status: str):
    if status not in STATUS:
        raise StoreError("알 수 없는 상태입니다.")
    with _tx() as c:
        c.execute("UPDATE req SET status=?, updated_at=? WHERE g=?", (status, time.time(), g))


def total_sec(d: dict) -> int:
    return sum(int(s["sec"]) for s in d["scenes"])


def length_sec(d: dict) -> int | None:
    m = {"15초": 15, "30초": 30, "1분": 60}
    if d["length"] in m:
        return m[d["length"]]
    n = re.findall(r"\d+", str(d["length_custom"]))
    if not n:
        return None
    v = int(n[0])
    return v * 60 if "분" in str(d["length_custom"]) and "초" not in str(d["length_custom"]) else v


# ───────────────────────── 파일
def _safe(name: str) -> str:
    base = os.path.basename(str(name)).strip() or "file"
    base = re.sub(r"[^\w.\-가-힣 ()]+", "_", base)[:80]
    return base


def _put_file(g: int, prefix: str, name: str, data: bytes) -> tuple[str, int]:
    d = os.path.join(FILES, f"g{g}")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{prefix}_{int(time.time() * 1000)}_{_safe(name)}")
    with open(path, "wb") as f:
        f.write(data)
    return path, len(data)


def add_attachment(g: int, name: str, data: bytes) -> int:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ATT_TYPES:
        raise StoreError(f"올릴 수 없는 파일 형식입니다: {name}")
    path, size = _put_file(g, "att", name, data)
    with _tx() as c:
        cur = c.execute("INSERT INTO att(g, name, path, size, at) VALUES (?,?,?,?,?)", (g, _safe(name), path, size, time.time()))
        return cur.lastrowid


def attachments(g: int) -> list[dict]:
    c = _connect()
    try:
        rows = c.execute("SELECT * FROM att WHERE g=? ORDER BY id", (g,)).fetchall()
    finally:
        c.close()
    return [dict(r) for r in rows if os.path.exists(r["path"])]


def del_attachment(g: int, aid: int):
    with _tx() as c:
        r = c.execute("SELECT * FROM att WHERE id=? AND g=?", (aid, g)).fetchone()
        if r:
            c.execute("DELETE FROM att WHERE id=?", (aid,))
    if r:
        with contextlib.suppress(OSError):
            os.remove(r["path"])


def add_result(g: int, name: str, data: bytes, note: str = "", mark_done: bool = True) -> int:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in RES_TYPES:
        raise StoreError(f"올릴 수 없는 파일 형식입니다: {name}")
    path, size = _put_file(g, "res", name, data)
    with _tx() as c:
        cur = c.execute("INSERT INTO res(g, name, path, size, note, at) VALUES (?,?,?,?,?,?)",
                        (g, _safe(name), path, size, str(note).strip(), time.time()))
        if mark_done:
            c.execute("UPDATE req SET status='done', updated_at=? WHERE g=?", (time.time(), g))
        return cur.lastrowid


def results(g: int) -> list[dict]:
    """최신 것부터."""
    c = _connect()
    try:
        rows = c.execute("SELECT * FROM res WHERE g=? ORDER BY id DESC", (g,)).fetchall()
    finally:
        c.close()
    out = []
    for r in rows:
        if os.path.exists(r["path"]):
            d = dict(r)
            d["ext"] = d["name"].rsplit(".", 1)[-1].lower() if "." in d["name"] else ""
            d["video"] = d["ext"] in VIDEO_EXT
            out.append(d)
    return out


def get_result(rid: int) -> dict | None:
    c = _connect()
    try:
        r = c.execute("SELECT * FROM res WHERE id=?", (rid,)).fetchone()
    finally:
        c.close()
    if not r or not os.path.exists(r["path"]):
        return None
    d = dict(r)
    d["ext"] = d["name"].rsplit(".", 1)[-1].lower() if "." in d["name"] else ""
    d["video"] = d["ext"] in VIDEO_EXT
    return d


def del_result(rid: int):
    with _tx() as c:
        r = c.execute("SELECT * FROM res WHERE id=?", (rid,)).fetchone()
        if r:
            c.execute("DELETE FROM res WHERE id=?", (rid,))
            if (_kv_get(c, "screen", {}) or {}).get("rid") == rid:
                _kv_put(c, "screen", {"rid": None, "at": time.time()})
    if r:
        with contextlib.suppress(OSError):
            os.remove(r["path"])


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


# ───────────────────────── 수정 요청 · 대화
def add_message(g: int, who: str, text: str):
    text = str(text).strip()
    if not text:
        raise StoreError("내용을 적어 주세요.")
    if who not in ("group", "admin"):
        raise StoreError("잘못된 요청입니다.")
    with _tx() as c:
        c.execute("INSERT INTO msg(g, who, text, at, seen) VALUES (?,?,?,?,?)", (g, who, text[:2000], time.time(), 1 if who == "admin" else 0))
        if who == "group":
            st = c.execute("SELECT status FROM req WHERE g=?", (g,)).fetchone()["status"]
            if st == "done":
                c.execute("UPDATE req SET status='revise', updated_at=? WHERE g=?", (time.time(), g))


def messages(g: int) -> list[dict]:
    c = _connect()
    try:
        rows = c.execute("SELECT * FROM msg WHERE g=? ORDER BY id", (g,)).fetchall()
    finally:
        c.close()
    return [dict(r) for r in rows]


def unseen(g: int) -> int:
    c = _connect()
    try:
        return c.execute("SELECT COUNT(*) n FROM msg WHERE g=? AND who='group' AND seen=0", (g,)).fetchone()["n"]
    finally:
        c.close()


def mark_seen(g: int):
    with _tx() as c:
        c.execute("UPDATE msg SET seen=1 WHERE g=? AND who='group'", (g,))


def pending_revisions(g: int) -> list[dict]:
    """마지막 결과물 이후에 분임이 남긴 요청."""
    rs = results(g)
    last = rs[0]["at"] if rs else 0
    return [m for m in messages(g) if m["who"] == "group" and m["at"] > last]


# ───────────────────────── 스크린(프로젝터)에 틀 것
def screen_get() -> dict:
    c = _connect()
    try:
        return _kv_get(c, "screen", {}) or {"rid": None, "at": 0}
    finally:
        c.close()


def screen_set(rid: int | None):
    with _tx() as c:
        _kv_put(c, "screen", {"rid": rid, "at": time.time()})


def board_token() -> str:
    """스크린이 다시 그려야 하는지 보는 값(틀 영상·상태·결과물 수가 바뀌면 달라짐)."""
    c = _connect()
    try:
        a = ",".join(f"{r['g']}:{r['status']}:{json.loads(r['data']).get('title', '')}" for r in c.execute("SELECT g, status, data FROM req ORDER BY g"))
        b = c.execute("SELECT COUNT(*) n, ifnull(MAX(id),0) m FROM res").fetchone()
        s = _kv_get(c, "screen", {}) or {}
        n = _kv_get(c, "settings", {}) or {}
    finally:
        c.close()
    return hashlib.md5(f"{a}|{b['n']}|{b['m']}|{s.get('rid')}|{s.get('at')}|{json.dumps(n, ensure_ascii=False)}".encode()).hexdigest()


# ───────────────────────── Claude에게 보낼 요청문
def prompt_text(g: int, S: dict | None = None) -> str:
    S = S or get_settings()
    R = get_request(g)
    d = R["data"]
    L = length_sec(d)
    length = d["length_custom"] if d["length"] == "직접 입력" else d["length"]
    use = d["use_etc"] if d["use"] == "기타" and str(d["use_etc"]).strip() else d["use"]
    ratio = d["ratio"].split(" (")[0]
    res = "3840×2160" if d["quality"].startswith("4K") else "1920×1080"
    if ratio.startswith("세로"):
        res = "2160×3840" if d["quality"].startswith("4K") else "1080×1920"
    elif ratio.startswith("정사각"):
        res = "2160×2160" if d["quality"].startswith("4K") else "1080×1080"
    atts = attachments(g)
    lines = [
        f"아래 의뢰서대로 모션 영상을 만들어 줘. ({S['event']} · {gname(g, S)})",
        "",
        "[만들 때 지킬 것]",
        f"- 결과물: mp4 영상, {ratio}, {res}, 길이 약 {length}" + (" · 끝과 처음이 자연스럽게 이어지게(반복 재생용)" if d["loop"].startswith("계속") else ""),
        "- 장면별 미리보기 그림을 먼저 보여 주고, 확인하면 영상으로 만들어 줘.",
        "- 배경음악은 새로 만든 곡으로. 기존 노래·유명한 곡 멜로디는 쓰지 마.",
        "- 유명 캐릭터·영화·게임 그림이나 다른 회사 로고·디자인을 따라 하지 말고 새로 그려 줘.",
        "- 관공서 행사라서 욱일기처럼 보일 수 있는 햇살(방사선) 무늬는 쓰지 마.",
        "- 화면에 나올 글자는 아래 적은 그대로(띄어쓰기 포함) 넣어 줘.",
        "",
        "[1. 기본 정보]",
        f"- 영상 제목: {d['title']}",
        f"- 쓰임새: {use}",
        f"- 길이: {length}",
        f"- 화면: {d['ratio']} · {d['quality']}",
        f"- 재생: {d['loop']}",
        "",
        "[2. 전하고 싶은 것]",
        f"- 핵심 한 문장: {d['message']}",
    ]
    if str(d["audience"]).strip():
        lines.append(f"- 보는 사람: {d['audience']}")
    if str(d["feeling"]).strip():
        lines.append(f"- 보고 느꼈으면 하는 것: {d['feeling']}")
    lines += ["", "[3. 분위기와 디자인]"]
    if d["mood"]:
        lines.append(f"- 분위기: {', '.join(d['mood'])}")
    lines.append(f"- 그림 스타일: {d['style']}")
    if str(d["color"]).strip():
        lines.append(f"- 주인공 색: {d['color']}")
    lines.append(f"- 글꼴 느낌: {d['font']}")
    if str(d["ref"]).strip():
        lines.append(f"- 참고할 느낌(분위기만 참고, 따라 하지 말 것): {d['ref']}")
    if str(d["avoid"]).strip():
        lines.append(f"- 피하고 싶은 것: {d['avoid']}")
    lines += ["", f"[4. 장면 구성] (장면 길이 합계 {total_sec(d)}초" + (f" / 목표 {L}초" if L else "") + ")"]
    for i, s in enumerate(d["scenes"], 1):
        lines.append(f"장면 {i} ({s['sec']}초)")
        lines.append(f"  · 화면 글자: {s['text'].strip() or '(없음)'}")
        if str(s["look"]).strip():
            lines.append(f"  · 보이는 모습: {s['look']}")
        if str(s["motion"]).strip():
            lines.append(f"  · 움직임: {s['motion']}")
    lines += ["", "[5. 소리]", f"- 배경음악: {d['music']}" + (f" ({d['music_mood']})" if d["music"] == YESNO_MUSIC[0] and str(d["music_mood"]).strip() else "")]
    if str(d["sfx"]).strip():
        lines.append(f"- 효과음: {d['sfx']}")
    lines.append(f"- 내레이션: {d['narration']}")
    lines += ["", "[6. 넣을 자료와 받는 형태]"]
    lines.append("- 첨부: " + (", ".join(a["name"] for a in atts) + " (같이 첨부함)" if atts else "없음"))
    if d["hold_end"]:
        lines.append(f"- 마지막 장면에서 {d['hold_end']}초 멈추기")
    if d["cover"]:
        lines.append("- 마지막 장면 그림 파일(PNG)도 따로 주기")
    if str(d["etc"]).strip():
        lines += ["", "[기타 요청]", str(d["etc"]).strip()]
    revs = pending_revisions(g)
    if revs and results(g):
        lines += ["", "[수정 요청 — 앞서 만든 영상에서 고칠 것]"] + [f"- {m['text']}" for m in revs]
    return "\n".join(lines)


def revision_text(g: int, S: dict | None = None) -> str:
    """이미 만든 영상을 고칠 때 Claude 대화창에 이어서 보낼 글."""
    S = S or get_settings()
    revs = pending_revisions(g)
    if not revs:
        return ""
    return "\n".join([f"앞서 만든 {gname(g, S)} 영상을 아래처럼 고쳐 줘. 나머지는 그대로 두고, 고친 영상을 mp4로 다시 줘.", ""] +
                     [f"- {m['text']}" for m in revs])


# ───────────────────────── 백업 · 초기화
def backup() -> str:
    c = _connect()
    try:
        out = {
            "kind": "motion-backup", "at": time.time(),
            "settings": _kv_get(c, "settings", {}) or {},
            "requests": [dict(r) for r in c.execute("SELECT * FROM req ORDER BY g")],
            "messages": [dict(r) for r in c.execute("SELECT * FROM msg ORDER BY id")],
            "results": [{k: r[k] for k in ("g", "name", "size", "note", "at")} for r in c.execute("SELECT * FROM res ORDER BY id")],
        }
    finally:
        c.close()
    return json.dumps(out, ensure_ascii=False, indent=1)


def restore(raw: str | bytes) -> int:
    try:
        b = json.loads(raw)
        assert b.get("kind") == "motion-backup"
    except Exception:
        raise StoreError("백업 파일이 아닙니다.")
    with _tx() as c:
        if b.get("settings"):
            _kv_put(c, "settings", b["settings"])
        for r in b.get("requests", []):
            g = int(r["g"])
            if 1 <= g <= N_GROUPS:
                c.execute("UPDATE req SET data=?, status=?, submitted_at=?, updated_at=? WHERE g=?",
                          (json.dumps(norm_request(json.loads(r["data"])), ensure_ascii=False),
                           r["status"] if r["status"] in STATUS else "draft", r.get("submitted_at"), r.get("updated_at") or time.time(), g))
        c.execute("DELETE FROM msg")
        for m in b.get("messages", []):
            c.execute("INSERT INTO msg(g, who, text, at, seen) VALUES (?,?,?,?,?)", (m["g"], m["who"], m["text"], m["at"], m.get("seen", 1)))
    return len(b.get("requests", []))


def results_zip() -> bytes:
    """모든 분임의 결과물을 한 파일로(관리팀 보관용)."""
    S = get_settings()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for g in range(1, N_GROUPS + 1):
            for r in reversed(results(g)):
                stamp = time.strftime("%H%M", time.gmtime(r["at"] + 9 * 3600))
                z.write(r["path"], f"{gname(g, S)}/{stamp}_{r['name']}")
        z.writestr("의뢰서_백업.json", backup())
    return buf.getvalue()


def reset_all():
    with _tx() as c:
        c.execute("DELETE FROM att")
        c.execute("DELETE FROM res")
        c.execute("DELETE FROM msg")
        c.execute("DELETE FROM kv WHERE k='screen'")
        for g in range(1, N_GROUPS + 1):
            c.execute("UPDATE req SET data=?, status='draft', submitted_at=NULL, updated_at=? WHERE g=?",
                      (json.dumps(blank_request(), ensure_ascii=False), time.time(), g))
    shutil.rmtree(FILES, ignore_errors=True)
    os.makedirs(FILES, exist_ok=True)

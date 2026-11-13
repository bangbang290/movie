"""워크숍 모션 영상 의뢰(AI 모션그래픽 광고제) — 저장소(SQLite + 파일 폴더).

  분임(1~7)마다 분임 기획서 1장 · 첨부 자료 · 결과물(영상·그림) · 수정 요청(최대 2번)·문의를 보관합니다.
  상태 흐름: draft(작성 중) → submitted(접수) → making(제작 중) → done(완료) ⇄ revise(수정 요청)
  분임 비밀번호는 분임이 처음 들어올 때 직접 만듭니다(숫자 4자리, 해시로만 보관 · 관리팀은 초기화만 가능).
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

# 분임 기획서(AI 모션그래픽 광고제)와 같은 칸
FORMATS = ["웅장한 광고", "영화 예고편", "뉴스 속보", "인포그래픽", "귀여운 애니메이션", "기타"]
SCENES = [("① 시작", "0~5초"), ("② 전개", "5~15초"), ("③ 강조", "15~25초"), ("④ 마무리", "25~30초")]
ROLES = [("director", "감독"), ("writer", "작가"), ("prompter", "프롬프트 담당"), ("presenter", "발표자")]
MAX_REV = 2          # 수정 요청은 최대 2번
LENGTH = "30초"

ATT_TYPES = ["png", "jpg", "jpeg", "gif", "webp", "svg", "pdf", "mp3", "wav", "m4a", "mp4", "mov"]
RES_TYPES = ["mp4", "mov", "webm", "png", "jpg", "jpeg", "gif", "webp"]
VIDEO_EXT = ("mp4", "mov", "webm")


class StoreError(Exception):
    pass


def blank_request() -> dict:
    return {
        "director": "", "writer": "", "prompter": "", "presenter": "",
        "topic": "", "title": "", "message": "", "last_line": "", "color": "", "character": "",
        "format": FORMATS[0], "format_etc": "",
        "scenes": [blank_scene() for _ in SCENES],
        "pitch": "",
    }


def blank_scene() -> dict:
    return {"look": "", "caption": "", "fx": ""}


def norm_request(d: dict | None) -> dict:
    out = blank_request()
    for k, v in (d or {}).items():
        if k in out and k != "scenes":
            out[k] = v if isinstance(v, str) else str(v)
    sc = (d or {}).get("scenes")
    sc = sc if isinstance(sc, list) else []
    for i in range(len(SCENES)):
        if i < len(sc) and isinstance(sc[i], dict):
            out["scenes"][i] = {k: str(sc[i].get(k, "") or "") for k in blank_scene()}
    if out["format"] not in FORMATS:
        out["format"] = FORMATS[0]
    return out


def format_text(d: dict) -> str:
    return (d["format_etc"].strip() or "기타") if d["format"] == "기타" else d["format"]


def filled_scenes(d: dict) -> list[tuple[int, dict]]:
    return [(i, s) for i, s in enumerate(d["scenes"]) if s["look"].strip() or s["caption"].strip()]


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
                    "CREATE TABLE IF NOT EXISTS msg (id INTEGER PRIMARY KEY AUTOINCREMENT, g INTEGER, who TEXT, text TEXT, at REAL, seen INTEGER DEFAULT 0)",
                    "CREATE TABLE IF NOT EXISTS pw (g INTEGER PRIMARY KEY, hash TEXT, salt TEXT, set_at REAL, fails INTEGER DEFAULT 0, lock_until REAL DEFAULT 0)",
                    "CREATE TABLE IF NOT EXISTS vote (k TEXT PRIMARY KEY, name TEXT, voter_g INTEGER, g INTEGER, at REAL)"):
            c.execute(sql)
        if "kind" not in [r["name"] for r in c.execute("PRAGMA table_info(msg)")]:
            c.execute("ALTER TABLE msg ADD COLUMN kind TEXT DEFAULT 'q'")
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
        "notice": "★ 칸만 채우면 돼요. 20분 안에 쓰고 맨 아래 [제출하기]를 눌러 주세요.",
        "public_url": "",
        "order": "",          # 시사회 상영 순서(예: "3,1,2"). 비우면 1분임부터
        "awards": "최우수상",   # 투표 1위 상 이름(1위 한 팀만 시상)
        "bgm": "https://www.youtube.com/watch?v=52p4L7f3DZQ",   # 관리 화면 배경음악(유튜브)
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


# ───────────────────────── 분임 비밀번호 (분임이 직접 만듦)
PW_LEN = 4
MAX_FAILS = 5        # 연속으로 이만큼 틀리면
LOCK_SEC = 30        # 잠깐 막기


def _pw_hash(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), 60000).hex()


def _check_pw_form(pw: str):
    pw = str(pw or "").strip()
    if not (len(pw) == PW_LEN and pw.isascii() and pw.isdigit()):
        raise StoreError(f"비밀번호는 숫자 {PW_LEN}자리로 넣어 주세요.")
    return pw


def _pw_row(c, g):
    return c.execute("SELECT * FROM pw WHERE g=?", (g,)).fetchone()


def has_password(g: int) -> bool:
    c = _connect()
    try:
        return _pw_row(c, g) is not None
    finally:
        c.close()


def _token_of(row) -> str | None:
    return hashlib.sha256(f"tok|{row['hash']}".encode()).hexdigest()[:16] if row else None


def session_token(g: int) -> str | None:
    """로그인 유지용 표(주소 k=에 들어감). 비밀번호 자체가 아니고, 비밀번호가 바뀌면 같이 바뀜."""
    c = _connect()
    try:
        return _token_of(_pw_row(c, g))
    finally:
        c.close()


def check_token(g: int, tok) -> bool:
    return bool(tok) and 1 <= g <= N_GROUPS and session_token(g) == str(tok)


def set_password(g: int, pw: str, pw2: str) -> str:
    """분임이 처음 들어올 때 비밀번호 만들기. 로그인 표를 돌려줌."""
    if not 1 <= g <= N_GROUPS:
        raise StoreError("분임 번호가 맞지 않아요.")
    pw = _check_pw_form(pw)
    if pw != str(pw2 or "").strip():
        raise StoreError("두 번 넣은 비밀번호가 서로 달라요. 다시 넣어 주세요.")
    salt = os.urandom(8).hex()
    with _tx() as c:
        if _pw_row(c, g):
            raise StoreError("방금 다른 분임원이 비밀번호를 먼저 만들었어요. 그 비밀번호로 들어와 주세요.")
        c.execute("INSERT INTO pw(g, hash, salt, set_at, fails, lock_until) VALUES (?,?,?,?,0,0)", (g, _pw_hash(pw, salt), salt, time.time()))
        return _token_of(_pw_row(c, g))


def login(g: int, pw: str) -> str:
    """비밀번호 확인. 맞으면 로그인 표를 돌려줌."""
    now = time.time()
    with _tx() as c:
        row = _pw_row(c, g)
        if not row:
            raise StoreError("아직 비밀번호가 없어요. 새로 만들어 주세요.")
        if row["lock_until"] and row["lock_until"] > now:
            raise StoreError(f"여러 번 틀려서 잠깐 막혔어요. {int(row['lock_until'] - now) + 1}초 뒤에 다시 해 주세요.")
        if _pw_hash(str(pw or "").strip(), row["salt"]) == row["hash"]:
            c.execute("UPDATE pw SET fails=0, lock_until=0 WHERE g=?", (g,))
            return _token_of(row)
        fails = (row["fails"] or 0) + 1
        if fails >= MAX_FAILS:
            c.execute("UPDATE pw SET fails=0, lock_until=? WHERE g=?", (now + LOCK_SEC, g))
            msg = f"비밀번호가 {MAX_FAILS}번 틀려서 {LOCK_SEC}초 동안 막아요. 잊었으면 관리팀에 초기화를 부탁하세요."
        else:
            c.execute("UPDATE pw SET fails=? WHERE g=?", (fails, g))
            msg = f"비밀번호가 맞지 않아요. ({fails}/{MAX_FAILS})"
    raise StoreError(msg)


def reset_password(g: int):
    """관리팀: 비밀번호 지우기 → 그 분임이 다음에 들어올 때 새로 만듦(이미 들어와 있던 휴대폰도 나가짐)."""
    with _tx() as c:
        c.execute("DELETE FROM pw WHERE g=?", (g,))


def password_info() -> dict[int, dict]:
    c = _connect()
    try:
        rows = {r["g"]: {"set_at": r["set_at"], "locked": bool(r["lock_until"] and r["lock_until"] > time.time())}
                for r in c.execute("SELECT * FROM pw")}
    finally:
        c.close()
    return rows


# ───────────────────────── 기획서
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
        raise StoreError("제작이 시작돼서 기획서를 고칠 수 없어요. 고칠 내용은 [수정 요청]에 남겨 주세요.")


def set_field(g: int, field: str, value):
    """기획서 한 칸 저장(쓰는 대로 자동 저장)."""
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


def missing(d: dict) -> list[str]:
    """제출 전에 꼭 채워야 하는 칸(기획서의 ★ 칸)."""
    out = []
    if not d["topic"].strip():
        out.append("주제")
    if not d["message"].strip():
        out.append("핵심 메시지")
    if not d["last_line"].strip():
        out.append("마지막 문구")
    if d["format"] == "기타" and not d["format_etc"].strip():
        out.append("영상 형식(기타)")
    if len(filled_scenes(d)) < 3:
        out.append("장면 구성 (3장면 이상)")
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
def add_message(g: int, who: str, text: str, kind: str = "q"):
    """kind: 'rev' = 수정 요청(완성본이 있을 때, 최대 2번) · 'q' = 문의·답장."""
    text = str(text).strip()
    if not text:
        raise StoreError("내용을 적어 주세요.")
    if who not in ("group", "admin") or kind not in ("rev", "q"):
        raise StoreError("잘못된 요청입니다.")
    with _tx() as c:
        if kind == "rev":
            if who != "group":
                raise StoreError("수정 요청은 분임만 보낼 수 있습니다.")
            if not c.execute("SELECT COUNT(*) n FROM res WHERE g=?", (g,)).fetchone()["n"]:
                raise StoreError("완성된 영상이 올라온 뒤에 수정 요청을 보낼 수 있어요.")
            used = c.execute("SELECT COUNT(*) n FROM msg WHERE g=? AND kind='rev'", (g,)).fetchone()["n"]
            if used >= MAX_REV:
                raise StoreError(f"수정 요청은 {MAX_REV}번까지예요. 더 필요하면 [문의]로 관리팀에 말해 주세요.")
        c.execute("INSERT INTO msg(g, who, text, at, seen, kind) VALUES (?,?,?,?,?,?)",
                  (g, who, text[:2000], time.time(), 1 if who == "admin" else 0, kind))
        if kind == "rev":
            c.execute("UPDATE req SET status='revise', updated_at=? WHERE g=?", (time.time(), g))


def messages(g: int) -> list[dict]:
    c = _connect()
    try:
        rows = c.execute("SELECT * FROM msg WHERE g=? ORDER BY id", (g,)).fetchall()
    finally:
        c.close()
    return [dict(r) for r in rows]


def rev_count(g: int) -> int:
    return sum(1 for m in messages(g) if m.get("kind") == "rev")


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
    """마지막 결과물 이후에 분임이 보낸 수정 요청."""
    rs = results(g)
    last = rs[0]["at"] if rs else 0
    return [m for m in messages(g) if m.get("kind") == "rev" and m["at"] > last]


# ───────────────────────── 스크린(프로젝터)에 틀 것
#   mode: board(대기 판) · intro(분임 소개 화면, g) · play(영상 상영, rid·g) · end(투표 화면: QR·참여 수)
#         · result(투표 결과 발표, n = 지금까지 공개한 순위 수)
SCREEN_MODES = ("board", "intro", "play", "end", "result")


def _norm_screen(s: dict | None) -> dict:
    s = dict(s or {})
    out = {"rid": s.get("rid"), "g": s.get("g"), "at": s.get("at") or 0, "mode": s.get("mode"), "n": int(s.get("n") or 0)}
    if out["mode"] not in SCREEN_MODES:          # 예전 모양({"rid": …})도 그대로 읽기
        out["mode"] = "play" if out["rid"] else "board"
    return out


def screen_get() -> dict:
    c = _connect()
    try:
        return _norm_screen(_kv_get(c, "screen", {}))
    finally:
        c.close()


def screen_go(step: dict):
    """스크린을 step({"mode": …, "g": …, "rid": …}) 상태로 바꾸기."""
    mode = step.get("mode") if step.get("mode") in SCREEN_MODES else "board"
    g, rid = step.get("g"), step.get("rid")
    if mode == "intro" and not (isinstance(g, int) and 1 <= g <= N_GROUPS):
        raise StoreError("없는 분임입니다.")
    if mode == "play":
        r = get_result(rid) if rid else None
        if not r:
            raise StoreError("틀 결과물이 없습니다.")
        g = r["g"]
    n = max(0, int(step.get("n") or 0)) if mode == "result" else 0
    with _tx() as c:
        _kv_put(c, "screen", {"mode": mode, "g": g if mode in ("intro", "play") else None,
                              "rid": rid if mode == "play" else None, "n": n, "at": time.time()})


def screen_set(rid: int | None):
    """결과물 하나를 바로 틀기(None이면 대기 판)."""
    screen_go({"mode": "play", "rid": rid} if rid else {"mode": "board"})


def screen_order(S: dict | None = None) -> list[int]:
    """상영 순서: [시사회] 탭의 '상영 순서'(예: 3,1,2)대로, 빠진 분임은 번호 순으로 뒤에."""
    S = S or get_settings()
    out: list[int] = []
    for t in re.split(r"[^0-9]+", str(S.get("order", ""))):
        if t and 1 <= int(t) <= N_GROUPS and int(t) not in out:
            out.append(int(t))
    return out + [g for g in range(1, N_GROUPS + 1) if g not in out]


def premiere_clip(g: int) -> dict | None:
    """시사회에 틀 결과물: 가장 최근에 올린 영상(영상이 없으면 가장 최근 그림)."""
    rs = results(g)
    vids = [r for r in rs if r["video"]]
    return (vids or rs or [None])[0]


def lineup(S: dict | None = None) -> list[dict]:
    """시사회 순서대로 [{g, clip}] — 결과물이 올라온 분임만."""
    out = []
    for g in screen_order(S):
        clip = premiere_clip(g)
        if clip:
            out.append({"g": g, "clip": clip})
    return out


def screen_next(S: dict | None = None) -> dict:
    """[▶ 다음]이 할 일: 대기 판 → 첫 분임 소개 → 그 분임 영상 → 다음 분임 소개 → … → 투표 화면 → 대기 판."""
    L = lineup(S)
    cur = screen_get()
    gs = [x["g"] for x in L]
    if not L or cur["mode"] in ("end", "result"):
        return {"mode": "board"}
    if cur["mode"] == "intro" and cur["g"] in gs:
        x = L[gs.index(cur["g"])]
        return {"mode": "play", "g": x["g"], "rid": x["clip"]["id"]}
    if cur["mode"] in ("intro", "play") and cur["g"]:
        order = screen_order(S)
        after = order[order.index(cur["g"]) + 1:] if cur["g"] in order else []
        for g in after:
            if g in gs:
                return {"mode": "intro", "g": g}
        return {"mode": "end"}
    return {"mode": "intro", "g": gs[0]}


def board_token() -> str:
    """스크린이 다시 그려야 하는지 보는 값(틀 영상·상태·결과물 수가 바뀌면 달라짐)."""
    c = _connect()
    try:
        a = ",".join(f"{r['g']}:{r['status']}:{json.loads(r['data']).get('title', '')}" for r in c.execute("SELECT g, status, data FROM req ORDER BY g"))
        b = c.execute("SELECT COUNT(*) n, ifnull(MAX(id),0) m FROM res").fetchone()
        s = _kv_get(c, "screen", {}) or {}
        n = _kv_get(c, "settings", {}) or {}
        v = c.execute("SELECT COUNT(*) n FROM vote").fetchone()["n"]
        vs = (_kv_get(c, "vote", {}) or {}).get("state")
        ro = _kv_get(c, "roster", {}) or {}
    finally:
        c.close()
    return hashlib.md5(f"{a}|{b['n']}|{b['m']}|{s.get('rid')}|{s.get('at')}|{json.dumps(n, ensure_ascii=False)}|{v}|{vs}|"
                       f"{json.dumps(ro, ensure_ascii=False)}".encode()).hexdigest()


# ───────────────────────── 투표 (1인 1표 · 내 이름으로 · 우리 분임 작품은 빼고)
#   명단: kv "roster" = {"0": [분임 없이 투표하는 사람], "1": [1분임 명단], …}
#   상태: kv "vote" = {"state": ready(아직) | open(투표 중) | closed(마감)}   표: vote 테이블(이름당 1줄)
VOTE_STATES = ("ready", "open", "closed")
AWARD_TOP = 1          # 시상할 순위 수(1 = 최우수 한 팀만)


def name_key(name: str) -> str:
    """이름 비교용: 띄어쓰기·대소문자 무시."""
    return re.sub(r"\s+", "", str(name or "")).lower()


def parse_names(text: str) -> list[str]:
    """명단 칸 → 이름 목록(한 줄에 한 명, 쉼표로 나눠도 됨)."""
    out: list[str] = []
    for t in re.split(r"[\n,，、]+", str(text or "")):
        t = re.sub(r"\s+", " ", t).strip()[:20]
        if t and t not in out:
            out.append(t)
    return out


def get_roster() -> dict[int, list[str]]:
    c = _connect()
    try:
        raw = _kv_get(c, "roster", {}) or {}
    finally:
        c.close()
    return {g: [str(n) for n in raw.get(str(g), [])] for g in range(0, N_GROUPS + 1)}


def save_roster(roster: dict[int, list[str]]):
    """명단 저장. 띄어쓰기를 빼고 같은 이름이 두 번 있으면(분임이 달라도) 저장하지 않음."""
    S = get_settings()
    label = lambda g: "분임 없음" if g == 0 else S["names"][g - 1]     # noqa: E731
    seen: dict[str, tuple[str, int]] = {}
    dup, clean = [], {}
    for g in range(0, N_GROUPS + 1):
        names = []
        for n in roster.get(g, []):
            n = re.sub(r"\s+", " ", str(n)).strip()[:20]
            k = name_key(n)
            if not k:
                continue
            if k in seen:
                dup.append(f"{n}({label(seen[k][1])}·{label(g)})" if seen[k][1] != g else f"{n}({label(g)}에 두 번)")
                continue
            seen[k] = (n, g)
            names.append(n)
        clean[str(g)] = names
    if dup:
        raise StoreError("같은 이름이 있어요: " + ", ".join(dup) + " → '김민수A', '김민수B'처럼 구분해서 다시 저장해 주세요.")
    with _tx() as c:
        _kv_put(c, "roster", clean)
    return sum(len(v) for v in clean.values())


def find_voter(name: str) -> tuple[str, int] | None:
    """명단에서 이름 찾기 → (명단에 적힌 이름, 분임 번호 · 분임 없음은 0)."""
    k = name_key(name)
    if not k:
        return None
    for g, names in get_roster().items():
        for n in names:
            if name_key(n) == k:
                return n, g
    return None


def vote_state() -> str:
    c = _connect()
    try:
        s = (_kv_get(c, "vote", {}) or {}).get("state")
    finally:
        c.close()
    return s if s in VOTE_STATES else "ready"


def set_vote_state(state: str):
    if state not in VOTE_STATES:
        raise StoreError("잘못된 투표 상태입니다.")
    with _tx() as c:
        _kv_put(c, "vote", {"state": state, "at": time.time()})


def vote_candidates(voter_g: int, S: dict | None = None) -> list[int]:
    """고를 수 있는 작품: 결과물이 올라온 분임(아무도 없으면 모든 분임)에서 내 분임을 뺀 것, 상영 순서대로."""
    gs = [x["g"] for x in lineup(S)] or screen_order(S)
    return [g for g in gs if g != voter_g]


def has_voted(name: str) -> bool:
    c = _connect()
    try:
        return c.execute("SELECT 1 FROM vote WHERE k=?", (name_key(name),)).fetchone() is not None
    finally:
        c.close()


def roster_total() -> int:
    return sum(len(v) for v in get_roster().values())


def cast_vote(name: str, g: int, voter_g: int | None = None) -> str:
    """투표. 명단이 있으면 명단의 이름만(분임은 명단대로), 명단이 비어 있으면 '자유 입력'(이름 + 직접 고른 우리 분임)."""
    if roster_total():
        who = find_voter(name)
        if not who:
            raise StoreError("명단에 없는 이름이에요. 분임에 등록된 이름 그대로 써 주세요.")
    else:
        disp = re.sub(r"\s+", " ", str(name or "")).strip()[:20]
        if len(name_key(disp)) < 2:
            raise StoreError("이름을 두 글자 이상 써 주세요.")
        if voter_g is None or not 0 <= int(voter_g) <= N_GROUPS:
            raise StoreError("우리 분임을 골라 주세요.")
        who = (disp, int(voter_g))
    disp, vg = who
    if g == vg:
        raise StoreError("우리 분임 작품에는 투표할 수 없어요.")
    if g not in vote_candidates(vg):
        raise StoreError("고를 수 없는 작품입니다.")
    with _tx() as c:
        state = (_kv_get(c, "vote", {}) or {}).get("state")
        if state != "open":
            raise StoreError("투표가 마감됐어요." if state == "closed" else "아직 투표 시간이 아니에요.")
        if c.execute("SELECT 1 FROM vote WHERE k=?", (name_key(disp),)).fetchone():
            raise StoreError("이미 투표한 이름이에요.")
        c.execute("INSERT INTO vote(k, name, voter_g, g, at) VALUES (?,?,?,?,?)", (name_key(disp), disp, vg, int(g), time.time()))
    return disp


def voters() -> list[dict]:
    """투표한 사람(누구를 찍었는지는 빼고)."""
    c = _connect()
    try:
        return [dict(r) for r in c.execute("SELECT name, voter_g, at FROM vote ORDER BY at")]
    finally:
        c.close()


def vote_tally() -> dict[int, int]:
    out = {g: 0 for g in range(1, N_GROUPS + 1)}
    c = _connect()
    try:
        for r in c.execute("SELECT g, COUNT(*) n FROM vote GROUP BY g"):
            if r["g"] in out:
                out[r["g"]] = r["n"]
    finally:
        c.close()
    return out


def ranking(S: dict | None = None) -> list[dict]:
    """득표순 [{g, votes, rank}] — 표가 같으면 공동 순위(1, 1, 3 …)."""
    order = screen_order(S)
    items = sorted(vote_tally().items(), key=lambda kv: (-kv[1], order.index(kv[0])))
    out, prev, rank = [], None, 0
    for i, (g, v) in enumerate(items, 1):
        if v != prev:
            rank, prev = i, v
        out.append({"g": g, "votes": v, "rank": rank})
    return out


def award_steps(S: dict | None = None) -> list[dict]:
    """결과 발표 단계: 1위(최우수상) 한 팀만. 표가 같으면 공동 1위로 함께. [{rank, award, groups:[{g, votes}]}]"""
    S = S or get_settings()
    names = [a.strip() for a in str(S.get("awards") or "").split(",")]
    top = [x for x in ranking(S) if x["votes"] > 0 and x["rank"] <= AWARD_TOP]
    return [{"rank": r, "award": (names[r - 1] if r - 1 < len(names) and names[r - 1] else f"{r}위"),
             "groups": [x for x in top if x["rank"] == r]} for r in sorted({x["rank"] for x in top}, reverse=True)]


def reset_votes():
    """표만 지우고 투표를 '준비'로(명단은 그대로)."""
    with _tx() as c:
        c.execute("DELETE FROM vote")
        _kv_put(c, "vote", {"state": "ready", "at": time.time()})
        if (_kv_get(c, "screen", {}) or {}).get("mode") in ("end", "result"):
            _kv_put(c, "screen", {"mode": "board", "rid": None, "g": None, "n": 0, "at": time.time()})


# ───────────────────────── Claude에게 보낼 요청문
def _eul(word: str) -> str:
    """받침이 있으면 '을', 없으면 '를'."""
    ch = word.strip()[-1:] if word.strip() else ""
    if ch and "가" <= ch <= "힣":
        return "을" if (ord(ch) - 0xAC00) % 28 else "를"
    return "을(를)"


def prompt_text(g: int, S: dict | None = None) -> str:
    """제작 부스 프롬프트 틀에 기획서를 채운 글(Claude 대화창에 그대로 붙여 넣기)."""
    S = S or get_settings()
    d = get_request(g)["data"]
    atts = attachments(g)
    has_img = any(a["name"].rsplit(".", 1)[-1].lower() in ("png", "jpg", "jpeg", "gif", "webp", "svg") for a in atts)
    topic = d["topic"].strip() or "(주제)"
    lines = ["너는 최고의 모션그래픽 디자이너야.", f"{topic}{_eul(topic)} 알리는 {LENGTH} 모션그래픽 영상을 만들어줘."]
    if has_img:
        lines.append("첨부한 캐릭터가 주인공이야.")
    lines += [f"- 영상 제목: {d['title'].strip()}" if d["title"].strip() else None,
              f"- 핵심 메시지: {d['message'].strip()}",
              f"- 영상 형식: {format_text(d)}",
              "- 장면 구성:"]
    for i, s in enumerate(d["scenes"]):
        if not (s["look"].strip() or s["caption"].strip()):
            continue
        name, sec = SCENES[i]
        part = [s["look"].strip()]
        if s["caption"].strip():
            part.append(f'자막 "{s["caption"].strip()}"')
        if s["fx"].strip():
            part.append(f"효과: {s['fx'].strip()}")
        lines.append(f"  {name} ({sec}) " + " / ".join(p for p in part if p))
    lines += [f"- 분위기와 색감: {d['color'].strip() or '자유롭게'}",
              f"- 등장 캐릭터: {d['character'].strip() or '자유롭게'}",
              f"- 마지막 문구: {d['last_line'].strip()}",
              "- 화면 비율: 16:9",
              "- 저작권 있는 음악·캐릭터·로고는 쓰지 말고 새로 만들어줘. 욱일기처럼 보이는 햇살 무늬는 쓰지 마."]
    revs = pending_revisions(g)
    if revs and results(g):
        lines += ["", "[수정 요청 — 앞서 만든 영상에서 고칠 것]"] + [f"- {m['text']}" for m in revs]
    return "\n".join(x for x in lines if x is not None)


def revision_text(g: int, S: dict | None = None) -> str:
    """이미 만든 영상을 고칠 때, 그 영상을 만든 대화창에 이어서 보낼 글(전체를 다시 만들지 않기)."""
    revs = pending_revisions(g)
    if not revs:
        return ""
    return "\n".join(["전체를 다시 만들지 말고, 아래 부분만 고쳐줘. 나머지는 그대로 두고 고친 영상을 다시 줘.", ""] +
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
            "passwords": [{k: r[k] for k in ("g", "hash", "salt", "set_at")} for r in c.execute("SELECT * FROM pw ORDER BY g")],
            "roster": _kv_get(c, "roster", {}) or {},
            "vote": _kv_get(c, "vote", {}) or {},
            "votes": [dict(r) for r in c.execute("SELECT * FROM vote ORDER BY at")],
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
            c.execute("INSERT INTO msg(g, who, text, at, seen, kind) VALUES (?,?,?,?,?,?)",
                      (m["g"], m["who"], m["text"], m["at"], m.get("seen", 1), m.get("kind") or "q"))
        if "passwords" in b:      # 분임 비밀번호도 그대로(이미 들어와 있던 휴대폰도 계속 쓸 수 있게)
            c.execute("DELETE FROM pw")
            for p in b["passwords"]:
                if 1 <= int(p["g"]) <= N_GROUPS and p.get("hash") and p.get("salt"):
                    c.execute("INSERT INTO pw(g, hash, salt, set_at, fails, lock_until) VALUES (?,?,?,?,0,0)",
                              (int(p["g"]), p["hash"], p["salt"], p.get("set_at")))
        if b.get("roster"):          # 투표 명단·상태·표도 그대로
            _kv_put(c, "roster", b["roster"])
        if b.get("vote"):
            _kv_put(c, "vote", b["vote"])
        if "votes" in b:
            c.execute("DELETE FROM vote")
            for v in b["votes"]:
                c.execute("INSERT OR IGNORE INTO vote(k, name, voter_g, g, at) VALUES (?,?,?,?,?)",
                          (v["k"], v["name"], v["voter_g"], v["g"], v["at"]))
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
        z.writestr("기획서_백업.json", backup())
    return buf.getvalue()


def reset_all():
    with _tx() as c:
        c.execute("DELETE FROM att")
        c.execute("DELETE FROM res")
        c.execute("DELETE FROM msg")
        c.execute("DELETE FROM pw")
        c.execute("DELETE FROM vote")          # 투표 명단(roster)은 설정처럼 남김(리허설용 연습 명단이면 같이 지움)
        if (_kv_get(c, "rehearsal", {}) or {}).get("roster"):
            c.execute("DELETE FROM kv WHERE k='roster'")
        c.execute("DELETE FROM kv WHERE k IN ('screen', 'vote', 'rehearsal')")
        for g in range(1, N_GROUPS + 1):
            c.execute("UPDATE req SET data=?, status='draft', submitted_at=NULL, updated_at=? WHERE g=?",
                      (json.dumps(blank_request(), ensure_ascii=False), time.time(), g))
    shutil.rmtree(FILES, ignore_errors=True)
    os.makedirs(FILES, exist_ok=True)


# ───────────────────────── 리허설(연습용 데이터) — 영상을 만들지 않고 시사회·투표·결과 발표를 끝까지 연습
REHEARSAL_SAMPLE = os.path.join(BASE, "rehearsal_sample.mp4")    # 7초 샘플(카운트다운·삐 소리). 없으면 그림으로 대신
REHEARSAL_NAMES = ["김하늘", "이바다", "박구름", "최햇살", "정별빛", "강노을", "윤새벽", "한가람", "오솔길", "서나래", "문다온", "배하람", "신이슬", "유보람",
                   "장미르", "임가온", "조은솔", "홍해든", "권다솜", "황누리", "송아라", "안마루", "전하랑", "고은별", "남다인", "류하진", "변소담", "차도윤"]
REHEARSAL_PLANS = [
    ("우리 일을 광고하라", "심사2국, 오늘도 정확하게", "웅장한 광고", "보이지 않는 곳에서 숫자 하나까지 지킨다", "정확함이 우리의 자부심입니다",
     "평범한 서류 검토를 블록버스터처럼 찍었어요. 관전 포인트는 도장 찍는 슬로모션!",
     [("서류 더미 위로 조명이 떨어진다", "모두가 퇴근한 시간"), ("돋보기로 숫자 하나를 찾아낸다", "단 하나의 오류도 놓치지 않는다"),
      ("도장이 쾅 찍히며 금빛이 퍼진다", "심사2국")]),
    ("숫자로 보는 2026 심사2국", "숫자로 보는 2026", "인포그래픽", "올해도 우리는 이만큼 해냈다", "2026, 수고했어 우리",
     "진짜 숫자와 체감 숫자를 섞었어요. 커피 잔 수는 진짜입니다.",
     [("막대그래프가 쑥쑥 자란다", "처리 건수 ○○○건"), ("비행기 아이콘이 지도를 가로지른다", "출장 ○○회"), ("커피잔이 끝없이 쌓인다", "커피 ∞잔")]),
    ("우리끼리 공익광고", "회의는 30분 안에", "귀여운 애니메이션", "짧은 회의가 모두를 살린다", "회의는 30분 안에, 약속해요",
     "회의가 길어질수록 시계가 녹아내려요. 마지막 반전을 봐 주세요.",
     [("시계 바늘이 빙글빙글 돈다", "회의 시작 1시간째…"), ("마타가 타이머를 들고 등장", "30분이면 충분하멍!"), ("모두 웃으며 자리에서 일어난다", "회의는 30분 안에")]),
    ("2030 심사2국 예고편", "2030: AI와 함께", "영화 예고편", "2030년에도 판단은 사람이 한다", "2030 심사2국, 개봉 박두",
     "AI 동료와 함께 일하는 4년 뒤를 상상했어요.",
     [("어두운 화면에 2030 글자가 떠오른다", "2030년, 심사2국"), ("AI 동료가 서류를 순식간에 정리한다", "AI가 정리하고"), ("직원이 마지막 확인 버튼을 누른다", "사람이 판단한다")]),
    ("우리끼리 공익광고", "속보: 퇴근 5분 전 업무 요청 멈춰!", "뉴스 속보", "퇴근 5분 전 업무 요청은 내일로", "퇴근 5분 전, 멈춰 주세요",
     "뉴스 앵커가 된 마타가 속보를 전해요.",
     [("속보 자막이 빨갛게 깜빡인다", "[속보] 퇴근 5분 전 업무 요청 포착"), ("시계가 17:55를 가리킨다", "17시 55분, 메신저 알림이…"),
      ("마타가 '멈춰!' 표지판을 든다", "내일 해도 괜찮아요")]),
    ("우리 일을 광고하라", "심사의 정석", "웅장한 광고", "꼼꼼함은 기본, 친절은 덤", "심사의 정석, 서울세관 심사2국",
     "명품 광고처럼 우아하게 만들었어요. 배경음악에 주목!",
     [("검은 배경에 금빛 펜이 천천히 돈다", "꼼꼼함"), ("서류가 한 장씩 날아와 정렬된다", "정확함"), ("팀원들이 나란히 서서 미소 짓는다", "그리고 우리")]),
    ("숫자로 보는 2026 심사2국", "커피로 보는 우리 국", "인포그래픽", "우리 국을 움직이는 건 커피다", "오늘도 한 잔, 내일도 한 잔",
     "한 해 동안 마신 커피를 다 쌓으면 어디까지 갈까요?",
     [("커피잔 아이콘이 하나씩 늘어난다", "1월부터 지금까지"), ("커피잔 탑이 구름을 뚫는다", "쌓으면 구름보다 높다"), ("마타가 빈 잔을 들고 윙크", "오늘도 수고했어요")]),
]


def rehearsal_roster() -> dict[int, list[str]]:
    """연습 명단: 분임마다 '연습3-1' ~ '연습3-8', 분임 없음은 '연습국장'."""
    r = {g: [f"연습{g}-{i}" for i in range(1, 9)] for g in range(1, N_GROUPS + 1)}
    r[0] = ["연습국장"]
    return r


def rehearsal_info() -> dict:
    """리허설 데이터가 들어 있으면 {"at": …, "roster": 연습 명단을 넣었는지}, 아니면 {}."""
    c = _connect()
    try:
        return _kv_get(c, "rehearsal", {}) or {}
    finally:
        c.close()


def _sample_png(g: int) -> bytes:
    """샘플 영상 파일이 없을 때 쓸 그림(분임 번호)."""
    buf = io.BytesIO()
    try:
        from PIL import Image, ImageDraw, ImageFont
        im = Image.new("RGB", (1280, 720), (14, 35, 80))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 1280, 12], fill=(226, 180, 60))
        try:
            d.text((640, 330), f"#{g}", font=ImageFont.load_default(size=220), fill=(226, 180, 60), anchor="mm")
            d.text((640, 560), "REHEARSAL SAMPLE", font=ImageFont.load_default(size=56), fill=(185, 203, 230), anchor="mm")
        except Exception:
            pass
        im.save(buf, "PNG")
    except Exception:          # Pillow도 없으면 1×1 그림
        buf.write(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c63f8cfc000000301"
                                "0100c9fe92ef0000000049454e44ae426082"))
    return buf.getvalue()


def fill_rehearsal(roster_too: bool = True) -> int:
    """모두 지우고 7개 분임을 연습용으로 채움: 기획서(제출·완성) + 샘플 영상 + (선택) 연습 명단. 설정은 그대로."""
    reset_all()
    has_mp4 = os.path.exists(REHEARSAL_SAMPLE)
    clip = read_bytes(REHEARSAL_SAMPLE) if has_mp4 else None
    now = time.time()
    with _tx() as c:
        for g in range(1, N_GROUPS + 1):
            topic, title, fmt, message, last, pitch, scenes = REHEARSAL_PLANS[(g - 1) % len(REHEARSAL_PLANS)]
            d = blank_request()
            for j, (k, _lab) in enumerate(ROLES):
                d[k] = REHEARSAL_NAMES[((g - 1) * len(ROLES) + j) % len(REHEARSAL_NAMES)]
            d.update(topic=topic, title=title, format=fmt if fmt in FORMATS else FORMATS[0], message=message, last_line=last, pitch=pitch,
                     color="하늘색·남색·금색", character="마타")
            for i, (look, cap) in enumerate(scenes[:len(SCENES)]):
                d["scenes"][i] = {"look": look, "caption": cap, "fx": ""}
            c.execute("UPDATE req SET data=?, status='submitted', submitted_at=?, updated_at=? WHERE g=?",
                      (json.dumps(d, ensure_ascii=False), now, now, g))
    for g in range(1, N_GROUPS + 1):
        if has_mp4:
            add_result(g, f"{g}분임_리허설샘플.mp4", clip, "리허설용 샘플 영상", True)
        else:
            add_result(g, f"{g}분임_리허설샘플.png", _sample_png(g), "리허설용 샘플 그림", True)
    with _tx() as c:
        if roster_too:
            _kv_put(c, "roster", {str(g): v for g, v in rehearsal_roster().items()})
        _kv_put(c, "rehearsal", {"at": now, "roster": bool(roster_too)})
        _kv_put(c, "vote", {"state": "ready", "at": now})
    return N_GROUPS


def simulate_votes(ratio: float = 0.8) -> int:
    """연습용 가짜 표: 아직 투표 안 한 명단의 ratio만큼이 (우리 분임을 뺀) 아무 작품에나 투표. 투표 상태와 상관없이 넣음."""
    import random
    roster = get_roster()
    voted = {name_key(v["name"]) for v in voters()}
    pending = [(n, g) for g, ns in roster.items() for n in ns if name_key(n) not in voted]
    random.shuffle(pending)
    pending = pending[:max(1, round(len(pending) * ratio))] if pending else []
    cands = {g: vote_candidates(g) for g in {vg for _n, vg in pending}}
    weight = {g: random.uniform(1, 6) for g in range(1, N_GROUPS + 1)}      # 분임마다 인기를 달리해서 순위가 갈리게
    n = 0
    with _tx() as c:
        for name, vg in pending:
            if not cands[vg]:
                continue
            pick = random.choices(cands[vg], weights=[weight[g] for g in cands[vg]])[0]
            cur = c.execute("INSERT OR IGNORE INTO vote(k, name, voter_g, g, at) VALUES (?,?,?,?,?)",
                            (name_key(name), name, vg, pick, time.time()))
            n += cur.rowcount
    return n

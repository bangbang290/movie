"""워크숍 모션 영상 의뢰 (Streamlit) — 주소 하나로 세 화면.

  /                 분임 화면(휴대폰): 분임 고르기 → 비밀번호(처음엔 분임이 직접 만듦) → 기획서 쓰기·제출 → 결과물 보기·수정 요청
  /?g=3             분임 QR 카드로 바로 들어오는 주소(그 분임 비밀번호 화면)
  /?view=admin      관리팀(노트북, PIN): 진행 현황 · Claude 요청문 복사 · 결과물 올리기 · 비밀번호 초기화/QR · 백업
  /?view=screen     스크린(프로젝터): 관리팀이 고른 결과물을 크게 틀기
"""
from __future__ import annotations

import html
import time

import streamlit as st

import store

st.set_page_config(page_title="워크숍 영상 의뢰", page_icon="🎬", layout="centered", initial_sidebar_state="collapsed")
store.init()

ESC = html.escape
BADGE = {"draft": ("작성 중", "#8a7a62", "#efe6cf"), "submitted": ("접수 완료", "#1f3f8f", "#dfe7fb"),
         "making": ("제작 중", "#b4560f", "#fbe7d2"), "done": ("완성", "#1f7a3c", "#dcf2e1"),
         "revise": ("수정 요청", "#b3261e", "#fbdedb")}

BASE_CSS = """<style>
@import url("https://fonts.googleapis.com/css2?family=Gowun+Dodum&family=Yeon+Sung&display=swap");
header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],#MainMenu,footer{display:none!important}
[data-stale="true"],.stale-element{opacity:1!important;transition:none!important}
.stApp{background:linear-gradient(180deg,#d6ecdf 0%,#f4e7c6 60%,#f4e7c6 100%)}
.block-container{max-width:760px!important;padding-top:1rem!important;padding-bottom:4rem!important}
.stApp,.stMarkdown,.stTextInput,.stTextArea,.stRadio,.stSelectbox{font-family:"Gowun Dodum","Malgun Gothic","Apple SD Gothic Neo",sans-serif}
.mx{font-family:"Gowun Dodum","Malgun Gothic","Apple SD Gothic Neo",sans-serif;color:#2b2218}
.mx-card{background:#fffaf0;border:2.5px solid #2b2218;border-radius:14px;box-shadow:3px 3px 0 #2b2218;padding:.9rem 1rem;margin:.2rem 0 .8rem}
.mx-top{display:flex;align-items:center;gap:.7rem;flex-wrap:wrap}
.mx-ev{font-size:.95rem;color:#6a5a45}
.mx-h1{font-family:"Yeon Sung","Malgun Gothic",sans-serif;font-size:2.1rem;line-height:1.1;margin:.1rem 0}
.mx-badge{display:inline-block;font-family:"Yeon Sung",sans-serif;font-size:1.15rem;padding:.05rem .75rem;border-radius:999px;border:2px solid currentColor;white-space:nowrap}
.mx-steps{display:flex;gap:.3rem;margin:.7rem 0 .1rem;flex-wrap:wrap}
.mx-steps span{flex:1 1 0;min-width:4.6rem;text-align:center;font-size:.85rem;padding:.35rem .2rem;border-radius:9px;background:#efe6cf;color:#8a7a62;border:1.5px solid transparent}
.mx-steps span.on{background:#2b2218;color:#fffaf0}
.mx-steps span.ok{background:#e9dfc4;color:#2b2218}
.mx-note{font-size:.95rem;color:#5b4c39;line-height:1.55}
.mx-sec{font-family:"Yeon Sung","Malgun Gothic",sans-serif;font-size:1.45rem;margin:1.2rem 0 .3rem;display:flex;align-items:center;gap:.45rem}
.mx-sec i{font-style:normal;display:inline-grid;place-items:center;width:1.7rem;height:1.7rem;border-radius:50%;background:#cf4430;color:#fff;font-size:1.05rem}
.mx-warn{font-size:.92rem;line-height:1.5;padding:.6rem .8rem;border-radius:10px;background:#fff3e8;border:1.5px dashed #cf4430;margin:.3rem 0 .6rem}
.mx-sum{font-size:.98rem;line-height:1.6}
.mx-sum b{font-family:"Yeon Sung",sans-serif;font-weight:400;font-size:1.08rem}
.mx-sum .sc{border-top:1px dashed #cdbf9e;padding:.45rem 0}
.mx-chat{display:flex;flex-direction:column;gap:.45rem;margin:.3rem 0 .8rem}
.mx-chat div{max-width:86%;padding:.5rem .75rem;border-radius:14px;font-size:.98rem;line-height:1.5;border:2px solid #2b2218;white-space:pre-wrap;word-break:keep-all}
.mx-chat .me{align-self:flex-end;background:#fffaf0;border-bottom-right-radius:4px}
.mx-chat .them{align-self:flex-start;background:#dfe7fb;border-bottom-left-radius:4px}
.mx-chat small{display:block;font-size:.75rem;color:#7a6a55;margin-top:.15rem}
div[data-testid="stButton"] button,div[data-testid="stFormSubmitButton"] button,div[data-testid="stDownloadButton"] button{border-radius:12px!important;border:2.5px solid #2b2218!important;box-shadow:0 3px 0 #2b2218;min-height:2.9rem;background:#fffaf0;color:#2b2218}
div[data-testid="stButton"] button p,div[data-testid="stFormSubmitButton"] button p,div[data-testid="stDownloadButton"] button p{font-size:1.08rem}
div[data-testid="stButton"] button[kind="primary"],div[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]{background:#cf4430;color:#fff}
div[data-testid="stButton"] button:active{transform:translateY(2px);box-shadow:0 1px 0 #2b2218}
div[class*="st-key-row_"] [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:.4rem!important}
div[class*="st-key-row_"] [data-testid="stColumn"]{min-width:0!important}
div[class*="st-key-row_"] button{min-height:2.4rem!important;padding:0 .4rem!important}
div[class*="st-key-scene_"]{background:#fffaf0;border-radius:12px}
[data-testid="stExpander"] details{background:#fffaf0;border:2px solid #2b2218;border-radius:12px}
</style>"""

ADMIN_CSS = """<style>
.block-container{max-width:1200px!important}
.mx-tbl{width:100%;border-collapse:collapse;font-size:.98rem;background:#fffaf0;border:2.5px solid #2b2218;border-radius:12px;overflow:hidden}
.mx-tbl th,.mx-tbl td{padding:.5rem .6rem;border-bottom:1px solid #e3d7b8;text-align:left;vertical-align:middle}
.mx-tbl th{background:#2b2218;color:#fffaf0;font-weight:400;font-family:"Yeon Sung",sans-serif;font-size:1.05rem}
.mx-tbl .new{color:#fff;background:#cf4430;border-radius:999px;padding:0 .5rem;font-size:.85rem}
</style>"""

SCREEN_CSS = """<style>
@import url("https://fonts.googleapis.com/css2?family=Gowun+Dodum&family=Nanum+Brush+Script&family=Yeon+Sung&display=swap");
header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],#MainMenu,footer{display:none!important}
[data-stale="true"],.stale-element{opacity:1!important;transition:none!important}
.stApp{background:#0e0b08}
.block-container{max-width:100%!important;padding:1.2vh 2.2vw 0!important}
.sc-head{display:flex;align-items:baseline;gap:1.2vw;color:#f4e7c6;font-family:"Yeon Sung",sans-serif;margin:0 0 1vh}
.sc-head b{font-weight:400;font-size:clamp(1.6rem,3vw,3rem)}
.sc-head span{font-size:clamp(1rem,1.6vw,1.6rem);color:#c9b892}
[data-testid="stVideo"] video,.stVideo video{width:100%!important;max-height:86vh;background:#000;border-radius:10px}
[data-testid="stImage"] img{max-height:86vh;object-fit:contain}
.sc-board{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(24vw,340px),1fr));gap:1.4vw;margin-top:2vh}
.sc-card{background:#fffaf0;border:3px solid #2b2218;border-radius:16px;box-shadow:5px 5px 0 #000;padding:1.4vw 1.6vw;font-family:"Gowun Dodum",sans-serif;color:#2b2218}
.sc-card .n{font-family:"Yeon Sung",sans-serif;font-size:clamp(1.4rem,2.4vw,2.6rem)}
.sc-card .t{font-size:clamp(1rem,1.3vw,1.4rem);margin-top:.4vh;min-height:1.5em}
.sc-title{font-family:"Nanum Brush Script",serif;color:#f4e7c6;font-size:clamp(3rem,7vw,7rem);line-height:1;text-align:center;margin-top:4vh}
.sc-sub{font-family:"Yeon Sung",sans-serif;color:#c9b892;text-align:center;font-size:clamp(1.2rem,2vw,2rem)}
.mx-badge{display:inline-block;font-family:"Yeon Sung",sans-serif;font-size:clamp(.9rem,1.1vw,1.2rem);padding:.05rem .7rem;border-radius:999px;border:2px solid currentColor;white-space:nowrap;vertical-align:middle}
</style>"""


def md(h: str):
    st.markdown(h, unsafe_allow_html=True)


def kst(ts: float | None, fmt: str = "%m/%d %H:%M") -> str:
    if not ts:
        return ""
    return time.strftime(fmt, time.gmtime(ts + 9 * 3600))


def secret(name: str):
    try:
        if name in st.secrets:
            v = str(st.secrets[name]).strip()
            return v or None
    except Exception:
        pass
    return None


def admin_pin() -> str:
    return secret("admin_pin") or "0000"


def base_url() -> str:
    S = store.get_settings()
    if S["public_url"]:
        return S["public_url"].rstrip("/")
    try:
        h = {k.lower(): v for k, v in st.context.headers.items()}
        host = h.get("x-forwarded-host") or h.get("host") or ""
        if host:
            proto = h.get("x-forwarded-proto") or ("https" if "streamlit.app" in host else "http")
            return f"{proto}://{host}"
    except Exception:
        pass
    return ""


def badge(status: str) -> str:
    t, fg, bg = BADGE.get(status, BADGE["draft"])
    return f'<span class="mx-badge" style="color:{fg};background:{bg}">{t}</span>'


def act(fn, *a) -> bool:
    try:
        fn(*a)
        return True
    except store.StoreError as e:
        st.error(str(e))
        return False


def size_txt(n: int) -> str:
    return f"{n / 1048576:.1f}MB" if n >= 1048576 else f"{max(1, n // 1024)}KB"


def confirm_button(label, key, warn):
    """두 번 눌러야 실행되는 버튼."""
    if st.session_state.get(f"cf_{key}"):      # 칸(columns) 안에서도 쓰므로 버튼은 위아래로
        st.warning(warn)
        ok = st.button("실행", key=f"{key}_ok", type="primary", use_container_width=True)
        if st.button("취소", key=f"{key}_no", use_container_width=True):
            st.session_state.pop(f"cf_{key}", None)
            st.rerun()
        if ok:
            st.session_state.pop(f"cf_{key}", None)
        return ok
    if st.button(label, key=key, use_container_width=True):
        st.session_state[f"cf_{key}"] = True
        st.rerun()
    return False


# ───────────────────────── 기획서 내용 보기(읽기 전용)
def summary_html(d: dict, atts: list[dict]) -> str:
    def row(k, v):
        v = str(v).strip()
        return f"<div><b>{k}</b> · {ESC(v)}</div>" if v else ""
    roles = " · ".join(f"{lab} {d[k]}" for k, lab in store.ROLES if d[k].strip())
    h = [row("역할", roles), row("주제", d["topic"]), row("영상 제목", d["title"]), row("핵심 메시지", d["message"]),
         row("마지막 문구", d["last_line"]), row("색감·분위기", d["color"]), row("등장 캐릭터", d["character"]),
         row("영상 형식", store.format_text(d))]
    h.append('<div style="margin-top:.4rem"><b>장면 구성</b> · 30초</div>')
    for i, sc in enumerate(d["scenes"]):
        name, sec = store.SCENES[i]
        if not (sc["look"].strip() or sc["caption"].strip() or sc["fx"].strip()):
            continue
        h.append(f'<div class="sc">{name} ({sec})<br>· 화면: {ESC(sc["look"]) or "-"}<br>· 자막: {ESC(sc["caption"]) or "-"}'
                 + (f'<br>· 효과: {ESC(sc["fx"])}' if sc["fx"].strip() else "") + "</div>")
    h += [row("첨부", ", ".join(a["name"] for a in atts)), row("발표 한마디", d["pitch"])]
    return '<div class="mx mx-card mx-sum">' + "".join(h) + "</div>"


def chat_html(msgs: list[dict], me: str) -> str:
    if not msgs:
        return '<div class="mx mx-note">아직 주고받은 글이 없어요.</div>'
    out = []
    for m in msgs:
        who = "me" if m["who"] == me else "them"
        name = "관리팀" if m["who"] == "admin" else "분임"
        tag = "<b>✂ 수정 요청</b><br>" if m.get("kind") == "rev" else ""
        out.append(f'<div class="{who}">{tag}{ESC(m["text"])}<small>{name} · {kst(m["at"])}</small></div>')
    return '<div class="mx mx-chat">' + "".join(out) + "</div>"


def show_result(r: dict, key: str, big: bool = True):
    if r["video"]:
        st.video(r["path"], format="video/" + ("quicktime" if r["ext"] == "mov" else r["ext"]))
    else:
        st.image(r["path"], use_container_width=True)
    note = f' · {ESC(r["note"])}' if r["note"] else ""
    md(f'<div class="mx mx-note">{kst(r["at"])} 올림{note} · {size_txt(r["size"])}</div>')
    if big:
        st.download_button("⬇ 내려받기", store.read_bytes(r["path"]), file_name=r["name"], key=f"dl_{key}_{r['id']}", use_container_width=True)


# ───────────────────────── 첫 화면: 분임 고르기
def home_view():
    md(BASE_CSS)
    S = store.get_settings()
    md(f'<div class="mx mx-card"><div class="mx-ev">{ESC(S["event"])}</div><div class="mx-h1">🎬 모션 영상 의뢰</div>'
       f'<div class="mx-note">분임별로 영상 기획서를 쓰고, 완성된 영상을 여기서 바로 봅니다.<br>분임 QR 카드를 찍으면 우리 분임 비밀번호 화면이 바로 열려요.</div></div>')
    pick = st.session_state.get("pick")
    if not pick:
        md('<div class="mx mx-sec">우리 분임 고르기</div>')
        for row in range(0, store.N_GROUPS, 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                g = row + j + 1
                if g <= store.N_GROUPS and col.button(S["names"][g - 1], key=f"pick_{g}", use_container_width=True):
                    st.session_state["pick"] = g
                    st.rerun()
        return
    name = ESC(S["names"][pick - 1])
    if store.has_password(pick):
        md(f'<div class="mx mx-sec">{name} 비밀번호 넣기</div>')
        with st.form("login"):
            pw = st.text_input(f"우리 분임 비밀번호 (숫자 {store.PW_LEN}자리)", type="password", max_chars=store.PW_LEN)
            ok = st.form_submit_button("들어가기", type="primary", use_container_width=True)
        md('<div class="mx mx-note">비밀번호는 우리 분임에서 처음 들어온 분이 만들었어요. 모르면 분임원에게 물어보고, '
           '잊어버렸으면 관리팀에 <b>초기화</b>를 부탁하세요.</div>')
        if ok:
            try:
                enter(pick, store.login(pick, pw))
            except store.StoreError as e:
                st.error(str(e))
    else:
        md(f'<div class="mx mx-sec">{name} 비밀번호 만들기</div>')
        md(f'<div class="mx mx-warn">🔑 <b>{name}</b>에 처음 들어오셨어요. 우리 분임만 쓸 <b>비밀번호(숫자 {store.PW_LEN}자리)</b>를 만들어 주세요.<br>'
           '· 분임원끼리만 알려 주세요. 다른 휴대폰에서 들어올 때 필요해요.<br>· 평소 쓰는 비밀번호(은행·휴대폰 등)는 쓰지 마세요.<br>'
           f'· <b>{name}</b>이 맞는지 꼭 확인해 주세요.</div>')
        with st.form("make_pw"):
            pw = st.text_input(f"새 비밀번호 (숫자 {store.PW_LEN}자리)", type="password", max_chars=store.PW_LEN)
            pw2 = st.text_input("한 번 더 넣기", type="password", max_chars=store.PW_LEN)
            ok = st.form_submit_button("만들고 들어가기", type="primary", use_container_width=True)
        if ok:
            try:
                enter(pick, store.set_password(pick, pw, pw2))
            except store.StoreError as e:
                st.error(str(e))
    if st.button("← 다른 분임 고르기"):
        st.session_state.pop("pick", None)
        st.query_params.clear()
        st.rerun()


def enter(g: int, tok: str):
    """로그인: 주소에 분임 번호와 로그인 표(k)를 붙여 새로 고침해도 그대로 들어와 있게."""
    st.session_state.update({"g": g, "tok": tok})
    st.session_state.pop("pick", None)
    st.query_params.update({"g": str(g), "k": tok})
    st.rerun()


def leave():
    for k in ("g", "tok", "pick"):
        st.session_state.pop(k, None)
    st.query_params.clear()


# ───────────────────────── 분임 화면
STEPS = ["① 기획서 쓰기", "② 제출", "③ 제작 중", "④ 완성"]
STEP_AT = {"draft": 0, "submitted": 1, "making": 2, "revise": 2, "done": 3}


def group_header(g: int, R: dict, S: dict):
    at = STEP_AT[R["status"]]
    steps = "".join(f'<span class="{"on" if i == at else "ok" if i < at else ""}">{t}</span>' for i, t in enumerate(STEPS))
    what = {"draft": "기획서를 쓰고 맨 아래 [제출하기]를 눌러 주세요.",
            "submitted": "접수됐어요! 제작이 시작되기 전까지는 기획서를 더 고칠 수 있어요.",
            "making": "관리팀이 영상을 만들고 있어요. 완성되면 [결과물]에 올라와요.",
            "revise": "수정 요청을 받았어요. 고친 영상이 [결과물]에 올라올 거예요.",
            "done": "영상이 완성됐어요! [결과물]에서 보고, 고칠 곳은 [수정 요청]에 남겨 주세요."}[R["status"]]
    md(f'<div class="mx mx-card"><div class="mx-top"><div style="flex:1;min-width:0"><div class="mx-ev">{ESC(S["event"])} · 모션 영상 의뢰</div>'
       f'<div class="mx-h1">{ESC(S["names"][g - 1])}</div></div>{badge(R["status"])}</div>'
       f'<div class="mx-steps">{steps}</div><div class="mx-note" style="margin-top:.5rem">{what}</div></div>')


def group_view(g: int):
    md(BASE_CSS)
    S = store.get_settings()
    R = store.get_request(g)
    group_header(g, R, S)
    if S["notice"].strip():
        md(f'<div class="mx mx-note" style="margin:-.2rem 0 .6rem">📢 {ESC(S["notice"])}</div>')
    res = store.results(g)
    names = ["🎬 결과물", "📝 기획서", "💬 수정 요청·문의"] if res else ["📝 기획서", "🎬 결과물", "💬 수정 요청·문의"]
    tabs = dict(zip(names, st.tabs(names)))
    with tabs["📝 기획서"]:
        form_area(g)
    with tabs["🎬 결과물"]:
        results_area(g, res)
    with tabs["💬 수정 요청·문의"]:
        chat_area(g)
    watch_group(g)
    md('<div style="height:1.4rem"></div>')
    if st.button("다른 분임으로 바꾸기", key="logout"):
        leave()
        st.rerun()


def watch_group(g: int):
    """관리팀이 상태를 바꾸거나 결과물·답장을 올리면 화면을 새로 그림."""
    def token():
        R = store.get_request(g)
        return (R["status"], len(store.results(g)), len(store.messages(g)), store.session_token(g))
    st.session_state[f"tok_{g}"] = token()

    @st.fragment(run_every=8)
    def w():
        if token() != st.session_state.get(f"tok_{g}"):
            st.rerun()
    w()


# 기획서: 쓰는 대로 저장(칸마다). 칸 이름 앞에 '판 번호(ep)'를 붙여, [다른 휴대폰에서 쓴 내용 불러오기]를 누르면 새 칸으로 다시 불러옴.
def _ep(g):
    return st.session_state.setdefault(f"ep_{g}", 0)


def _bump(g):
    st.session_state[f"ep_{g}"] = _ep(g) + 1


def _key(g, name):
    return f"f{g}_{_ep(g)}_{name}"


def _cb_field(g, field, key):
    try:
        store.set_field(g, field, st.session_state[key])
    except store.StoreError as e:
        st.session_state["_err"] = str(e)


def _cb_scene(g, i, part, key):
    try:
        store.set_scene(g, i, part, st.session_state[key])
    except store.StoreError as e:
        st.session_state["_err"] = str(e)


def _cb_upload(g, key, ckey):
    files = st.session_state.get(key) or []
    for f in files:
        try:
            store.add_attachment(g, f.name, f.getvalue())
        except store.StoreError as e:
            st.session_state["_err"] = str(e)
    st.session_state[ckey] = st.session_state.get(ckey, 0) + 1   # 올리기 칸 비우기


def w_text(g, d, field, label, area=False, **kw):
    k = _key(g, field)
    if k not in st.session_state:
        st.session_state[k] = d[field]
    fn = st.text_area if area else st.text_input
    fn(label, key=k, on_change=_cb_field, args=(g, field, k), **kw)


def w_radio(g, d, field, label, options, **kw):
    k = _key(g, field)
    if k not in st.session_state:
        st.session_state[k] = d[field] if d[field] in options else options[0]
    st.radio(label, options, key=k, on_change=_cb_field, args=(g, field, k), **kw)


@st.fragment
def form_area(g: int):
    R = store.get_request(g)
    d = R["data"]
    err = st.session_state.pop("_err", None)
    if err:
        st.error(err)
    if R["status"] not in store.EDITABLE:
        md('<div class="mx mx-warn">제작이 시작돼서 기획서는 더 고칠 수 없어요. 고칠 곳은 <b>[수정 요청·문의]</b>에 장면 번호로 남겨 주세요.</div>')
        md(summary_html(d, store.attachments(g)))
        return
    md('<div class="mx mx-warn">✏️ <b>★ 칸만 채우면 돼요.</b> 쓰는 대로 저장돼요(칸을 벗어나면 저장). 한 분임에서 한 사람이 대표로 써 주세요.<br>'
       '🔒 외부 서버라서 업무 문서·보고서 같은 <b>내부자료는 적거나 올리지 마세요.</b></div>')

    md('<div class="mx mx-sec"><i>1</i>우리 분임</div>')
    cols = st.columns(2)
    for j, (field, label) in enumerate(store.ROLES):
        with cols[j % 2]:
            w_text(g, d, field, label, max_chars=20, placeholder="이름")

    md('<div class="mx mx-sec"><i>2</i>무엇을 만들까요</div>')
    w_text(g, d, "topic", "★ 주제", placeholder="예: 작년과 올해 워크숍 비교", max_chars=60)
    w_text(g, d, "title", "영상 제목", placeholder="예: 마타의 작년 vs 올해", max_chars=40)
    w_text(g, d, "message", "★ 핵심 메시지 (한 문장)", area=True, height=70, max_chars=150,
           placeholder="예: 작년엔 영상 하나에 2시간, 올해는 두 문장이면 끝")
    w_text(g, d, "last_line", "★ 마지막 문구 (끝 화면 한 줄)", placeholder="예: 2026 서울세관 심사2국 워크숍, 지금 시작합니다", max_chars=60)
    w_text(g, d, "color", "색감·분위기", placeholder="예: 작년은 회색, 올해는 하늘색·남색·금색", max_chars=80)
    w_text(g, d, "character", "등장 캐릭터", placeholder="예: 마타 (골든리트리버)", max_chars=60,
           help="캐릭터 그림이 있으면 아래 [캐릭터·로고 그림]에 올려 주세요. 그 캐릭터가 주인공이 돼요.")
    w_radio(g, d, "format", "★ 영상 형식", store.FORMATS, horizontal=True)
    if st.session_state.get(_key(g, "format")) == "기타":
        w_text(g, d, "format_etc", "영상 형식 직접 쓰기", max_chars=30)
    md('<div class="mx mx-note" style="margin-top:.4rem">캐릭터·로고 그림 (선택) · <b>쓰여도 되는 그림</b>만 올려 주세요.</div>')
    ck = f"upc_{g}"
    uk = f"up_{g}_{st.session_state.get(ck, 0)}"
    st.file_uploader("캐릭터·로고 그림 올리기", type=store.ATT_TYPES, accept_multiple_files=True, key=uk, on_change=_cb_upload, args=(g, uk, ck),
                     label_visibility="collapsed")
    for a in store.attachments(g):
        with st.container(key=f"row_att_{a['id']}"):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f'<div class="mx mx-note">📎 {ESC(a["name"])} · {size_txt(a["size"])}</div>', unsafe_allow_html=True)
            if c2.button("🗑", key=f"att_rm_{a['id']}", help="지우기"):
                store.del_attachment(g, a["id"])
                st.rerun(scope="fragment")

    md('<div class="mx mx-sec"><i>3</i>장면 구성 <span style="font-size:1rem;color:#6a5a45">30초 · 3~4장면</span></div>')
    md('<div class="mx mx-note">효과는 "유리처럼 깨지며", "도장이 쾅"처럼 말로 적으면 돼요. ④는 비워도 돼요.</div>')
    for i, sc in enumerate(d["scenes"]):
        name, sec = store.SCENES[i]
        with st.container(border=True, key=f"scene_{g}_{_ep(g)}_{i}"):
            md(f'<div class="mx mx-sec" style="margin:.1rem 0 .2rem">{name} <span style="font-size:1rem;color:#6a5a45">{sec}</span></div>')
            for part, label, kind, kw in (
                    ("look", "★ 화면에 보일 것", "area", {"height": 70, "max_chars": 300, "placeholder": "예: 마타가 \"크레딧 부족\" 에러창에 파묻힘"}),
                    ("caption", "★ 자막·문구", "text", {"max_chars": 80, "placeholder": "예: 작년, 영상 하나에 2시간"}),
                    ("fx", "효과 (선택)", "text", {"max_chars": 80, "placeholder": "예: 오래된 비디오 느낌"})):
                k = f"{_key(g, 'sc')}{i}_{part}"
                if k not in st.session_state:
                    st.session_state[k] = sc[part]
                fn = st.text_area if kind == "area" else st.text_input
                fn(label, key=k, on_change=_cb_scene, args=(g, i, part, k), **kw)

    md('<div class="mx mx-sec"><i>4</i>발표 준비</div>')
    w_text(g, d, "pitch", "발표 한마디 (기획 의도·관전 포인트)", area=True, height=80, max_chars=300)
    md(f'<div class="mx mx-note">수정 요청은 영상이 나온 뒤 <b>[수정 요청·문의]</b>에서 최대 {store.MAX_REV}번 보낼 수 있어요.</div>')

    md('<div style="height:.6rem"></div>')
    if st.button("🔄 다른 휴대폰에서 쓴 내용 불러오기", key=f"reload_{g}", use_container_width=True):
        _bump(g)
        st.rerun(scope="fragment")
    miss = store.missing(store.get_request(g)["data"])
    if R["status"] == "submitted":
        md('<div class="mx mx-warn" style="border-style:solid;border-color:#1f3f8f;background:#eef3ff">✅ 제출 완료! 제작이 시작되기 전까지 고치는 내용도 자동으로 관리팀에 보여요.</div>')
        return
    if miss:
        md(f'<div class="mx mx-note">제출하려면 이 칸을 채워 주세요: <b>{", ".join(miss)}</b></div>')
    if st.button("📮 제출하기", key=f"submit_{g}", type="primary", use_container_width=True, disabled=bool(miss)):
        if act(store.submit, g):
            st.rerun()


def results_area(g: int, res: list[dict]):
    if not res:
        R = store.get_request(g)
        md('<div class="mx mx-card mx-note">아직 결과물이 없어요. ' +
           ("기획서를 제출하면 관리팀이 만들기 시작해요." if R["status"] == "draft" else "완성되면 여기에 바로 올라와요.") + "</div>")
        return
    md('<div class="mx mx-warn">결과물은 <b>행사 동안만</b> 보관돼요. 필요하면 꼭 내려받아 두세요.</div>')
    latest = res[0]
    md(f'<div class="mx mx-sec">가장 최근 결과물</div>')
    show_result(latest, "g")
    if len(res) > 1:
        with st.expander(f"이전 결과물 {len(res) - 1}개"):
            for r in res[1:]:
                md(f'<div class="mx mx-note"><b>{ESC(r["name"])}</b></div>')
                show_result(r, "gold")


def chat_area(g: int):
    has_res = bool(store.results(g))
    left = store.MAX_REV - store.rev_count(g)
    md('<div class="mx mx-note">영상을 고칠 곳은 <b>장면 번호</b>로 적어 주세요. 예: "③ 자막을 더 크게", "② 장면을 더 밝게". '
       f'전체를 다시 만들지 않고 그 부분만 고쳐요. 수정 요청은 <b>최대 {store.MAX_REV}번</b>이에요.</div>')
    md(chat_html(store.messages(g), "group"))
    flash = st.session_state.pop(f"_sent_{g}", None)
    if flash:
        st.success(flash)
    with st.form(f"msg_{g}", clear_on_submit=True):
        t = st.text_area("보낼 내용", height=90, max_chars=1000, label_visibility="collapsed",
                         placeholder="수정 요청이나 궁금한 점을 적어 주세요")
        c1, c2 = st.columns(2)
        rev = c1.form_submit_button(f"✂ 수정 요청 보내기 (남은 {max(0, left)}번)", type="primary", use_container_width=True,
                                    disabled=not has_res or left <= 0)
        ask = c2.form_submit_button("💬 문의 보내기", use_container_width=True)
    if not has_res:
        st.caption("수정 요청은 완성 영상이 올라온 뒤에 보낼 수 있어요. 궁금한 점은 [문의 보내기]로 물어보세요.")
    if rev or ask:
        if act(store.add_message, g, "group", t, "rev" if rev else "q"):
            st.session_state[f"_sent_{g}"] = "수정 요청을 보냈어요. 고친 영상이 [결과물]에 올라올 거예요." if rev else "보냈어요!"
            st.rerun()


# ───────────────────────── 관리팀 화면
def admin_view():
    md(BASE_CSS + ADMIN_CSS)
    if not st.session_state.get("admin_ok"):
        md('<div class="mx mx-card"><div class="mx-h1">관리팀</div><div class="mx-note">모션 영상 의뢰 관리 화면입니다.</div></div>')
        with st.form("pin"):
            pin = st.text_input("관리자 PIN", type="password")
            if st.form_submit_button("들어가기", type="primary"):
                if pin.strip() == admin_pin():
                    st.session_state["admin_ok"] = True
                    st.rerun()
                st.error("PIN이 맞지 않습니다.")
        return
    S = store.get_settings()
    md(f'<div class="mx mx-h1">{ESC(S["event"])} · 영상 의뢰 관리</div>')
    if not secret("admin_pin"):
        st.error("Streamlit 설정(Secrets)에 admin_pin 이 없어서 관리 화면 PIN이 임시로 0000입니다. "
                 "배포 화면의 Settings → Secrets에 admin_pin = \"7391\" 처럼 관리팀만 아는 숫자를 넣어 주세요.")
    tabs = st.tabs(["📋 진행 현황", "🔑 분임 비밀번호·QR", "⚙️ 설정", "💾 백업·초기화"])
    with tabs[0]:
        overview()
        md("<hr>")
        detail()
    with tabs[1]:
        pw_panel()
    with tabs[2]:
        settings_panel()
    with tabs[3]:
        backup_panel()


@st.fragment(run_every=10)
def overview():
    S = store.get_settings()
    rows = []
    for R in store.all_requests():
        g, d = R["g"], R["data"]
        nres, new = len(store.results(g)), store.unseen(g)
        rows.append(f'<tr><td><b>{ESC(S["names"][g - 1])}</b></td><td>{ESC(d["title"] or d["topic"]) or "<span style=color:#9a8a72>(아직 없음)</span>"}</td>'
                    f'<td>{badge(R["status"])}</td><td>{len(store.filled_scenes(d))}장면</td><td>{nres}개 · 수정 {store.rev_count(g)}/{store.MAX_REV}</td>'
                    f'<td>{f"<span class=new>새 글 {new}</span>" if new else ""}</td><td>{kst(R["updated_at"])}</td></tr>')
    md('<table class="mx mx-tbl"><tr><th>분임</th><th>영상 제목</th><th>상태</th><th>장면</th><th>결과물·수정</th><th>새 글</th><th>마지막 변경</th></tr>'
       + "".join(rows) + "</table>")
    st.caption(f"10초마다 자동으로 새로 고칩니다 · {kst(time.time(), '%H:%M:%S')} 기준")


def detail():
    S = store.get_settings()
    labels = [f"{S['names'][g - 1]}" + (" ●" if store.unseen(g) else "") for g in range(1, store.N_GROUPS + 1)]
    sel = st.radio("분임 고르기", list(range(1, store.N_GROUPS + 1)), format_func=lambda g: labels[g - 1], horizontal=True, key="ad_g")
    g = int(sel)
    R = store.get_request(g)
    d = R["data"]
    md(f'<div class="mx mx-top" style="margin:.4rem 0"><div class="mx-h1" style="font-size:1.8rem">{ESC(S["names"][g - 1])}</div>{badge(R["status"])}'
       f'<div class="mx-note">제출 {kst(R["submitted_at"]) or "-"} · 마지막 변경 {kst(R["updated_at"])}</div></div>')
    with st.container(key=f"row_st_{g}"):
        c1, c2, c3 = st.columns(3)
        if c1.button("🎬 제작 시작", key=f"st_make_{g}", use_container_width=True, disabled=R["status"] in ("draft", "making")):
            store.set_status(g, "making")
            st.rerun()
        if c2.button("✅ 완성으로 표시", key=f"st_done_{g}", use_container_width=True, disabled=R["status"] == "done" or not store.results(g)):
            store.set_status(g, "done")
            st.rerun()
        if c3.button("↩ 분임이 다시 고치게", key=f"st_back_{g}", use_container_width=True, disabled=R["status"] == "draft",
                     help="기획서 잠금을 풀고 '작성 중'으로 돌립니다"):
            store.set_status(g, "draft")
            st.rerun()
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        md('<div class="mx mx-sec">Claude에게 보낼 요청문 <span style="font-size:1rem;color:#6a5a45">(부스 프롬프트 틀)</span></div>')
        if R["status"] == "draft":
            md('<div class="mx mx-note">아직 제출 전입니다(작성 중인 내용).</div>')
        md('<div class="mx mx-note">오른쪽 위 복사 버튼 → 새 Claude 대화창에 붙여 넣기. 아래 첨부 자료도 같이 올려 주세요.</div>')
        st.code(store.prompt_text(g, S), language=None, wrap_lines=True)
        rv = store.revision_text(g, S)
        if rv and store.results(g):
            md(f'<div class="mx mx-sec">수정 요청문 <span style="font-size:1rem;color:#6a5a45">(만들었던 대화창에 이어서 · {store.rev_count(g)}/{store.MAX_REV}번째)</span></div>')
            st.code(rv, language=None, wrap_lines=True)
        atts = store.attachments(g)
        md('<div class="mx mx-sec">분임이 올린 캐릭터·로고 그림</div>')
        if not atts:
            md('<div class="mx mx-note">없음</div>')
        for a in atts:
            st.download_button(f"📎 {a['name']} ({size_txt(a['size'])})", store.read_bytes(a["path"]), file_name=a["name"],
                               key=f"ad_att_{a['id']}", use_container_width=True)
        with st.expander("기획서 보기 (사람이 읽기 좋게)"):
            md(summary_html(d, atts))
    with right:
        md('<div class="mx mx-sec">결과물 올리기</div>')
        with st.form(f"up_res_{g}", clear_on_submit=True):
            f = st.file_uploader("영상(mp4) 또는 그림", type=store.RES_TYPES)
            note = st.text_input("메모 (분임에게 보임)", placeholder="예: 1차 완성본, 2번 장면 수정본")
            done = st.checkbox("올리면서 '완성'으로 표시 (분임 화면에 바로 뜸)", value=True)
            ok = st.form_submit_button("⬆ 올리기", type="primary", use_container_width=True)
        if ok:
            if not f:
                st.error("파일을 골라 주세요.")
            elif act(store.add_result, g, f.name, f.getvalue(), note, done):
                st.success(f"올렸습니다: {f.name}")
                st.rerun()
        res = store.results(g)
        scr = store.screen_get().get("rid")
        for r in res:
            with st.container(border=True):
                md(f'<div class="mx mx-note"><b>{ESC(r["name"])}</b> · {kst(r["at"])} · {size_txt(r["size"])}'
                   + (f' · {ESC(r["note"])}' if r["note"] else "") + (' · <b style="color:#cf4430">스크린에 나오는 중</b>' if scr == r["id"] else "") + "</div>")
                with st.container(key=f"row_res_{r['id']}"):
                    c1, c2 = st.columns(2)
                    if scr == r["id"]:
                        if c1.button("⏹ 스크린 비우기", key=f"scr_off_{r['id']}", use_container_width=True):
                            store.screen_set(None)
                            st.rerun()
                    elif c1.button("📺 스크린에 틀기", key=f"scr_{r['id']}", use_container_width=True):
                        store.screen_set(r["id"])
                        st.rerun()
                    with c2:
                        if confirm_button("🗑 지우기", f"res_rm_{r['id']}", "이 결과물을 지웁니다(분임 화면에서도 사라짐)."):
                            store.del_result(r["id"])
                            st.rerun()
                if st.toggle("미리 보기", key=f"pv_{r['id']}"):
                    show_result(r, "ad", big=False)
        md('<div class="mx mx-sec">수정 요청·문의</div>')
        if store.unseen(g):
            store.mark_seen(g)
        md(chat_html(store.messages(g), "admin"))
        with st.form(f"ad_msg_{g}", clear_on_submit=True):
            t = st.text_area("답장", height=80, max_chars=1000, label_visibility="collapsed", placeholder="분임에게 보낼 답장")
            if st.form_submit_button("답장 보내기", use_container_width=True):
                if act(store.add_message, g, "admin", t):
                    st.rerun()


def qr_cards_html(url: str, S: dict) -> str:
    """인쇄용 분임 QR 카드(A4 한 장에 2장)."""
    import segno
    cards = []
    for g in range(1, store.N_GROUPS + 1):
        link = f"{url}/?g={g}"
        qr = segno.make(link, error="m").svg_data_uri(scale=8, border=2, dark="#000000", light="#ffffff")
        name = ESC(S["names"][g - 1])
        cards.append(f'''<section class="card"><div class="ev">{ESC(S["event"])} · 모션 영상 의뢰</div><div class="nm">{name}</div>
<img class="qr" src="{qr}" alt="QR"><ol><li>휴대폰 <b>카메라</b>로 QR 코드를 비춥니다.</li><li>뜨는 <b>주소</b>를 누르면 우리 분임 화면이 열립니다.</li>
<li><b>처음 들어온 분</b>이 우리 분임 <b>비밀번호(숫자 4자리)</b>를 만들고, 분임원끼리 나눠 씁니다.</li>
<li>기획서를 쓰고 <b>[제출하기]</b>. 완성 영상도 여기서 봅니다.</li></ol>
<div class="ft">직접 들어갈 때: {ESC(url)} → {name} → 비밀번호 · 비밀번호를 잊으면 관리팀에 초기화를 부탁하세요.</div></section>''')
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>분임 QR 카드</title><style>
@page{{size:A4;margin:12mm}}body{{margin:0;font-family:"Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif;color:#111;background:#fff}}
.tip{{padding:10px 14px;margin:0 0 10px;background:#eef3ff;border:1px solid #c9d6f5;border-radius:8px;font-size:14px}}@media print{{.tip{{display:none}}}}
.card{{height:128mm;box-sizing:border-box;border:1.5px dashed #9aa4b8;border-radius:6mm;padding:9mm 12mm;margin:0 0 8mm;display:grid;grid-template-columns:1fr 62mm;
grid-template-rows:auto auto 1fr auto;column-gap:10mm;break-inside:avoid;page-break-inside:avoid}}.card:nth-of-type(2n){{break-after:page;page-break-after:always}}
.ev{{grid-column:1/3;font-size:13pt;color:#3b4a6b;font-weight:700}}.nm{{grid-column:1/2;font-size:34pt;font-weight:800;margin-top:6mm}}
.qr{{grid-column:2/3;grid-row:2/4;width:62mm;height:62mm;align-self:center}}ol{{grid-column:1/2;margin:5mm 0 0;padding-left:6mm;font-size:13pt;line-height:1.6;word-break:keep-all}}
.ft{{grid-column:1/3;font-size:11.5pt;color:#555;border-top:1px solid #dde3ee;padding-top:3mm;margin-top:4mm}}
</style></head><body><div class="tip">이 파일을 연 상태에서 <b>Ctrl + P</b>로 인쇄하세요. 한 장에 두 분임씩 나오고, 점선을 따라 자르면 됩니다. (이 안내는 인쇄되지 않습니다)</div>
{"".join(cards)}</body></html>'''


def pw_panel():
    S = store.get_settings()
    url = base_url()
    info = store.password_info()
    md('<div class="mx mx-note">분임 비밀번호는 <b>각 분임이 처음 들어올 때 직접</b> 만듭니다(숫자 4자리). 관리팀도 숫자는 볼 수 없습니다.<br>'
       '분임이 비밀번호를 잊었거나 다른 분임이 잘못 만들었으면 <b>[🔄 초기화]</b> → 그 분임이 다음에 들어올 때 새로 만듭니다. '
       '(이미 들어와 있던 휴대폰도 나가지니, 새 비밀번호를 분임원에게 다시 알려 주세요.)</div>')
    for g in range(1, store.N_GROUPS + 1):
        p = info.get(g)
        st_txt = ("✅ 만듦 · " + kst(p["set_at"]) + (" · <b style='color:#cf4430'>잠깐 막힘(여러 번 틀림)</b>" if p["locked"] else "")) if p else "⏳ 아직 안 만듦"
        with st.container(border=True, key=f"row_pw_{g}"):
            c1, c2, c3 = st.columns([1.2, 3, 1.4], vertical_alignment="center")
            c1.markdown(f'<div class="mx" style="font-size:1.15rem"><b>{ESC(S["names"][g - 1])}</b></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="mx mx-note">{st_txt}<br><span style="font-size:.82rem">{ESC(url)}/?g={g}</span></div>', unsafe_allow_html=True)
            with c3:
                if p and confirm_button("🔄 초기화", f"pw_rm_{g}", f"{S['names'][g - 1]} 비밀번호를 지웁니다."):
                    store.reset_password(g)
                    st.rerun()
    if not url or "localhost" in url:
        st.warning("접속 주소를 알 수 없습니다. [설정] 탭에 앱 주소(…streamlit.app)를 넣어 주세요.")
        return
    st.download_button("🖨 인쇄용 분임 QR 카드 내려받기 (A4 한 장에 2분임)", qr_cards_html(url, S), file_name="분임_QR카드.html",
                       mime="text/html", use_container_width=True)
    st.markdown(f"**스크린(프로젝터) 주소** `{url}/?view=screen` · **관리 화면** `{url}/?view=admin`")


def settings_panel():
    S = store.get_settings()
    with st.form("settings"):
        ev = st.text_input("행사 이름", S["event"], max_chars=30)
        cols = st.columns(4)
        names = [cols[i % 4].text_input(f"{i + 1}번 분임 이름", S["names"][i], max_chars=16) for i in range(store.N_GROUPS)]
        notice = st.text_area("분임 화면 안내 문구", S["notice"], max_chars=200, help="예: 기획서 제출 마감 11/12(목) 18시")
        url = st.text_input("앱 주소 (QR 카드에 들어감)", S["public_url"], placeholder="https://….streamlit.app")
        if st.form_submit_button("저장", type="primary"):
            store.save_settings(event=ev.strip() or "워크숍", names=names, notice=notice, public_url=url.strip().rstrip("/"))
            st.success("저장했습니다.")
            st.rerun()


def backup_panel():
    md('<div class="mx mx-note">무료 서버는 다시 켜지면 기획서·결과물이 지워질 수 있습니다. 중간중간 백업 파일을 받아 두고, '
       '완성 영상 원본은 관리팀 노트북에도 꼭 보관해 주세요. (백업 파일에는 영상이 들어가지 않습니다)</div>')
    st.download_button(f"💾 기획서·대화 백업 내려받기 ({kst(time.time(), '%H:%M')} 기준)", store.backup(),
                       file_name=f"영상의뢰_백업_{kst(time.time(), '%m%d_%H%M')}.json", mime="application/json", use_container_width=True)
    up = st.file_uploader("백업 파일로 되살리기", type=["json"], key="restore")
    if up and st.button("이 백업으로 되살리기", type="primary"):
        if act(store.restore, up.getvalue()):
            st.success("되살렸습니다.")
    md("<hr>")
    if st.button("📦 모든 결과물 묶음 만들기 (보관용 zip)", use_container_width=True):
        st.session_state["zip"] = store.results_zip()
    if st.session_state.get("zip"):
        st.download_button(f"⬇ 결과물 묶음 내려받기 ({size_txt(len(st.session_state['zip']))})", st.session_state["zip"],
                           file_name=f"분임_영상_{kst(time.time(), '%m%d')}.zip", mime="application/zip", use_container_width=True)
    md("<hr>")
    if confirm_button("🧹 모두 지우고 처음부터 (리허설 뒤에)", "reset", "모든 기획서·자료·결과물·대화와 분임 비밀번호를 지웁니다. 설정(분임 이름 등)은 남습니다."):
        store.reset_all()
        st.success("초기화했습니다.")


# ───────────────────────── 스크린(프로젝터)
def screen_view():
    md(SCREEN_CSS)
    S = store.get_settings()
    rid = store.screen_get().get("rid")
    r = store.get_result(rid) if rid else None
    # 영상을 트는 중에는 '틀 영상'이 바뀔 때만 다시 그림(분임이 기획서를 고쳐도 영상이 처음부터 다시 시작하지 않게)
    tok = (lambda: f"play|{store.screen_get()}") if r else store.board_token
    st.session_state["scr_tok"] = tok()
    if r:
        R = store.get_request(r["g"])
        md(f'<div class="sc-head"><b>{ESC(S["names"][r["g"] - 1])}</b><span>{ESC(R["data"]["title"] or R["data"]["topic"])}</span></div>')
        if r["video"]:
            st.video(r["path"], format="video/" + ("quicktime" if r["ext"] == "mov" else r["ext"]), autoplay=True)
        else:
            st.image(r["path"], use_container_width=True)
    else:
        md(f'<div class="sc-title">{ESC(S["event"])}</div><div class="sc-sub">분임 모션 영상</div>')
        cards = []
        for R in store.all_requests():
            g = R["g"]
            cards.append(f'<div class="sc-card"><div class="n">{ESC(S["names"][g - 1])} {badge(R["status"])}</div>'
                         f'<div class="t">{ESC(R["data"]["title"] or R["data"]["topic"])}</div></div>')
        md('<div class="sc-board">' + "".join(cards) + "</div>")

    @st.fragment(run_every=2)
    def watch():
        if tok() != st.session_state.get("scr_tok"):
            st.rerun()
    watch()


# ───────────────────────── 어느 화면?
qp = st.query_params
view = qp.get("view", "")
if view == "admin":
    admin_view()
elif view == "screen":
    screen_view()
else:
    g = st.session_state.get("g")
    if g and not store.check_token(int(g), st.session_state.get("tok")):
        leave()                      # 관리팀이 비밀번호를 초기화했으면 다시 들어오게
        st.session_state["pick"] = g
        g = None
    if not g and qp.get("g"):
        try:
            gq = int(qp.get("g"))
        except ValueError:
            gq = 0
        if store.check_token(gq, qp.get("k")):
            st.session_state.update({"g": gq, "tok": qp.get("k")})
            g = gq
        elif 1 <= gq <= store.N_GROUPS:
            st.session_state["pick"] = gq     # QR 카드로 들어옴 → 그 분임 비밀번호 화면
    if g:
        group_view(int(g))
    else:
        home_view()

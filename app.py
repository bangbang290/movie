"""워크숍 모션 영상 의뢰 (Streamlit) — 주소 하나로 세 화면.

  /                 분임 화면(휴대폰): 분임 고르기 → 분임 코드 → 의뢰서 쓰기·제출 → 결과물 보기·수정 요청
  /?g=3&k=1234      분임 QR 카드로 바로 들어오는 주소
  /?view=admin      관리팀(노트북, PIN): 진행 현황 · Claude 요청문 복사 · 결과물 올리기 · 코드/QR · 백업
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


def salt() -> str:
    return secret("code_salt") or secret("admin_pin") or "motion-default"


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


# ───────────────────────── 의뢰서 내용 보기(읽기 전용)
def summary_html(d: dict, atts: list[dict]) -> str:
    def row(k, v):
        v = str(v).strip()
        return f"<div><b>{k}</b> · {ESC(v)}</div>" if v else ""
    length = d["length_custom"] if d["length"] == "직접 입력" else d["length"]
    use = d["use_etc"] if d["use"] == "기타" and d["use_etc"] else d["use"]
    h = [row("영상 제목", d["title"]), row("쓰임새", use), row("길이", length), row("화면", f'{d["ratio"]} · {d["quality"]}'), row("재생", d["loop"]),
         row("전하고 싶은 한 문장", d["message"]), row("보는 사람", d["audience"]), row("느꼈으면 하는 것", d["feeling"]),
         row("분위기", ", ".join(d["mood"])), row("그림 스타일", d["style"]), row("주인공 색", d["color"]), row("글꼴", d["font"]),
         row("참고할 느낌", d["ref"]), row("피하고 싶은 것", d["avoid"])]
    h.append(f'<div style="margin-top:.4rem"><b>장면 구성</b> · 합계 {store.total_sec(d)}초</div>')
    for i, s in enumerate(d["scenes"], 1):
        h.append(f'<div class="sc">장면 {i} ({s["sec"]}초)<br>· 글자: {ESC(s["text"]) or "(없음)"}'
                 + (f'<br>· 모습: {ESC(s["look"])}' if s["look"].strip() else "")
                 + (f'<br>· 움직임: {ESC(s["motion"])}' if s["motion"].strip() else "") + "</div>")
    h += [row("배경음악", d["music"] + (f' ({d["music_mood"]})' if d["music_mood"] and d["music"] == store.YESNO_MUSIC[0] else "")),
          row("효과음", d["sfx"]), row("내레이션", d["narration"]),
          row("첨부", ", ".join(a["name"] for a in atts)), row("마지막 장면 멈춤", f'{d["hold_end"]}초' if d["hold_end"] else ""),
          row("표지 그림", "받기" if d["cover"] else ""), row("기타 요청", d["etc"])]
    return '<div class="mx mx-card mx-sum">' + "".join(h) + "</div>"


def chat_html(msgs: list[dict], me: str) -> str:
    if not msgs:
        return '<div class="mx mx-note">아직 주고받은 글이 없어요.</div>'
    out = []
    for m in msgs:
        who = "me" if m["who"] == me else "them"
        name = "관리팀" if m["who"] == "admin" else "분임"
        out.append(f'<div class="{who}">{ESC(m["text"])}<small>{name} · {kst(m["at"])}</small></div>')
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
       f'<div class="mx-note">분임별로 영상 의뢰서를 쓰고, 완성된 영상을 여기서 바로 봅니다.<br>분임 QR 카드를 찍었다면 바로 들어와져요.</div></div>')
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
    md(f'<div class="mx mx-sec">{ESC(S["names"][pick - 1])} 코드 넣기</div>')
    with st.form("login"):
        code = st.text_input("분임 코드 (숫자 4자리 · 분임 카드에 적혀 있어요)", max_chars=4)
        ok = st.form_submit_button("들어가기", type="primary", use_container_width=True)
    if ok:
        if store.check_code(pick, code, salt()):
            st.session_state["g"] = pick
            st.query_params.update({"g": str(pick), "k": code.strip()})
            st.rerun()
        st.error("코드가 맞지 않아요. 분임 카드의 숫자 4자리를 확인해 주세요.")
    if st.button("← 다른 분임 고르기"):
        st.session_state.pop("pick", None)
        st.rerun()


# ───────────────────────── 분임 화면
STEPS = ["① 의뢰서 쓰기", "② 제출", "③ 제작 중", "④ 완성"]
STEP_AT = {"draft": 0, "submitted": 1, "making": 2, "revise": 2, "done": 3}


def group_header(g: int, R: dict, S: dict):
    at = STEP_AT[R["status"]]
    steps = "".join(f'<span class="{"on" if i == at else "ok" if i < at else ""}">{t}</span>' for i, t in enumerate(STEPS))
    what = {"draft": "의뢰서를 쓰고 맨 아래 [제출하기]를 눌러 주세요.",
            "submitted": "접수됐어요! 제작이 시작되기 전까지는 의뢰서를 더 고칠 수 있어요.",
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
    names = ["🎬 결과물", "📝 의뢰서", "💬 수정 요청·문의"] if res else ["📝 의뢰서", "🎬 결과물", "💬 수정 요청·문의"]
    tabs = dict(zip(names, st.tabs(names)))
    with tabs["📝 의뢰서"]:
        form_area(g)
    with tabs["🎬 결과물"]:
        results_area(g, res)
    with tabs["💬 수정 요청·문의"]:
        chat_area(g)
    watch_group(g)
    md('<div style="height:1.4rem"></div>')
    if st.button("다른 분임으로 바꾸기", key="logout"):
        for k in ("g", "pick"):
            st.session_state.pop(k, None)
        st.query_params.clear()
        st.rerun()


def watch_group(g: int):
    """관리팀이 상태를 바꾸거나 결과물·답장을 올리면 화면을 새로 그림."""
    def token():
        R = store.get_request(g)
        return (R["status"], len(store.results(g)), len(store.messages(g)))
    st.session_state[f"tok_{g}"] = token()

    @st.fragment(run_every=8)
    def w():
        if token() != st.session_state.get(f"tok_{g}"):
            st.rerun()
    w()


# 의뢰서: 쓰는 대로 저장(칸마다). 칸 이름 앞에 '판 번호(ep)'를 붙여, 장면을 넣거나 지우면 새 칸으로 다시 불러옴.
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
        md('<div class="mx mx-warn">제작이 시작돼서 의뢰서는 더 고칠 수 없어요. 고칠 내용은 <b>[수정 요청·문의]</b>에 남겨 주세요.</div>')
        md(summary_html(d, store.attachments(g)))
        return
    md('<div class="mx mx-warn">✏️ 쓰는 대로 저장돼요(칸을 벗어나면 저장). 한 분임에서 <b>한 사람이 대표로</b> 쓰는 걸 권해요.<br>'
       '🔒 외부 서버라서 업무 문서·보고서 같은 <b>내부자료는 적거나 올리지 마세요.</b></div>')

    md('<div class="mx mx-sec"><i>1</i>기본 정보</div>')
    w_text(g, d, "title", "영상 제목 *", placeholder="예: 3분임, 그 시절로!", max_chars=40)
    w_radio(g, d, "use", "어디에 쓰나요?", store.USES, horizontal=True)
    if st.session_state.get(_key(g, "use")) == "기타":
        w_text(g, d, "use_etc", "쓰임새 직접 쓰기", max_chars=40)
    w_radio(g, d, "length", "영상 길이", store.LENGTHS, horizontal=True)
    if st.session_state.get(_key(g, "length")) == "직접 입력":
        w_text(g, d, "length_custom", "길이 직접 쓰기", placeholder="예: 45초", max_chars=10)
    w_radio(g, d, "ratio", "화면 비율", store.RATIOS)
    w_radio(g, d, "quality", "화질", store.QUALITIES, horizontal=True)
    w_radio(g, d, "loop", "재생 방식", store.LOOPS)

    md('<div class="mx mx-sec"><i>2</i>전하고 싶은 것</div>')
    w_text(g, d, "message", "전하고 싶은 한 문장 *", area=True, height=80, max_chars=200,
           placeholder="예: 우리 분임은 함께라서 더 즐겁다!")
    w_text(g, d, "audience", "보는 사람", placeholder="예: 워크숍에 온 심사2국 직원", max_chars=60)
    w_text(g, d, "feeling", "보고 나서 느꼈으면 하는 것", placeholder="예: 웃음, 뿌듯함, 설렘", max_chars=60)

    md('<div class="mx mx-sec"><i>3</i>분위기와 디자인</div>')
    k = _key(g, "mood")
    if k not in st.session_state:
        st.session_state[k] = [m for m in d["mood"] if m in store.MOODS]
    st.pills("분위기 (여러 개 골라도 돼요)", store.MOODS, selection_mode="multi", key=k, on_change=_cb_field, args=(g, "mood", k))
    w_radio(g, d, "style", "그림 스타일", store.STYLES, horizontal=True)
    w_text(g, d, "color", "주인공 색", placeholder="예: 남색과 금색, 기관 색", max_chars=40)
    w_radio(g, d, "font", "글꼴 느낌", store.FONTS, horizontal=True)
    w_text(g, d, "ref", "참고할 느낌 (말로 설명)", placeholder="예: 옛날 운동회 포스터처럼", max_chars=120,
           help="분위기만 참고해요. 유명 캐릭터·영화·광고를 똑같이 따라 만들지는 않아요.")
    w_text(g, d, "avoid", "피하고 싶은 것", placeholder="예: 너무 어두운 색", max_chars=120)

    tot, L = store.total_sec(d), store.length_sec(d)
    gap = f" · 목표 {L}초" + (" ✔" if L and abs(tot - L) <= 2 else f" (차이 {tot - L:+d}초)" if L else "") if L else ""
    md(f'<div class="mx mx-sec"><i>4</i>장면 구성 <span style="font-size:1rem;color:#6a5a45">합계 {tot}초{gap}</span></div>')
    md('<div class="mx mx-note">한 칸이 한 장면이에요. 화면에 나올 글자는 띄어쓰기까지 <b>그대로</b> 적어 주세요.<br>'
       '움직임 예: 서서히 나타남 · 옆에서 미끄러져 들어옴 · 통 튀어오름 · 한 자씩 타자 치듯 · 카메라가 다가감 · 반짝임</div>')
    n = len(d["scenes"])
    for i, s in enumerate(d["scenes"]):
        with st.container(border=True, key=f"scene_{g}_{_ep(g)}_{i}"):
            with st.container(key=f"row_sc_{g}_{_ep(g)}_{i}"):
                c0, c1, c2, c3 = st.columns([3, 1, 1, 1])
                c0.markdown(f'<div class="mx mx-sec" style="margin:.2rem 0">장면 {i + 1}</div>', unsafe_allow_html=True)
                if c1.button("↑", key=f"up_{g}_{_ep(g)}_{i}", disabled=i == 0, help="위로"):
                    if act(store.move_scene, g, i, -1):
                        _bump(g)
                        st.rerun(scope="fragment")
                if c2.button("↓", key=f"dn_{g}_{_ep(g)}_{i}", disabled=i == n - 1, help="아래로"):
                    if act(store.move_scene, g, i, 1):
                        _bump(g)
                        st.rerun(scope="fragment")
                if c3.button("🗑", key=f"rm_{g}_{_ep(g)}_{i}", disabled=n == 1, help="이 장면 지우기"):
                    if act(store.del_scene, g, i):
                        _bump(g)
                        st.rerun(scope="fragment")
            for part, label, kind, kw in (
                    ("sec", "길이(초)", "num", {}),
                    ("text", "화면에 나올 글자 (그대로)", "area", {"height": 68, "max_chars": 200, "placeholder": "예: 2026 심사2국 워크숍"}),
                    ("look", "보이는 모습", "area", {"height": 68, "max_chars": 300, "placeholder": "예: 하늘색 배경에 운동회 깃발"}),
                    ("motion", "움직임 · 다음 장면으로 넘어가는 방식", "text", {"max_chars": 150, "placeholder": "예: 글자가 붓으로 쓰듯 한 자씩"})):
                k = f"{_key(g, 'sc')}{i}_{part}"
                if k not in st.session_state:
                    st.session_state[k] = s[part]
                if kind == "num":
                    st.number_input(label, min_value=1, max_value=120, step=1, key=k, on_change=_cb_scene, args=(g, i, part, k))
                elif kind == "area":
                    st.text_area(label, key=k, on_change=_cb_scene, args=(g, i, part, k), **kw)
                else:
                    st.text_input(label, key=k, on_change=_cb_scene, args=(g, i, part, k), **kw)
    if st.button("＋ 장면 추가", key=f"add_{g}", use_container_width=True, disabled=n >= 15):
        if act(store.add_scene, g):
            _bump(g)
            st.rerun(scope="fragment")

    md('<div class="mx mx-sec"><i>5</i>소리</div>')
    w_radio(g, d, "music", "배경음악", store.YESNO_MUSIC, horizontal=True)
    if st.session_state.get(_key(g, "music")) == store.YESNO_MUSIC[0]:
        w_text(g, d, "music_mood", "음악 분위기", placeholder="예: 경쾌한 행진곡, 잔잔한 국악", max_chars=60,
               help="새로 만든 곡을 넣어요. 기존 노래나 유명한 곡 멜로디는 쓸 수 없어요.")
    w_text(g, d, "sfx", "효과음 (넣고 싶은 곳)", placeholder="예: 글자가 나올 때 '띠링'", max_chars=100)
    w_radio(g, d, "narration", "내레이션 (사람 목소리)", store.NARR)

    md('<div class="mx mx-sec"><i>6</i>넣을 자료와 받는 형태</div>')
    md('<div class="mx mx-note">로고·사진·녹음 파일이 있으면 올려 주세요. <b>쓰여도 되는 로고, 찍힌 사람이 동의한 사진</b>만 올려 주세요.</div>')
    ck = f"upc_{g}"
    uk = f"up_{g}_{st.session_state.get(ck, 0)}"
    st.file_uploader("자료 올리기", type=store.ATT_TYPES, accept_multiple_files=True, key=uk, on_change=_cb_upload, args=(g, uk, ck),
                     label_visibility="collapsed")
    for a in store.attachments(g):
        with st.container(key=f"row_att_{a['id']}"):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f'<div class="mx mx-note">📎 {ESC(a["name"])} · {size_txt(a["size"])}</div>', unsafe_allow_html=True)
            if c2.button("🗑", key=f"att_rm_{a['id']}", help="지우기"):
                store.del_attachment(g, a["id"])
                st.rerun(scope="fragment")
    k = _key(g, "hold_end")
    if k not in st.session_state:
        st.session_state[k] = d["hold_end"]
    st.number_input("마지막 장면에서 멈춰 있을 시간(초) · 시상 뒤 화면을 세워 둘 때", min_value=0, max_value=30, step=1, key=k,
                    on_change=_cb_field, args=(g, "hold_end", k))
    k = _key(g, "cover")
    if k not in st.session_state:
        st.session_state[k] = d["cover"]
    st.checkbox("마지막 장면 그림 파일(표지·포스터용)도 받기", key=k, on_change=_cb_field, args=(g, "cover", k))
    w_text(g, d, "etc", "그 밖에 하고 싶은 말", area=True, height=80, max_chars=500)

    md('<div style="height:.6rem"></div>')
    if st.button("🔄 다른 휴대폰에서 쓴 내용 불러오기", key=f"reload_{g}", use_container_width=True):
        _bump(g)
        st.rerun(scope="fragment")
    miss = store.missing(store.get_request(g)["data"])
    if R["status"] == "submitted":
        md('<div class="mx mx-warn" style="border-style:solid;border-color:#1f3f8f;background:#eef3ff">✅ 제출 완료! 지금 고치는 내용도 자동으로 관리팀에 보여요.</div>')
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
           ("의뢰서를 제출하면 관리팀이 만들기 시작해요." if R["status"] == "draft" else "완성되면 여기에 바로 올라와요.") + "</div>")
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
    R = store.get_request(g)
    md('<div class="mx mx-note">고칠 곳은 <b>장면 번호</b>로 말해 주세요. 예: "3번 장면 글자를 더 크게", "2번 장면을 2초 짧게".</div>')
    md(chat_html(store.messages(g), "group"))
    with st.form(f"msg_{g}", clear_on_submit=True):
        t = st.text_area("보낼 내용", height=90, max_chars=1000, label_visibility="collapsed",
                         placeholder="수정 요청이나 궁금한 점을 적어 주세요")
        ok = st.form_submit_button("보내기", type="primary", use_container_width=True)
    if ok:
        if act(store.add_message, g, "group", t):
            st.success("보냈어요!" + (" 수정 요청으로 접수됐어요." if R["status"] == "done" else ""))
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
        st.error("Streamlit 설정(Secrets)에 admin_pin 이 없습니다. 지금은 임시 PIN 0000이고, 분임 코드도 누구나 계산할 수 있는 상태입니다. "
                 "배포 화면의 Settings → Secrets에 admin_pin = \"숫자\"를 넣어 주세요.")
    tabs = st.tabs(["📋 진행 현황", "🔑 분임 코드·QR", "⚙️ 설정", "💾 백업·초기화"])
    with tabs[0]:
        overview()
        md("<hr>")
        detail()
    with tabs[1]:
        codes_panel()
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
        rows.append(f'<tr><td><b>{ESC(S["names"][g - 1])}</b></td><td>{ESC(d["title"]) or "<span style=color:#9a8a72>(제목 없음)</span>"}</td>'
                    f'<td>{badge(R["status"])}</td><td>{len(d["scenes"])}장면 · {store.total_sec(d)}초</td><td>{nres}개</td>'
                    f'<td>{f"<span class=new>새 글 {new}</span>" if new else ""}</td><td>{kst(R["updated_at"])}</td></tr>')
    md('<table class="mx mx-tbl"><tr><th>분임</th><th>영상 제목</th><th>상태</th><th>장면</th><th>결과물</th><th>새 글</th><th>마지막 변경</th></tr>'
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
                     help="의뢰서 잠금을 풀고 '작성 중'으로 돌립니다"):
            store.set_status(g, "draft")
            st.rerun()
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        md('<div class="mx mx-sec">Claude에게 보낼 요청문</div>')
        if R["status"] == "draft":
            md('<div class="mx mx-note">아직 제출 전입니다(작성 중인 내용).</div>')
        md('<div class="mx mx-note">오른쪽 위 복사 버튼 → 새 Claude 대화창에 붙여 넣기. 아래 첨부 자료도 같이 올려 주세요.</div>')
        st.code(store.prompt_text(g, S), language=None, wrap_lines=True)
        rv = store.revision_text(g, S)
        if rv and store.results(g):
            md('<div class="mx mx-sec">수정 요청문 <span style="font-size:1rem;color:#6a5a45">(만들었던 대화창에 이어서)</span></div>')
            st.code(rv, language=None, wrap_lines=True)
        atts = store.attachments(g)
        md('<div class="mx mx-sec">분임이 올린 자료</div>')
        if not atts:
            md('<div class="mx mx-note">없음</div>')
        for a in atts:
            st.download_button(f"📎 {a['name']} ({size_txt(a['size'])})", store.read_bytes(a["path"]), file_name=a["name"],
                               key=f"ad_att_{a['id']}", use_container_width=True)
        with st.expander("의뢰서 보기 (사람이 읽기 좋게)"):
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
        code = store.group_code(g, salt())
        link = f"{url}/?g={g}&k={code}"
        qr = segno.make(link, error="m").svg_data_uri(scale=8, border=2, dark="#000000", light="#ffffff")
        name = ESC(S["names"][g - 1])
        cards.append(f'''<section class="card"><div class="ev">{ESC(S["event"])} · 모션 영상 의뢰</div><div class="nm">{name}</div>
<img class="qr" src="{qr}" alt="QR"><ol><li>휴대폰 <b>카메라</b>로 QR 코드를 비춥니다.</li><li>뜨는 <b>주소</b>를 누르면 우리 분임 화면이 열립니다.</li>
<li>의뢰서를 쓰고 <b>[제출하기]</b>. 완성 영상도 여기서 봅니다.</li></ol>
<div class="ft">직접 들어갈 때: {ESC(url)} → {name} → 분임 코드 <b class="code">{code}</b> · 다른 분임과 바꿔 쓰지 마세요.</div></section>''')
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>분임 QR 카드</title><style>
@page{{size:A4;margin:12mm}}body{{margin:0;font-family:"Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif;color:#111;background:#fff}}
.tip{{padding:10px 14px;margin:0 0 10px;background:#eef3ff;border:1px solid #c9d6f5;border-radius:8px;font-size:14px}}@media print{{.tip{{display:none}}}}
.card{{height:128mm;box-sizing:border-box;border:1.5px dashed #9aa4b8;border-radius:6mm;padding:9mm 12mm;margin:0 0 8mm;display:grid;grid-template-columns:1fr 62mm;
grid-template-rows:auto auto 1fr auto;column-gap:10mm;break-inside:avoid;page-break-inside:avoid}}.card:nth-of-type(2n){{break-after:page;page-break-after:always}}
.ev{{grid-column:1/3;font-size:13pt;color:#3b4a6b;font-weight:700}}.nm{{grid-column:1/2;font-size:34pt;font-weight:800;margin-top:6mm}}
.qr{{grid-column:2/3;grid-row:2/4;width:62mm;height:62mm;align-self:center}}ol{{grid-column:1/2;margin:6mm 0 0;padding-left:6mm;font-size:14pt;line-height:1.75;word-break:keep-all}}
.ft{{grid-column:1/3;font-size:11.5pt;color:#555;border-top:1px solid #dde3ee;padding-top:3mm;margin-top:4mm}}.code{{font-size:15pt;color:#111;letter-spacing:2px}}
</style></head><body><div class="tip">이 파일을 연 상태에서 <b>Ctrl + P</b>로 인쇄하세요. 한 장에 두 분임씩 나오고, 점선을 따라 자르면 됩니다. (이 안내는 인쇄되지 않습니다)</div>
{"".join(cards)}</body></html>'''


def codes_panel():
    S = store.get_settings()
    url = base_url()
    md('<div class="mx mx-note">분임 코드는 비밀값으로 계산해서 서버가 다시 켜져도 바뀌지 않습니다. 카드를 인쇄해 분임마다 나눠 주세요.</div>')
    rows = "".join(f'<tr><td><b>{ESC(S["names"][g - 1])}</b></td><td style="font-size:1.3rem;letter-spacing:2px">{store.group_code(g, salt())}</td>'
                   f'<td style="font-size:.85rem">{ESC(url)}/?g={g}&amp;k={store.group_code(g, salt())}</td></tr>' for g in range(1, store.N_GROUPS + 1))
    md(f'<table class="mx mx-tbl"><tr><th>분임</th><th>코드</th><th>바로 들어가는 주소 (QR 내용)</th></tr>{rows}</table>')
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
        notice = st.text_area("분임 화면 안내 문구", S["notice"], max_chars=200, help="예: 의뢰서 제출 마감 11/12(목) 18시")
        url = st.text_input("앱 주소 (QR 카드에 들어감)", S["public_url"], placeholder="https://….streamlit.app")
        if st.form_submit_button("저장", type="primary"):
            store.save_settings(event=ev.strip() or "워크숍", names=names, notice=notice, public_url=url.strip().rstrip("/"))
            st.success("저장했습니다.")
            st.rerun()


def backup_panel():
    md('<div class="mx mx-note">무료 서버는 다시 켜지면 의뢰서·결과물이 지워질 수 있습니다. 중간중간 백업 파일을 받아 두고, '
       '완성 영상 원본은 관리팀 노트북에도 꼭 보관해 주세요. (백업 파일에는 영상이 들어가지 않습니다)</div>')
    st.download_button(f"💾 의뢰서·대화 백업 내려받기 ({kst(time.time(), '%H:%M')} 기준)", store.backup(),
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
    if confirm_button("🧹 모두 지우고 처음부터 (리허설 뒤에)", "reset", "모든 의뢰서·자료·결과물·대화를 지웁니다. 설정(분임 이름 등)은 남습니다."):
        store.reset_all()
        st.success("초기화했습니다.")


# ───────────────────────── 스크린(프로젝터)
def screen_view():
    md(SCREEN_CSS)
    S = store.get_settings()
    rid = store.screen_get().get("rid")
    r = store.get_result(rid) if rid else None
    # 영상을 트는 중에는 '틀 영상'이 바뀔 때만 다시 그림(분임이 의뢰서를 고쳐도 영상이 처음부터 다시 시작하지 않게)
    tok = (lambda: f"play|{store.screen_get()}") if r else store.board_token
    st.session_state["scr_tok"] = tok()
    if r:
        R = store.get_request(r["g"])
        md(f'<div class="sc-head"><b>{ESC(S["names"][r["g"] - 1])}</b><span>{ESC(R["data"]["title"])}</span></div>')
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
                         f'<div class="t">{ESC(R["data"]["title"])}</div></div>')
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
    if not g and qp.get("g") and qp.get("k"):
        try:
            gq = int(qp.get("g"))
        except ValueError:
            gq = 0
        if store.check_code(gq, qp.get("k"), salt()):
            st.session_state["g"] = g = gq
    if g:
        group_view(int(g))
    else:
        home_view()

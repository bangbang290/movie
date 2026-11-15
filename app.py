"""워크숍 모션 영상 의뢰 (Streamlit) — 주소 하나로 세 화면.

  /                 분임 화면(휴대폰): 분임 고르기 → 비밀번호(처음엔 분임이 직접 만듦) → 기획서 쓰기·제출 → 결과물 보기·수정 요청
  /                 행사 공통 QR → 분임 고르기 → 비밀번호
  /?g=3             (선택) 분임별 QR 카드로 바로 들어오는 주소(그 분임 비밀번호 화면)
  /?view=admin      관리팀(노트북, PIN): 진행 현황 · 팀 배정 · Claude 요청문 복사 · 결과물 올리기 · 비밀번호 초기화/QR · 백업
  /?view=screen     스크린(프로젝터): 마법의 분임 배정식 · 발표 자료 · 결과물 크게 틀기 · 시사회(분임 소개 → 영상 → 다음 분임) · 투표 QR · 결과 발표
  /?view=vote       투표(각자 휴대폰): 내 이름 → 우리 분임을 뺀 작품 중 한 편 (1인 1표, 명단은 관리팀이 미리 등록)
"""
from __future__ import annotations

import html
import json
import os
import random
import re
import time

import streamlit as st

import store

st.set_page_config(page_title="워크숍 영상 의뢰", page_icon="🎬", layout="centered", initial_sidebar_state="collapsed")
store.init()

ESC = html.escape
BADGE = {"draft": ("작성 중", "#8a7a62", "#efe6cf"), "submitted": ("접수 완료", "#1f3f8f", "#dfe7fb"),
         "making": ("제작 중", "#b4560f", "#fbe7d2"), "done": ("완성", "#1f7a3c", "#dcf2e1"),
         "revise": ("수정 요청", "#b3261e", "#fbdedb")}

# 디자인: 윈터 매직(와인색 바탕 · 샴페인 금색 · 상아색 영화표 · 명조체) — 색은 아래 값과 .streamlit/config.toml에서 함께 바꿈
FONTS = ('@import url("https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500'
         '&family=Noto+Serif+KR:wght@400;500;600&family=Noto+Sans+KR:wght@400;500;700&display=swap");')
TWINKLE = ("@keyframes tw{0%,100%{opacity:1}50%{opacity:.18}}@keyframes pl{0%,100%{opacity:1}50%{opacity:.62}}"
           ".tw{animation:tw 2.2s ease-in-out infinite}.pl{animation:pl 2.8s ease-in-out infinite}"
           "@media (prefers-reduced-motion: reduce){.tw,.pl{animation:none}}")

BASE_CSS = """<style>
""" + FONTS + TWINKLE + """
header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],#MainMenu,footer{display:none!important}
[data-stale="true"],.stale-element{opacity:1!important;transition:none!important}
.stApp{background:#3A2126}
.stApp::before{content:"";position:fixed;inset:10px;border:1px solid #D6B676;pointer-events:none;z-index:1}
.stApp::after{content:"";position:fixed;inset:15px;border:1px solid #8E6F45;pointer-events:none;z-index:1}
.block-container{max-width:760px!important;padding-top:1.8rem!important;padding-bottom:4rem!important}
.stApp,.stMarkdown,.stTextInput,.stTextArea,.stRadio,.stSelectbox{font-family:"Noto Sans KR","Malgun Gothic","Apple SD Gothic Neo",sans-serif}
.mx{font-family:"Noto Sans KR","Malgun Gothic","Apple SD Gothic Neo",sans-serif;color:#F4EAD5}
.mx-card{background:#F4EAD5;color:#3A1F17;border-radius:4px;box-shadow:inset 0 0 0 5px #F4EAD5,inset 0 0 0 6px #D6B676;padding:1.05rem 1.2rem;margin:.2rem 0 .8rem}
.mx-card .mx-note{color:#5B4636}
.mx-card .mx-ev{color:#7A5A3C}
.mx-top{display:flex;align-items:center;gap:.7rem;flex-wrap:wrap}
.mx-ev{font-family:"Cormorant Garamond","Noto Serif KR",serif;font-size:.95rem;font-weight:600;letter-spacing:.1em;color:#D6B676}
.mx-h1{font-family:"Noto Serif KR",serif;font-weight:600;font-size:2rem;line-height:1.25;margin:.15rem 0}
.mx-badge{display:inline-block;font-family:"Noto Serif KR",serif;font-weight:500;font-size:1rem;padding:.05rem .75rem;border-radius:999px;border:1.5px solid currentColor;white-space:nowrap}
.mx-steps{display:flex;gap:.3rem;margin:.7rem 0 .1rem;flex-wrap:wrap}
.mx-steps span{flex:1 1 0;min-width:4.6rem;text-align:center;font-size:.85rem;padding:.35rem .2rem;border-radius:3px;background:#E9DCC0;color:#7A5A3C}
.mx-steps span.on{background:#6B1F2C;color:#F4EAD5}
.mx-steps span.ok{background:#E2CFA8;color:#3A1F17}
.mx-note{font-size:.95rem;color:#E5D3C2;line-height:1.6;word-break:keep-all}
.mx-note a{color:#E8D4A8}
.mx-sec{font-family:"Noto Serif KR",serif;font-weight:500;font-size:1.3rem;letter-spacing:.04em;color:#D6B676;margin:1.3rem 0 .4rem;display:flex;align-items:center;gap:.5rem}
.mx-sec i{font-style:normal;display:inline-grid;place-items:center;width:1.65rem;height:1.65rem;border-radius:50%;background:#D6B676;color:#6B1F2C;font-size:.95rem}
.mx-warn{font-size:.92rem;line-height:1.55;padding:.65rem .85rem;border-radius:4px;background:#F4EAD5;color:#3A1F17;border:1.5px dashed #C9A45C;margin:.3rem 0 .6rem}
.mx-warn a{color:#9E2236}
.mx-sum{font-size:.98rem;line-height:1.6}
.mx-sum b{font-family:"Noto Serif KR",serif;font-weight:600;font-size:1.02rem}
.mx-sum .sc{border-top:1px dashed #C9B48E;padding:.45rem 0}
.mx-chat{display:flex;flex-direction:column;gap:.45rem;margin:.3rem 0 .8rem}
.mx-chat div{max-width:86%;padding:.55rem .8rem;border-radius:10px;font-size:.98rem;line-height:1.5;color:#3A1F17;white-space:pre-wrap;word-break:keep-all}
.mx-chat .me{align-self:flex-end;background:#F4EAD5;border-bottom-right-radius:3px}
.mx-chat .them{align-self:flex-start;background:#E8D4A8;border-bottom-left-radius:3px}
.mx-chat small{display:block;font-size:.75rem;color:#7A5A3C;margin-top:.15rem}
.mx-hero{display:flex;flex-direction:column;align-items:center;text-align:center;margin:.2rem 0 .4rem}
.mx-orn{display:flex;align-items:center;gap:12px;width:100%;box-sizing:border-box;padding:0 8px;font-family:"Cormorant Garamond","Noto Serif KR",serif;font-size:.8rem;font-weight:600;letter-spacing:.32em;color:#D6B676;white-space:nowrap}
.mx-orn::before,.mx-orn::after{content:"";flex:1;height:1px;background:#D6B676}
.mx-orn.sub{font-family:"Noto Serif KR",serif;font-size:.88rem;font-weight:500;letter-spacing:.12em;margin:1.4rem 0 .5rem}
.mx-orn.sub::before,.mx-orn.sub::after{background:#8E6F45}
.mx-subt{font-family:"Noto Serif KR",serif;font-size:.88rem;font-weight:500;letter-spacing:.14em;color:#D6B676}
.mx-foot{text-align:center;margin-top:1.6rem;font-family:"Cormorant Garamond",serif;font-style:italic;font-size:1.15rem;font-weight:500;color:#D6B676}
div[data-testid="stButton"] button,div[data-testid="stFormSubmitButton"] button,div[data-testid="stDownloadButton"] button{border-radius:3px!important;border:0!important;box-shadow:inset 0 0 0 4px #F4EAD5,inset 0 0 0 5px #D6B676!important;min-height:2.9rem;background:#F4EAD5!important;color:#3A1F17!important}
div[data-testid="stButton"] button p,div[data-testid="stFormSubmitButton"] button p,div[data-testid="stDownloadButton"] button p{font-family:"Noto Serif KR",serif;font-weight:600;font-size:1.05rem}
div[data-testid="stButton"] button[kind="primary"],div[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]{background:#D6B676!important;color:#2A140F!important;box-shadow:inset 0 0 0 4px #D6B676,inset 0 0 0 5px #6B1F2C!important}
div[data-testid="stButton"] button:hover,div[data-testid="stFormSubmitButton"] button:hover{filter:brightness(1.05)}
div[data-testid="stButton"] button:active{transform:translateY(1px)}
div[data-testid="stButton"] button:disabled{opacity:.45}
div[class*="st-key-row_"] [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:.6rem!important}
div[class*="st-key-row_"] [data-testid="stColumn"]{min-width:0!important}
div[class*="st-key-row_"] button{min-height:2.4rem!important;padding:0 .4rem!important}
div[class*="st-key-pick_"] button{min-height:64px!important;flex-direction:column!important;gap:1px;
 -webkit-mask:radial-gradient(circle 7px at 0 50%,#0000 97%,#000) left/51% 100% no-repeat,radial-gradient(circle 7px at 100% 50%,#0000 97%,#000) right/51% 100% no-repeat;
 mask:radial-gradient(circle 7px at 0 50%,#0000 97%,#000) left/51% 100% no-repeat,radial-gradient(circle 7px at 100% 50%,#0000 97%,#000) right/51% 100% no-repeat}
div[class*="st-key-pick_"] button::before{font-family:"Cormorant Garamond",serif;font-size:.74rem;font-weight:600;letter-spacing:.22em;color:#7A5A3C}
div[class*="st-key-pick_"] button p{font-size:1.2rem!important}
div[class*="st-key-scene_"]{background:#46292F;border-radius:6px}
[data-testid="stExpander"] details{background:#46292F;border:1px solid #8E6F45;border-radius:6px}
</style>"""

ADMIN_CSS = """<style>
.block-container{max-width:1200px!important}
.mx-tbl{width:100%;border-collapse:collapse;font-size:.98rem;background:#F4EAD5;color:#3A1F17;border-radius:4px;overflow:hidden}
.mx-tbl th,.mx-tbl td{padding:.5rem .6rem;border-bottom:1px solid #E2D2B0;text-align:left;vertical-align:middle}
.mx-tbl th{background:#4F1520;color:#F4EAD5;font-weight:500;font-family:"Noto Serif KR",serif;font-size:1rem}
.mx-tbl .new{color:#fff;background:#C22D45;border-radius:999px;padding:0 .5rem;font-size:.85rem}
.tm-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(136px,1fr));gap:.6rem;margin:.4rem 0 .9rem}
.tm-card{background:#F4EAD5;color:#3A1F17;border-radius:4px;padding:.5rem .75rem .7rem;font-family:"Noto Sans KR","Malgun Gothic",sans-serif}
.tm-h{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid #E2D2B0;padding-bottom:.3rem;margin-bottom:.35rem}
.tm-h b{font-family:"Noto Serif KR",serif;font-weight:600;font-size:1.05rem}
.tm-h span{font-size:.85rem;color:#7A5A3C}
.tm-n{font-size:.98rem;line-height:1.6}
</style>"""

SCREEN_CSS = """<style>
""" + FONTS + TWINKLE + """
header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],#MainMenu,footer{display:none!important}
[data-stale="true"],.stale-element{opacity:1!important;transition:none!important}
.stApp{background:#6B1F2C}
.stApp::before{content:"";position:fixed;inset:2.2vh 1.6vw;border:1px solid #D6B676;pointer-events:none;z-index:1}
.stApp::after{content:"";position:fixed;inset:3.1vh 2.2vw;border:1px solid #8E6F45;pointer-events:none;z-index:1}
.block-container{max-width:100%!important;padding:5vh 4vw 0!important}
.sc-garland{position:fixed;left:4vw;right:4vw;top:4.2vh;z-index:2;pointer-events:none}
.sc-garland svg{width:100%;height:auto;overflow:visible;display:block}
.sc-sleigh{position:fixed;left:4.2vw;bottom:10vh;width:23vw;z-index:2;pointer-events:none}
.sc-tree{position:fixed;right:5vw;bottom:5.5vh;height:44vh;z-index:2;pointer-events:none}
.sc-sleigh svg,.sc-tree svg{width:100%;height:100%;overflow:visible;display:block}
.sc-head{display:flex;align-items:baseline;gap:1.2vw;color:#F4EAD5;font-family:"Noto Serif KR",serif;margin:0 0 1vh}
.sc-head b{font-weight:600;font-size:clamp(1.5rem,2.6vw,2.8rem)}
.sc-head span{font-size:clamp(1rem,1.5vw,1.6rem);color:#D6B676}
[data-testid="stVideo"] video,.stVideo video{width:100%!important;max-height:84vh;background:#000;border-radius:4px}
[data-testid="stImage"] img{max-height:84vh;object-fit:contain}
.sc-board{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(24vw,340px),1fr));gap:1.4vw;margin-top:3vh}
.sc-card{background:#F4EAD5;border-radius:4px;box-shadow:inset 0 0 0 6px #F4EAD5,inset 0 0 0 7px #D6B676;padding:1.6vw 1.9vw;font-family:"Noto Sans KR",sans-serif;color:#3A1F17}
.sc-card .n{font-family:"Noto Serif KR",serif;font-weight:600;font-size:clamp(1.3rem,2.1vw,2.3rem)}
.sc-card .t{font-size:clamp(1rem,1.3vw,1.4rem);margin-top:.4vh;min-height:1.5em}
.sc-title{font-family:"Noto Serif KR",serif;font-weight:600;color:#F4EAD5;font-size:clamp(2.6rem,5.2vw,5.6rem);line-height:1.15;text-align:center;margin-top:8vh}
.sc-sub{font-family:"Cormorant Garamond","Noto Serif KR",serif;font-weight:600;letter-spacing:.3em;color:#D6B676;text-align:center;font-size:clamp(1rem,1.6vw,1.7rem)}
.mx-badge{display:inline-block;font-family:"Noto Serif KR",serif;font-weight:500;font-size:clamp(.85rem,1.05vw,1.15rem);padding:.05rem .7rem;border-radius:999px;border:1.5px solid currentColor;white-space:nowrap;vertical-align:middle}
.sc-intro{position:relative;z-index:3;min-height:88vh;max-width:52vw;margin:0 auto;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:#F4EAD5;font-family:"Noto Serif KR",serif}
.sc-intro.wide{max-width:92vw}
.sc-intro.entry{max-width:45vw;min-height:90vh}
.sc-intro.entry .sc-title{margin-top:2.4vh;font-size:clamp(2rem,3.6vw,3.8rem)}
.sc-intro.entry .sc-sub{margin-top:.6vh}
.sc-entry{margin-top:3vh;width:31vh;height:31vh;box-sizing:border-box;padding:1.3vh;background:#fff;border-radius:3px;box-shadow:0 0 0 1px #D6B676,0 0 0 1.2vh #6B1F2C,0 0 0 calc(1.2vh + 1px) #8E6F45}
.sc-entry img{width:100%;height:100%;display:block}
.sc-how{margin-top:3vh;font-size:clamp(1.1rem,1.7vw,1.9rem);color:#F4EAD5}
.sc-how b{color:#D6B676;font-weight:600}
.sc-intro.entry .sc-board{width:100%;grid-template-columns:repeat(4,minmax(0,1fr));gap:.8vw;margin-top:3.4vh}
.sc-intro.entry .sc-card{padding:1.1vh 1vw;text-align:left;box-shadow:inset 0 0 0 4px #F4EAD5,inset 0 0 0 5px #D6B676}
.sc-intro.entry .sc-card .n{font-size:clamp(.95rem,1.35vw,1.5rem)}
.sc-intro.entry .sc-card .mx-badge{font-size:clamp(.7rem,.8vw,.9rem);padding:0 .45rem}
.sc-intro.entry .sc-card .t{font-size:clamp(.75rem,.95vw,1.05rem);min-height:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sc-intro .ev{width:100%;display:flex;align-items:center;gap:1.2vw;font-family:"Cormorant Garamond","Noto Serif KR",serif;font-weight:600;font-size:clamp(.9rem,1.25vw,1.4rem);letter-spacing:.3em;color:#D6B676;white-space:nowrap}
.sc-intro .ev::before,.sc-intro .ev::after{content:"";flex:1;height:1px;background:#D6B676}
.sc-intro .grp{margin-top:3.6vh;font-size:clamp(1.3rem,2vw,2.2rem);font-weight:500;letter-spacing:.12em;color:#D6B676}
.sc-intro .ttl{margin-top:.8vh;font-weight:600;font-size:clamp(2.8rem,6vw,6.4rem);line-height:1.15;color:#F4EAD5;word-break:keep-all}
.sc-intro .fmt{margin-top:2vh;display:flex;align-items:center;gap:1vw;font-size:clamp(.9rem,1.2vw,1.35rem);font-weight:500;letter-spacing:.2em;color:#D6B676}
.sc-intro .fmt::before,.sc-intro .fmt::after{content:"";width:2.2vw;height:1px;background:#D6B676}
.sc-intro .cr{margin-top:3.4vh;display:flex;flex-wrap:wrap;justify-content:center;gap:.8vh 2.4vw;font-size:clamp(1rem,1.45vw,1.6rem);font-weight:500}
.sc-intro .cr i{font-style:normal;color:#D6B676;font-size:.72em;letter-spacing:.1em;margin-right:.5em}
.sc-intro .pitch{margin-top:4.4vh;width:min(41vw,100%);padding:2.4vh 0;border-top:1px solid #8E6F45;border-bottom:1px solid #8E6F45;font-size:clamp(1rem,1.45vw,1.6rem);line-height:1.75;color:#EAD9C8;word-break:keep-all}
.sc-intro .pitch b{display:block;font-weight:500;font-size:.66em;letter-spacing:.22em;color:#D6B676;margin-bottom:1vh}
.sc-intro .soon{margin-top:4vh;display:flex;align-items:center;gap:1vw;font-size:clamp(1rem,1.3vw,1.45rem);font-weight:500;letter-spacing:.3em;color:#D6B676;animation:pl 2.8s ease-in-out infinite}
.sc-vote{display:flex;align-items:center;justify-content:center;gap:5vw;margin-top:3vh}
.sc-vote img{width:44vh;height:44vh;background:#fff;border-radius:4px;padding:1.8vh;box-sizing:border-box;box-shadow:0 0 0 1px #D6B676,0 0 0 7px #6B1F2C,0 0 0 8px #8E6F45}
.sc-vote .side{display:flex;flex-direction:column;gap:2.4vh;text-align:left;max-width:44vw}
.sc-vote .how{font-size:clamp(1.3rem,2.3vw,2.5rem);line-height:1.5;color:#F4EAD5}
.sc-vote .how b{color:#D6B676}
.sc-vote .url{font-family:"Noto Sans KR",sans-serif;font-size:clamp(.9rem,1.2vw,1.3rem);color:#CDB8A6;word-break:break-all}
.sc-count{font-family:"Noto Serif KR",serif;font-weight:600;font-size:clamp(1.6rem,2.8vw,3rem);color:#D6B676}
.sc-podium{display:flex;align-items:flex-end;justify-content:center;gap:2.4vw;margin-top:3vh;width:100%}
.sc-podium .pd{flex:0 1 27vw;background:#F4EAD5;color:#3A1F17;border-radius:4px;box-shadow:inset 0 0 0 6px #F4EAD5,inset 0 0 0 7px #D6B676;padding:3.4vh 1.6vw;text-align:center}
.sc-podium .pd.p1{padding:7vh 1.6vw;background:#D6B676;box-shadow:inset 0 0 0 6px #D6B676,inset 0 0 0 7px #6B1F2C}
.sc-podium .pd.hide{background:#561826;color:#D6B676;box-shadow:inset 0 0 0 1px #8E6F45}
.sc-podium .aw{font-family:"Noto Serif KR",serif;font-weight:600;font-size:clamp(1.4rem,2.3vw,2.5rem);color:#9E2236}
.sc-podium .hide .aw{color:#D6B676}
.sc-podium .rk{font-family:"Cormorant Garamond","Noto Serif KR",serif;font-weight:600;letter-spacing:.2em;font-size:clamp(1rem,1.4vw,1.5rem);color:#7A5A3C}
.sc-podium .gn{font-family:"Noto Serif KR",serif;font-weight:600;font-size:clamp(1.8rem,3.2vw,3.6rem);line-height:1.15;margin-top:1.2vh}
.sc-podium .gt{font-size:clamp(1rem,1.5vw,1.6rem);margin-top:.5vh;word-break:keep-all}
.sc-podium .gv{font-family:"Noto Serif KR",serif;font-weight:600;font-size:clamp(1.1rem,1.8vw,2rem);margin-top:.8vh;color:#6B1F2C}
.sc-podium .q{font-family:"Cormorant Garamond",serif;font-size:clamp(3rem,7vw,7.5rem);line-height:1}
.sc-podium .pd.p1{flex:0 1 44vw}
.sc-podium .pd.hide .q{animation:pl 1s ease-in-out infinite}
.sc-podium .pd.win{animation:pop .9s cubic-bezier(.2,1.4,.4,1) both,glow 2.4s ease-in-out .9s infinite}
.sc-podium .pd.win .gn{font-size:clamp(2.4rem,4.6vw,5rem)}
@keyframes pop{0%{transform:scale(.4) rotate(-4deg);opacity:0}100%{transform:scale(1) rotate(0);opacity:1}}
@keyframes glow{0%,100%{box-shadow:inset 0 0 0 6px #D6B676,inset 0 0 0 7px #6B1F2C,0 0 0 0 rgba(246,215,122,0)}50%{box-shadow:inset 0 0 0 6px #D6B676,inset 0 0 0 7px #6B1F2C,0 0 8vh 2vh rgba(246,215,122,.55)}}
.sc-intro .ttl.shine{color:#F6E3A8;animation:shine 1.8s ease-in-out infinite}
@keyframes shine{50%{text-shadow:0 0 3.5vh rgba(246,215,122,.9);transform:scale(1.04)}}
.sc-confetti{position:fixed;top:0;left:0;right:0;bottom:0;width:100vw;height:100vh;pointer-events:none;z-index:999;overflow:hidden}
.sc-confetti span{position:absolute;top:-4vh;display:block;width:1vw;height:2vh;border-radius:2px;opacity:.95;animation-timing-function:linear;animation-iteration-count:infinite}
.sc-confetti span.r{width:1.1vw;height:1.1vw;border-radius:50%}
.sc-confetti span.s{width:.5vw;height:2.6vh}
.sc-confetti span.f0{animation-name:cf0}
.sc-confetti span.f1{animation-name:cf1}
.sc-confetti span.f2{animation-name:cf2}
.sc-confetti span.f3{animation-name:cf3}
.sc-confetti span.f4{animation-name:cf4}
.sc-confetti span.f5{animation-name:cf5}
.sc-confetti span.bl,.sc-confetti span.br{top:auto;bottom:-3vh;animation-timing-function:cubic-bezier(.15,.6,.4,1);animation-iteration-count:1;animation-fill-mode:both}
.sc-confetti span.bl{left:-1vw}.sc-confetti span.br{right:-1vw}
.sc-confetti span.bl.b0{animation-name:bl0}.sc-confetti span.br.b0{animation-name:br0}
.sc-confetti span.bl.b1{animation-name:bl1}.sc-confetti span.br.b1{animation-name:br1}
.sc-confetti span.bl.b2{animation-name:bl2}.sc-confetti span.br.b2{animation-name:br2}
.sc-confetti span.bl.b3{animation-name:bl3}.sc-confetti span.br.b3{animation-name:br3}
@keyframes cf0{0%{transform:translate(0,0) rotate(0deg)}100%{transform:translate(-9vw,118vh) rotate(720deg)}}
@keyframes cf1{0%{transform:translate(0,0) rotate(0deg)}100%{transform:translate(7vw,118vh) rotate(-900deg)}}
@keyframes cf2{0%{transform:translate(0,0) rotate(0deg)}100%{transform:translate(-4vw,118vh) rotate(1080deg)}}
@keyframes cf3{0%{transform:translate(0,0) rotate(0deg)}100%{transform:translate(11vw,118vh) rotate(540deg)}}
@keyframes cf4{0%{transform:translate(0,0) rotate(0deg)}100%{transform:translate(3vw,118vh) rotate(-640deg)}}
@keyframes cf5{0%{transform:translate(0,0) rotate(0deg)}100%{transform:translate(-12vw,118vh) rotate(960deg)}}
@keyframes bl0{0%{transform:translate(0,0) rotate(0deg);opacity:1}55%{transform:translate(14vw,-78vh) rotate(500deg);opacity:1}100%{transform:translate(19vw,-8vh) rotate(900deg);opacity:0}}
@keyframes br0{0%{transform:translate(0,0) rotate(0deg);opacity:1}55%{transform:translate(-14vw,-78vh) rotate(-500deg);opacity:1}100%{transform:translate(-19vw,-8vh) rotate(-900deg);opacity:0}}
@keyframes bl1{0%{transform:translate(0,0) rotate(0deg);opacity:1}55%{transform:translate(24vw,-66vh) rotate(500deg);opacity:1}100%{transform:translate(32vw,4vh) rotate(900deg);opacity:0}}
@keyframes br1{0%{transform:translate(0,0) rotate(0deg);opacity:1}55%{transform:translate(-24vw,-66vh) rotate(-500deg);opacity:1}100%{transform:translate(-32vw,4vh) rotate(-900deg);opacity:0}}
@keyframes bl2{0%{transform:translate(0,0) rotate(0deg);opacity:1}55%{transform:translate(34vw,-56vh) rotate(500deg);opacity:1}100%{transform:translate(46vw,14vh) rotate(900deg);opacity:0}}
@keyframes br2{0%{transform:translate(0,0) rotate(0deg);opacity:1}55%{transform:translate(-34vw,-56vh) rotate(-500deg);opacity:1}100%{transform:translate(-46vw,14vh) rotate(-900deg);opacity:0}}
@keyframes bl3{0%{transform:translate(0,0) rotate(0deg);opacity:1}55%{transform:translate(9vw,-88vh) rotate(500deg);opacity:1}100%{transform:translate(12vw,-18vh) rotate(900deg);opacity:0}}
@keyframes br3{0%{transform:translate(0,0) rotate(0deg);opacity:1}55%{transform:translate(-9vw,-88vh) rotate(-500deg);opacity:1}100%{transform:translate(-12vw,-18vh) rotate(-900deg);opacity:0}}
.st-key-deck_keys{position:fixed;left:0;top:0;width:0;height:0;overflow:hidden}
.st-key-deck_view img,.st-key-deck_view video{position:fixed!important;left:0;top:0;width:100vw!important;height:100vh!important;max-width:none!important;max-height:none!important;object-fit:contain;background:#000;border-radius:0!important;z-index:40}
.st-key-deck_pre{position:fixed;left:-300vw;top:0;width:8px;height:8px;overflow:hidden}
.st-key-deck_hit button{position:fixed!important;left:0;top:0;width:100vw!important;height:100vh!important;opacity:0;z-index:45;border:0!important;cursor:pointer}
.st-key-deck_nav{position:fixed;right:1.4vw;bottom:1.6vh;width:9.5rem;z-index:60;opacity:.16;transition:opacity .2s}
.st-key-deck_nav:hover{opacity:1}
.st-key-deck_nav button{min-height:2.4rem;padding:.2rem .6rem;background:rgba(20,20,24,.78)!important;color:#fff!important;border:1px solid rgba(255,255,255,.35)!important;border-radius:8px}
.sc-deckno{position:fixed;left:1.4vw;bottom:1.8vh;z-index:60;font:600 clamp(.8rem,1vw,1.05rem) "Noto Sans KR",sans-serif;color:#fff;opacity:.35;pointer-events:none}
[data-testid="stAudio"],.st-key-aud_roll,.st-key-aud_win{position:fixed!important;left:-9999px!important;width:1px!important}
.st-key-sort_view iframe{position:fixed!important;left:0;top:0;width:100vw!important;height:100vh!important;border:0!important;z-index:50;background:#07061A}
</style>"""


# ───────────────────────── 그림(트리 · 산타 썰매 · 전구 줄) — 한 줄 SVG로 만들어 화면에 넣음
_TREE = (
    '<svg viewBox="0 0 120 160" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"{flip}>'
    '<defs><linearGradient id="g{u}" x1="0" y1="0" x2="1" y2="0"><stop offset="0.5" stop-color="#2E9479"></stop><stop offset="0.5" stop-color="#21705C"></stop></linearGradient>'
    '<filter id="f{u}" x="-150%" y="-150%" width="400%" height="400%"><feGaussianBlur stdDeviation="1.2" result="b"></feGaussianBlur><feMerge><feMergeNode in="b"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge></filter>'
    '<filter id="h{u}" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="12"></feGaussianBlur></filter></defs>'
    '<ellipse cx="60" cy="84" rx="50" ry="66" fill="#F2B45E" fill-opacity="0.28" filter="url(#h{u})"></ellipse>'
    '<ellipse cx="60" cy="147" rx="52" ry="3.5" fill="#000000" fill-opacity="0.25"></ellipse>'
    '<rect x="53" y="122" width="14" height="18" rx="2" fill="#9A6A45"></rect><path d="M53 128H67M53 134H67" stroke="#7A5032" stroke-width="1"></path>'
    '<path d="M60 70Q74 100 106 124Q96.8 132 87.6 124Q78.4 132 69.2 124Q60 132 50.8 124Q41.6 132 32.4 124Q23.2 132 14 124Q46 100 60 70Z" fill="url(#g{u})"></path>'
    '<path d="M27 117Q56 124 86 109" stroke="#0F3D33" stroke-width="0.7"></path>'
    '<circle cx="40" cy="111" r="2.6" fill="#D8394A"></circle><circle cx="82" cy="120" r="2.6" fill="#F5B83D"></circle><circle cx="64" cy="122" r="2.6" fill="#D8394A"></circle>'
    '<path d="M90 114V108.5A2.5 2.5 0 0 0 85 108.5" stroke="#FFFFFF" stroke-width="1.7"></path><path d="M90 114V108.5A2.5 2.5 0 0 0 85 108.5" stroke="#D8394A" stroke-width="1.7" stroke-dasharray="1.6 1.6" stroke-linecap="butt"></path>'
    '<path d="M60 50Q72 76 98 100Q88.5 108 79 100Q69.5 108 60 100Q50.5 108 41 100Q31.5 108 22 100Q48 76 60 50Z" fill="url(#g{u})"></path>'
    '<path d="M33 96Q60 102 81 89" stroke="#0F3D33" stroke-width="0.7"></path>'
    '<circle cx="36" cy="91" r="2.6" fill="#F5B83D"></circle><circle cx="76" cy="96" r="2.6" fill="#D8394A"></circle><circle cx="60" cy="86" r="2.6" fill="#F5B83D"></circle>'
    '<path d="M46 92V85.5A2.5 2.5 0 0 0 41 85.5" stroke="#FFFFFF" stroke-width="1.7"></path><path d="M46 92V85.5A2.5 2.5 0 0 0 41 85.5" stroke="#D8394A" stroke-width="1.7" stroke-dasharray="1.6 1.6" stroke-linecap="butt"></path>'
    '<path d="M60 32Q70 56 90 76Q82.5 83 75 76Q67.5 83 60 76Q52.5 83 45 76Q37.5 83 30 76Q50 56 60 32Z" fill="url(#g{u})"></path>'
    '<path d="M38 70Q58 76 76 64" stroke="#0F3D33" stroke-width="0.7"></path>'
    '<circle cx="44" cy="64" r="2.4" fill="#D8394A"></circle><circle cx="70" cy="72" r="2.4" fill="#F5B83D"></circle>'
    '<path d="M66 68V61.5A2.5 2.5 0 0 0 61 61.5" stroke="#FFFFFF" stroke-width="1.7"></path><path d="M66 68V61.5A2.5 2.5 0 0 0 61 61.5" stroke="#D8394A" stroke-width="1.7" stroke-dasharray="1.6 1.6" stroke-linecap="butt"></path>'
    '<path d="M60 16Q68 36 82 52Q74.67 58 67.33 52Q60 58 52.67 52Q45.33 58 38 52Q52 36 60 16Z" fill="url(#g{u})"></path>'
    '<path d="M49 44Q60 48 70 38" stroke="#0F3D33" stroke-width="0.7"></path>'
    '<circle cx="57" cy="30" r="2.2" fill="#F5B83D"></circle><circle cx="66" cy="48" r="2.2" fill="#D8394A"></circle>'
    '<g filter="url(#f{u})">'
    '<circle class="tw" cx="38.6" cy="119" r="1.4" fill="#FF6B6B"></circle>'
    '<circle class="tw" cx="50.4" cy="119" r="1.4" fill="#FFD166" style="animation-delay:.6s"></circle>'
    '<circle class="tw" cx="62.2" cy="117.5" r="1.4" fill="#6EC6FF" style="animation-delay:1.2s"></circle>'
    '<circle class="tw" cx="74" cy="114.2" r="1.4" fill="#8EE07A" style="animation-delay:1.8s"></circle>'
    '<circle class="tw" cx="46.1" cy="97.8" r="1.4" fill="#FFD166" style="animation-delay:.3s"></circle>'
    '<circle class="tw" cx="58.5" cy="97.25" r="1.4" fill="#FF9BD2" style="animation-delay:.9s"></circle>'
    '<circle class="tw" cx="70.1" cy="94.3" r="1.4" fill="#6EC6FF" style="animation-delay:1.5s"></circle>'
    '<circle class="tw" cx="47.9" cy="71.9" r="1.3" fill="#8EE07A" style="animation-delay:.4s"></circle>'
    '<circle class="tw" cx="57.5" cy="71.5" r="1.3" fill="#FF6B6B" style="animation-delay:1s"></circle>'
    '<circle class="tw" cx="66.9" cy="68.9" r="1.3" fill="#FFD166" style="animation-delay:1.6s"></circle>'
    '<circle class="tw" cx="56.1" cy="45.1" r="1.3" fill="#6EC6FF" style="animation-delay:.7s"></circle>'
    '<circle class="tw" cx="63.2" cy="43.1" r="1.3" fill="#FF9BD2" style="animation-delay:1.3s"></circle></g>'
    '<path class="pl" d="M60 1L62.23 6.93L68.56 7.22L63.61 11.17L65.29 17.28L60 13.8L54.71 17.28L56.39 11.17L51.44 7.22L57.77 6.93Z" fill="#F5B83D" filter="url(#f{u})"></path>'
    '<rect x="12" y="128" width="24" height="18" rx="1" fill="#2FA35F"></rect><path d="M24 128V146" stroke="#F5C542" stroke-width="2.2"></path>'
    '<path d="M24 128C20 123 16.5 126.5 24 128ZM24 128C28 123 31.5 126.5 24 128Z" fill="#F5C542"></path>'
    '<rect x="30" y="135" width="16" height="11" rx="1" fill="#F5C542"></rect><path d="M38 135V146" stroke="#FFFFFF" stroke-width="1.8"></path>'
    '<path d="M38 135C35 131 32 134 38 135ZM38 135C41 131 44 134 38 135Z" fill="#FFFFFF"></path>'
    '<rect x="62" y="139" width="12" height="7" rx="1" fill="#2FA35F"></rect><path d="M68 139V146" stroke="#F5C542" stroke-width="1.4"></path>'
    '<rect x="74" y="134" width="18" height="12" rx="1" fill="#D8394A"></rect><path d="M83 134V146" stroke="#F5C542" stroke-width="2"></path>'
    '<path d="M83 134C80 130 77 133 83 134ZM83 134C86 130 89 133 83 134Z" fill="#F5C542"></path>'
    '<rect x="92" y="124" width="16" height="22" rx="1" fill="#C22D45"></rect><path d="M100 124V146" stroke="#FFFFFF" stroke-width="2"></path>'
    '<path d="M100 124C96.5 119.5 93 123 100 124ZM100 124C103.5 119.5 107 123 100 124Z" fill="#FFFFFF"></path></svg>')

_STAR4 = 'l1 3.2 3.2 1-3.2 1-1 3.2-1-3.2-3.2-1 3.2-1z'
_SLEIGH = (
    '<svg viewBox="0 0 200 140" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<defs><filter id="fS" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="1.2" result="b"></feGaussianBlur><feMerge><feMergeNode in="b"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge></filter>'
    '<filter id="hS" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="14"></feGaussianBlur></filter></defs>'
    '<ellipse cx="100" cy="82" rx="96" ry="52" fill="#F2B45E" fill-opacity="0.22" filter="url(#hS)"></ellipse>'
    '<path d="M-34 138Q-6 132 10 116" stroke="#F5C542" stroke-width="2" stroke-dasharray="0.1 5"></path>'
    '<g filter="url(#fS)" fill="#F5C542">'
    f'<path class="tw" d="M-12 116{_STAR4}" style="animation-delay:.2s"></path><path class="tw" d="M18 126{_STAR4}" style="animation-delay:1.1s"></path>'
    f'<path class="tw" d="M104 28{_STAR4}" style="animation-delay:.6s"></path><path class="tw" d="M136 14{_STAR4}" style="animation-delay:1.6s"></path>'
    f'<path class="tw" d="M58 22{_STAR4}" style="animation-delay:1.3s"></path></g>'
    '<g transform="rotate(-8 100 90)">'
    '<path d="M66 74Q108 62 150 76" stroke="#E2B95C" stroke-width="1"></path><path d="M82 98Q115 92 147 85" stroke="#E2B95C" stroke-width="0.9"></path>'
    '<path d="M20 80Q16 64 24 58Q27 54 30 58Q38 64 34 80Z" fill="#3E7A4F"></path><path d="M23.5 59.5Q27 62 30.5 59.5" stroke="#F5C542" stroke-width="1.4"></path>'
    '<rect x="31" y="66" width="9" height="9" rx="0.8" fill="#F5C542"></rect><path d="M35.5 66V75" stroke="#D8394A" stroke-width="1.2"></path>'
    '<path d="M38 78Q38 62 48 60Q58 62 58 78Z" fill="#D8394A"></path><path d="M54 68Q61 70 66 74" stroke="#D8394A" stroke-width="5"></path>'
    '<circle cx="66.5" cy="74.3" r="2.6" fill="#1F5A3A"></circle><circle cx="48" cy="52" r="6" fill="#F2C9A8"></circle>'
    '<path d="M42 52Q42 65 48 65Q54 65 54 52Q51 56 48 56Q45 56 42 52Z" fill="#FFFFFF"></path>'
    '<circle cx="50.6" cy="51.4" r="0.85" fill="#2A1A12"></circle><circle cx="52.4" cy="53.6" r="1.1" fill="#E89A86"></circle>'
    '<path d="M42 49Q45 38 52 38Q58 39 60.5 46L55 49Q48 46.5 42 49Z" fill="#D8394A"></path>'
    '<path d="M41 49.5Q48 46 55.5 49.5L55.5 52.2Q48 48.8 41 52.2Z" fill="#FFFFFF"></path><circle cx="60.8" cy="46.6" r="2.3" fill="#FFFFFF"></circle>'
    '<path d="M12 66Q10 60 16 60Q22 60 22 66L22 78L64 78Q72 78 74 86L76 98Q76 104 70 104L26 104Q14 104 12 92Z" fill="#C22D45"></path>'
    '<path d="M22 80H63M14 92Q24 96 74 94" stroke="#F5C542" stroke-width="1.2"></path><circle cx="44" cy="91" r="3.2" stroke="#F5C542" stroke-width="1"></circle>'
    '<path d="M28 104V112M62 104V112" stroke="#F5C542" stroke-width="1.6"></path><path d="M6 112H74Q86 112 86 102Q86 96 81 97" stroke="#F5C542" stroke-width="2.2"></path>'
    '<path d="M126 86L116 96L108 100M130 88L124 100L120 108" stroke="#7A5032" stroke-width="3.2"></path>'
    '<path d="M156 86L166 96L168 104M152 88L156 100L162 106" stroke="#7A5032" stroke-width="3.2"></path>'
    '<circle cx="108" cy="100" r="1.7" fill="#3A2418"></circle><circle cx="120" cy="108" r="1.7" fill="#3A2418"></circle>'
    '<circle cx="168" cy="104" r="1.7" fill="#3A2418"></circle><circle cx="162" cy="106" r="1.7" fill="#3A2418"></circle>'
    '<path d="M117 77Q110 73 112 79Z" fill="#FFFFFF"></path><ellipse cx="140" cy="80" rx="24" ry="11" fill="#9A6A45"></ellipse>'
    '<ellipse cx="140" cy="86" rx="17" ry="4.5" fill="#C8996C"></ellipse><path d="M156 76Q162 62 168 56L175 60Q169 70 162 83Z" fill="#9A6A45"></path>'
    '<path d="M150 70Q153.5 80 150 90" stroke="#C22D45" stroke-width="3"></path><path d="M157 73Q163 76 170 66" stroke="#C22D45" stroke-width="3"></path>'
    '<circle cx="161" cy="75.6" r="1.9" fill="#F5C542"></circle><circle cx="165.4" cy="72.6" r="1.9" fill="#F5C542"></circle><circle cx="151.6" cy="80" r="1.6" fill="#F5C542"></circle>'
    '<path d="M170 48Q168 40 162 36M166 40Q164 36 165 33M162 36Q158 35 156 31M173 47Q174 39 178 34M175.6 39.4Q179 38 181 35M178 34Q178 30 176 28" stroke="#D9A867" stroke-width="1.7"></path>'
    '<ellipse cx="174" cy="55" rx="8" ry="5.5" transform="rotate(-20 174 55)" fill="#9A6A45"></ellipse>'
    '<path d="M167 50Q162.5 46 165 44Q169 47 169.5 50.5Z" fill="#7A5032"></path><ellipse cx="180.5" cy="57" rx="4.2" ry="3.1" fill="#C8996C"></ellipse>'
    '<circle cx="184.4" cy="56.4" r="1.6" fill="#3A2418"></circle><circle cx="172.2" cy="52.6" r="0.95" fill="#2A1A12"></circle></g></svg>')

_BULBS = ["#FFE7AE", "#FF6B6B", "#FFD166", "#6EC6FF", "#8EE07A"]


def tree_svg(uid: str, flip: bool = False) -> str:
    return _TREE.replace("{u}", uid).replace("{flip}", ' style="transform:scaleX(-1)"' if flip else "")


def garland_svg() -> str:
    """스크린 위쪽에 두 번 늘어진 전구 줄(전구마다 다른 박자로 반짝임)."""
    dots = []
    for k in range(19):
        x = 59 * (k + 1)
        t = (x % 590) / 590
        y = 6 + 116 * t * (1 - t)
        dots.append(f'<circle class="tw" cx="{x}" cy="{y:.1f}" r="3.4" fill="{_BULBS[k % 5]}" style="animation-delay:{(k * 0.37) % 2.2:.2f}s"></circle>')
    return ('<div class="sc-garland"><svg viewBox="0 0 1180 44" fill="none" aria-hidden="true"><defs><filter id="fG" x="-300%" y="-300%" width="700%" height="700%">'
            '<feGaussianBlur stdDeviation="2.4" result="b"></feGaussianBlur><feMerge><feMergeNode in="b"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge></filter></defs>'
            '<path d="M0 6Q295 64 590 6Q885 64 1180 6" stroke="#8E6F45" stroke-width="1.2"></path><g filter="url(#fG)">' + "".join(dots) + "</g></svg></div>")


STAR_SMALL = '<svg aria-hidden="true" width="11" height="11" viewBox="0 0 12 12"><path d="M6 0l1.4 4.6L12 6l-4.6 1.4L6 12l-1.4-4.6L0 6l4.6-1.4z" fill="#D6B676"></path></svg>'


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
    md(BASE_CSS + '<style>.stApp{background:#6B1F2C}</style>')   # 첫 화면만 축제 분위기(진한 와인색)
    S = store.get_settings()
    pick = st.session_state.get("pick")
    if not pick:
        md('<div class="mx mx-hero"><div class="mx-orn">WINTER PREMIERE</div>'
           f'<div style="width:165px;height:220px;margin-top:.8rem">{tree_svg("hp")}</div>'
           '<div class="mx-h1" style="margin-top:.9rem;font-size:2.1rem">모션 영상 의뢰</div>'
           f'<div class="mx-subt">{ESC(S["event"])}</div>'
           '<div class="mx-note" style="max-width:310px;margin-top:.5rem">분임별로 영상 기획서를 쓰고, 완성된 영상을 여기서 바로 봅니다.<br>'
           '우리 분임을 고르고 비밀번호를 넣으면 시작돼요.</div></div>')
        md('<div class="mx mx-orn sub">우리 분임을 골라 주세요</div>')
        # 영화표 버튼: 분임마다 'ADMIT ONE · No. 01' 한 줄을 위에 붙임
        md("<style>" + "".join(f'.st-key-pick_{g} button::before{{content:"ADMIT ONE · No. {g:02d}"}}'
                               for g in range(1, store.N_GROUPS + 1)) + "</style>")
        for row in range(0, store.N_GROUPS, 2):
            gs = [g for g in (row + 1, row + 2) if g <= store.N_GROUPS]
            with st.container(key=f"row_pick_{row}"):
                cols = st.columns(len(gs))
                for g, col in zip(gs, cols):
                    if col.button(S["names"][g - 1], key=f"pick_{g}", use_container_width=True):
                        st.session_state["pick"] = g
                        st.rerun()
        find_my_group(S)
        md('<div class="mx mx-foot">Merry Christmas &amp; Happy New Year</div>')
        return
    md(f'<div class="mx mx-hero"><div class="mx-orn">WINTER PREMIERE</div>'
       f'<div class="mx-h1" style="margin-top:.6rem">모션 영상 의뢰</div><div class="mx-subt">{ESC(S["event"])}</div></div>')
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


def find_my_group(S: dict):
    """배정식으로 분임을 나눈 뒤: 이름을 넣으면 내 분임을 알려 줌(배정식을 스크린에 공개한 뒤에만 보임)."""
    T = store.team_get()
    if not T["seq"] or T["show_mode"] not in ("play", "final"):
        return
    md('<div class="mx mx-orn sub">내 분임을 모르겠다면</div>')
    with st.form("find_me"):
        nm = st.text_input("🔮 이름을 넣으면 우리 분임을 알려 드려요", max_chars=20, placeholder="예: 홍길동")
        ok = st.form_submit_button("내 분임 찾기", use_container_width=True)
    if ok:
        if store.team_find(nm):
            st.session_state["found"] = re.sub(r"\s+", "", nm)
        else:
            st.session_state.pop("found", None)
            st.error("명단에 없는 이름이에요. 띄어쓰기 없이 다시 써 보거나 관리팀에 알려 주세요.")
    f = st.session_state.get("found")
    g = store.team_find(f) if f else None          # 매번 다시 찾음(관리팀이 다시 섞어도 맞게)
    if g:
        gn = S["names"][g - 1]
        md(f'<div class="mx mx-card" style="text-align:center"><div class="mx-note">{ESC(f)}님의 분임</div>'
           f'<div class="mx-h1">{ESC(gn)}</div><div class="mx-note">아래 버튼이나 위의 {ESC(gn)} 표를 눌러 들어가세요</div></div>')
        if st.button(f"🎟 {gn} 들어가기", key="found_go", type="primary", use_container_width=True):
            st.session_state["pick"] = g
            st.session_state.pop("found", None)
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
    if store.vote_state() == "open":
        md(f'<div class="mx mx-warn" style="border-style:solid;font-size:1.05rem">🗳 <b>투표가 열렸어요!</b> 각자 휴대폰으로 '
           f'<a href="{ESC(base_url())}/?view=vote" target="_blank"><b>투표하러 가기</b></a> (스크린의 QR을 찍어도 돼요)</div>')
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
        return (R["status"], len(store.results(g)), len(store.messages(g)), store.session_token(g), store.vote_state())
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

    md('<div class="mx mx-note" style="font-size:.85rem;opacity:.85">한 분임에서 두 사람이 따로 썼다면, 화면을 새로 고치면 서로 쓴 내용이 합쳐져 보여요.</div>')
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


# ───────────────────────── 투표 화면(각자 휴대폰)
def vote_view():
    md(BASE_CSS)
    S = store.get_settings()
    stt = store.vote_state()
    md(f'<div class="mx mx-card"><div class="mx-ev">{ESC(S["event"])}</div><div class="mx-h1">🗳 광고제 투표</div>'
       '<div class="mx-note">1인 1표 · 내 이름으로 · 우리 분임 작품은 빼고 한 편</div></div>')
    if store.rehearsal_info().get("roster"):
        md('<div class="mx mx-note">🧪 리허설 중이에요. <b>연습1-1</b>, <b>연습2-3</b>처럼 연습 명단 이름으로 투표해 보세요.</div>')

    @st.fragment(run_every=4)
    def watch():
        if store.vote_state() != stt:          # 열리거나 마감되면 화면을 새로 그림
            st.rerun()

    done = st.session_state.get("vote_done")
    if done:
        md(f'<div class="mx mx-card" style="text-align:center"><div class="mx-h1">투표 완료! 🎉</div>'
           f'<div class="mx-note"><b>{ESC(done)}</b> 님, 고마워요. 결과 발표를 기다려 주세요.</div></div>')
        return
    if stt != "open":
        md('<div class="mx mx-warn">' + ("투표가 마감됐어요. 결과 발표를 기다려 주세요." if stt == "closed" else
                                         "아직 투표 시간이 아니에요. 시사회가 끝나면 열려요.<br>이 화면을 켜 두면 열릴 때 자동으로 바뀌어요.") + "</div>")
        watch()
        return
    who = st.session_state.get("vote_who")
    if not who:
        free = not store.roster_total()          # 명단이 없으면: 이름 + 우리 분임을 직접 고름
        md('<div class="mx mx-sec"><i>1</i>' + ("내 이름과 우리 분임" if free else "내 이름") + '</div>')
        with st.form("vote_name"):
            nm = st.text_input("내 이름", max_chars=20, placeholder="예: 김민수")
            my_g = (st.radio("우리 분임 (이 분임 작품은 투표 목록에서 빠져요)", list(range(1, store.N_GROUPS + 1)) + [0], index=None, key="vote_myg",
                             horizontal=True, format_func=lambda x: S["names"][x - 1] if x else "분임 없음(국장님 등)") if free else None)
            ok = st.form_submit_button("다음 →", type="primary", use_container_width=True)
        md('<div class="mx mx-note">' + ("본인 이름을 정확히 써 주세요. 같은 이름으로는 한 번만 투표할 수 있어요." if free else
                                         "분임 명단에 등록된 이름 그대로 써 주세요(띄어쓰기는 상관없어요). 명단에 없다고 나오면 운영팀에 말해 주세요.") + "</div>")
        if ok and free:
            nm2 = " ".join(str(nm or "").split())
            if len(store.name_key(nm2)) < 2:
                st.error("이름을 두 글자 이상 써 주세요.")
            elif my_g is None:
                st.error("우리 분임을 골라 주세요.")
            elif store.has_voted(nm2):
                st.error("이미 투표한 이름이에요. 동명이인이면 '김민수B'처럼 구분해서 써 주세요.")
            else:
                st.session_state["vote_who"] = [nm2, int(my_g)]
                st.rerun()
        elif ok:
            found = store.find_voter(nm)
            if not found:
                st.error("명단에 없는 이름이에요. 이름을 다시 확인해 주세요.")
            elif store.has_voted(found[0]):
                st.error("이미 투표한 이름이에요. 내가 한 게 아니라면 운영팀에 말해 주세요.")
            else:
                st.session_state["vote_who"] = [found[0], found[1]]
                st.rerun()
        watch()
        return
    name, vg = who[0], int(who[1])
    cands = store.vote_candidates(vg, S)
    titles = {g: _title(g) for g in cands}
    md(f'<div class="mx mx-sec"><i>2</i>작품 고르기</div><div class="mx-note"><b>{ESC(name)}</b> 님 ({ESC(_glabel(vg, S))}) · '
       '마음에 드는 작품 한 편을 골라 주세요.' + (" 우리 분임 작품은 목록에 없어요." if vg else "") + "</div>")
    if not cands:
        md('<div class="mx mx-warn">고를 수 있는 작품이 아직 없어요. 운영팀에 말해 주세요.</div>')
    else:
        with st.form("vote_pick_form"):
            pick = st.radio("작품", cands, index=None, key="vote_pick", label_visibility="collapsed",
                            format_func=lambda g: f"{S['names'][g - 1]} · {titles[g]}" if titles[g] else S["names"][g - 1])
            ok = st.form_submit_button("🗳 이 작품에 투표하기", type="primary", use_container_width=True)
        if ok:
            if pick is None:
                st.error("작품을 하나 골라 주세요.")
            elif act(store.cast_vote, name, int(pick), vg):
                st.session_state["vote_done"] = name
                st.session_state.pop("vote_who", None)
                st.rerun()
    if st.button("← 이름 다시 쓰기", key="vote_back"):
        st.session_state.pop("vote_who", None)
        st.rerun()
    watch()


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
    bgm_player(S)
    if not secret("admin_pin"):
        st.error("Streamlit 설정(Secrets)에 admin_pin 이 없어서 관리 화면 PIN이 임시로 0000입니다. "
                 "배포 화면의 Settings → Secrets에 admin_pin = \"7391\" 처럼 관리팀만 아는 숫자를 넣어 주세요.")
    reh = store.rehearsal_info()
    if reh:
        st.warning(f"🧪 리허설 데이터가 들어 있어요({kst(reh.get('at'))} 채움). 행사 전에 꼭 [🧪 리허설] 탭에서 [리허설 끝: 모두 지우기]를 눌러 주세요.")
    tabs = st.tabs(["📋 진행 현황", "🪄 팀 배정", "📽 발표", "🎞 시사회", "🗳 투표", "🔑 분임 비밀번호·QR", "⚙️ 설정", "💾 백업·초기화", "🧪 리허설"])
    with tabs[0]:
        overview()
        md("<hr>")
        detail()
    with tabs[1]:
        team_panel()
    with tabs[2]:
        deck_panel()
    with tabs[3]:
        premiere_panel()
    with tabs[4]:
        vote_panel()
    with tabs[5]:
        pw_panel()
    with tabs[6]:
        settings_panel()
    with tabs[7]:
        backup_panel()
    with tabs[8]:
        rehearsal_panel()


# ───────────────────────── 리허설(연습용 데이터)
def rehearsal_panel():
    reh = store.rehearsal_info()
    roster = store.get_roster()
    total = sum(len(v) for v in roster.values())
    url = base_url() or "앱주소"
    md('<div class="mx mx-note">영상을 만들지 않고도 <b>시사회 → 투표 → 결과 발표</b>를 처음부터 끝까지 연습하는 곳입니다. '
       '버튼 하나로 7개 분임에 연습용 기획서(제목·감독·발표자·발표 한마디)와 <b>샘플 영상</b>(7초, 소리 확인용 삐 소리)이 들어갑니다.</div>')
    md(f'<div class="mx mx-card mx-note"><b>리허설 순서</b><br>'
       f'① 아래 <b>[🧪 연습용 데이터 채우기]</b><br>'
       f'② 스크린 PC에서 <b>{ESC(url)}/?view=screen</b> 열고 화면 한 번 클릭<br>'
       f'③ <b>[🎞 시사회]</b> 탭에서 [▶ 다음] → 분임 소개 → 샘플 영상(소리 확인) → … → 마지막 뒤 투표 화면(QR)<br>'
       f'④ 휴대폰으로 QR을 찍고 <b>연습1-1</b>, <b>연습2-3</b>처럼 연습 명단 이름으로 투표해 보기 (사람이 적으면 아래 <b>[🎲 연습용 표 채우기]</b>)<br>'
       f'⑤ <b>[🗳 투표]</b> 탭에서 [⏹ 투표 마감] → [🏆 결과 발표 화면 띄우기] 두구두구 → [🎉 최우수상 공개!]<br>'
       f'⑥ 끝나면 <b>[🧹 리허설 끝: 모두 지우기]</b></div>')
    if reh:
        st.info(f"지금 리허설 데이터가 들어 있어요({kst(reh.get('at'))} 채움" + (", 연습 명단 사용 중" if reh.get("roster") else ", 등록한 명단 그대로") + ").")
    default_roster = (not total) or bool(reh.get("roster"))
    roster_too = st.checkbox("투표 명단도 연습 명단으로 채우기 (연습1-1 ~ 연습7-8, 연습국장 · 끄면 자유 입력으로 연습)", value=default_roster, key="rh_roster")
    if total and not reh.get("roster"):
        md(f'<div class="mx mx-note">지금 등록된 명단 {total}명이 있어요. <b>체크를 끄면</b> 그 명단으로 투표 연습을 하고(리허설 뒤에도 명단은 남음), '
           '<b>체크하면</b> 연습 명단으로 바뀌고 리허설을 끝낼 때 지워집니다(그때는 명단을 다시 등록해야 해요).</div>')
    if confirm_button("🧪 연습용 데이터 채우기", "rh_fill", "지금 들어 있는 기획서·결과물·대화·투표·분임 비밀번호를 모두 지우고 7개 분임을 연습용으로 채웁니다. "
                      "(행사 이름·분임 이름 같은 설정은 남습니다)"):
        store.fill_rehearsal(bool(roster_too))
        st.success("연습용 데이터를 채웠습니다. [🎞 시사회] 탭에서 [▶ 다음]을 눌러 보세요.")
    if not os.path.exists(store.REHEARSAL_SAMPLE):
        st.caption("샘플 영상 파일(rehearsal_sample.mp4)이 저장소에 없어서 영상 대신 그림이 들어갑니다. 소리까지 확인하려면 app.py 옆에 그 파일을 올려 주세요.")
    md("<hr>")
    if st.button("🎲 연습용 표 채우기 (아직 안 한 명단의 80%가 아무 작품에나 투표)", key="rh_votes", use_container_width=True, disabled=not total):
        n = store.simulate_votes(0.8)
        st.success(f"표 {n}개를 넣었습니다. [🗳 투표] 탭에서 마감 → 결과 발표를 연습해 보세요.")
    md("<hr>")
    if confirm_button("🧹 리허설 끝: 모두 지우기", "rh_end", "기획서·결과물·대화·투표·분임 비밀번호를 모두 지웁니다"
                      + (" (연습 명단도 지웁니다)." if reh.get("roster") else ". 등록한 명단과 설정은 남습니다.")):
        had_roster = bool(reh.get("roster"))
        store.reset_all()
        st.success("모두 지웠습니다. 이제 실제 행사를 시작할 수 있어요." + (" 연습 명단이 지워졌으니 [🗳 투표] 탭에서 실제 명단을 등록해 주세요." if had_roster else ""))


def bgm_player(S: dict):
    """관리 화면 맨 위 배경음악(유튜브). 다른 탭을 눌러도 이 자리는 그대로라 계속 재생됩니다."""
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([\w-]{11})", S.get("bgm") or "")
    if not m:
        return
    with st.container(key="row_bgm"):
        c1, c2 = st.columns([1.2, 3], vertical_alignment="center")
        with c1:
            st.video(f"https://www.youtube.com/watch?v={m.group(1)}")
        c2.markdown('<div class="mx mx-note">🎵 <b>배경음악</b> — ▶을 누르면 나와요. 다른 탭을 눌러도 계속 나오고, 이 창을 새로 고치거나 닫으면 멈춰요. '
                    '음악은 [⚙️ 설정]에서 바꾸거나 지울 수 있어요.</div>', unsafe_allow_html=True)


# ───────────────────────── 팀 배정(마법의 분임 배정식)
SORT_COLORS = store.TEAM_COLORS      # 1~7분임 깃발 색(팀 배정 엑셀 머리글 색과 같음)
SORT_MODES = {"idle": "분임 배정식 · 🔮 준비 화면(시작 전)", "play": "분임 배정식 · 🪄 진행", "final": "분임 배정식 · ✅ 결과"}


def sort_secs(n: int) -> float:
    """배정식 길이(초): 스크린 그림(SORT_HTML)의 일정표와 같은 계산(이름이 다 꽂힐 때까지)."""
    calls, tc, end = min(4, n), 7.6, 7.6
    for k in range(n):
        end = max(end, tc + (.5 if k < calls else 0) + .82)
        tc += 1.3 if k < calls else max(.2, .72 * .85 ** (k - calls))
    return end + .6


def team_grid_html(S: dict, T: dict) -> str:
    cards = []
    for g in range(1, store.N_GROUPS + 1):
        ns = sorted(T["groups"].get(g, []))
        cards.append(f'<div class="tm-card" style="border-top:6px solid {SORT_COLORS[(g - 1) % len(SORT_COLORS)]}">'
                     f'<div class="tm-h"><b>{ESC(S["names"][g - 1])}</b><span>{len(ns)}명</span></div>'
                     f'<div class="tm-n">{"<br>".join(ESC(n) for n in ns) or "-"}</div></div>')
    return '<div class="tm-grid">' + "".join(cards) + "</div>"


def _tm_done(msg: str):
    st.session_state["tm_msg"] = msg
    st.rerun()


def team_panel():
    S = store.get_settings()
    T = store.team_get()
    people = store.team_people()
    scr = store.screen_get()
    on = scr["mode"] == "sort"
    has = bool(T["seq"])
    url = base_url() or "앱주소"
    md('<div class="mx mx-note">참가자 <b>이름만</b> 넣으면 순서를 무작위로 섞어 <b>7개 분임</b>(인원 차이 최대 1명)으로 나누고, '
       f'스크린({ESC(url)}/?view=screen)에서 <b>마법의 분임 배정식</b>으로 공개합니다. 이름이 마법진 소용돌이에 섞였다가 분임 깃발로 하나씩 날아가 꽂혀요.<br>'
       '배정하면 <b>투표 명단</b>도 이 배정대로 바뀌고(내 분임 작품에는 투표 못 함), 맨 아래 <b>🌙 저녁 세션</b> 칸에서 분임별 명단을 복사해 '
       '오락실 앱에 붙이면 저녁에도 같은 팀으로 진행됩니다.</div>')
    msg = st.session_state.pop("tm_msg", None)
    if msg:
        st.success(msg)

    # ① 참가자 명단
    md(f'<div class="mx mx-sec"><i>1</i>참가자 명단 <span style="font-size:1rem;color:#CDB8A6">{len(people)}명 저장됨</span></div>')
    with st.form("tm_people"):
        txt = st.text_area("한 줄에 한 명 · 엑셀에서 이름 칸을 통째로 복사해 붙여도 돼요(‘6급’·‘성명’ 같은 칸은 저절로 빠지고, ‘양 현’처럼 띄어 쓴 이름은 붙여서 저장)",
                           "\n".join(people), height=240)
        if st.form_submit_button("👥 참가자 명단 저장", type="primary", use_container_width=True):
            try:
                n = store.save_team_people(txt)
                _tm_done(f"참가자 {n}명을 저장했습니다." + (" 이미 나눈 배정과 다르면 아래 안내를 보고 다시 섞거나 한 명씩 넣고 빼 주세요." if has else ""))
            except store.StoreError as e:
                st.error(str(e))
    if has:
        done = {store.name_key(n) for n, _g in T["seq"]}
        pk = {store.name_key(n) for n in people}
        new = [n for n in people if store.name_key(n) not in done]
        gone = [n for n, _g in T["seq"] if store.name_key(n) not in pk]
        if new or gone:
            st.warning("참가자 명단과 지금 배정이 달라요. " + (f"배정 안 된 사람: {', '.join(new)}. " if new else "")
                       + (f"명단에서 빠진 사람: {', '.join(gone)}. " if gone else "")
                       + "② [🔀 다시 섞기]로 새로 나누거나, [✏️ 현장 변경]에서 한 명씩 넣고 빼 주세요.")

    # ② 무작위로 나누기
    md('<div class="mx mx-sec"><i>2</i>무작위로 나누기</div>')
    if not has:
        md('<div class="mx mx-note">누가 어느 분임이 될지는 <b>컴퓨터가 무작위로</b> 정하고, 남는 인원이 어느 분임에 갈지도 무작위예요. '
           '결과는 여기서 먼저 볼 수 있고, 스크린에는 ③에서 배정식을 시작할 때 공개됩니다. '
           '<b>미리 보지 않고</b> 모두와 함께 보고 싶으면 이 버튼 없이 ③의 [🪄 배정식 시작!]을 바로 누르세요(그때 자동으로 나눔).</div>')
        if st.button(f"🪄 무작위로 7개 분임 나누기 ({len(people)}명)", key="tm_assign", type="primary", use_container_width=True,
                     disabled=len(people) < store.N_GROUPS):
            if act(store.team_assign):
                _tm_done("나눴습니다. 결과를 확인하고 ③에서 스크린 배정식을 시작하세요.")
    else:
        sizes = [len(T["groups"].get(g, [])) for g in range(1, store.N_GROUPS + 1)]
        md(f'<div class="mx mx-card"><div class="mx-note">배정 완료 · {kst(T["at"])}'
           + (" · 스크린에 공개함" if T["show_mode"] in ("play", "final") else " · 아직 스크린에 공개 전") + '</div>'
           f'<div class="mx-h1" style="font-size:1.4rem">{sum(sizes)}명 → ' + "·".join(str(x) for x in sizes) + "명</div></div>")
        with st.expander("배정 결과 보기 (관리팀만 · 스크린에는 배정식 때 공개)", expanded=T["show_mode"] in ("play", "final")):
            md(team_grid_html(S, T))
        shown = T["show_mode"] in ("play", "final")
        voted = len(store.voters())
        with st.container(key="row_tm_ctl"):
            c1, c2 = st.columns(2)
            with c1:
                if shown or voted:
                    warn = ("이미 스크린에 공개한 배정을 버리고 새로 섞습니다. " if shown else "") + \
                           (f"이미 {voted}명이 투표했어요(그 표는 예전 분임 기준으로 남음). " if voted else "") + "새 배정은 스크린 '준비 화면'으로 돌아갑니다."
                    if confirm_button("🔀 다시 섞기", "tm_shuffle", warn) and act(store.team_assign):
                        _tm_done("새로 섞었습니다. ③에서 배정식을 다시 시작하세요.")
                elif st.button("🔀 다시 섞기", key="tm_shuffle_now", use_container_width=True):
                    if act(store.team_assign):
                        _tm_done("새로 섞었습니다.")
            with c2:
                if st.button("↩ 되돌리기 (바로 전 배정)", key="tm_undo", use_container_width=True, disabled=not T["hist"]):
                    if store.team_undo():
                        _tm_done("바로 전 배정으로 되돌렸습니다.")

    # ③ 스크린에서 배정식
    md('<div class="mx mx-sec"><i>3</i>스크린에서 배정식</div>')
    secs = round(sort_secs(len(T["seq"]) or len(people)))
    now_lab = SORT_MODES.get(T["show_mode"], "분임 배정식") if on else _step_label(scr, S)
    if on and T["show_mode"] == "play" and T["show_at"] and time.time() - T["show_at"] / 1000 > sort_secs(len(T["seq"])) + 1:
        now_lab = "분임 배정식 · ✅ 끝남(결과 화면)"
    md(f'<div class="mx mx-card"><div class="mx-note">지금 스크린</div><div class="mx-h1" style="font-size:1.5rem">📺 {ESC(now_lab)}</div></div>')
    md('<div class="mx mx-note">순서: <b>[🔮 준비 화면]</b>을 띄워 두고 진행자가 안내 → <b>[🪄 배정식 시작!]</b> '
       f'(약 {secs}초 · 효과음) → 끝나면 결과가 그대로 남아요. 모두 깃발에서 내 이름을 찾아 분임 자리로!<br>'
       '· 스크린 PC 화면을 <b>미리 한 번 클릭</b>해 두면 효과음이 나요(안 나면 스크린 오른쪽 아래 <b>🔈 소리 켜기</b>).<br>'
       '· 스크린을 새로 고쳐도 끝났으면 결과가, 하는 중이면 그 자리부터 이어서 나와요. 다른 화면으로 넘어가려면 [⏹ 대기 판으로] 또는 다른 탭 버튼.</div>')
    with st.container(key="row_tm_scr1"):
        c1, c2 = st.columns(2)
        if c1.button("🔮 준비 화면 띄우기", key="tm_idle", use_container_width=True, disabled=on and T["show_mode"] == "idle"):
            if act(store.team_show, "idle"):
                st.rerun()
        playing = on and T["show_mode"] == "play"
        if c2.button("🪄 배정식 처음부터 다시" if playing else "🪄 배정식 시작!", key="tm_play", type="primary", use_container_width=True,
                     disabled=not has and len(people) < store.N_GROUPS):
            if (has or act(store.team_assign)) and act(store.team_show, "play"):
                st.rerun()
    with st.container(key="row_tm_scr2"):
        c1, c2 = st.columns(2)
        if c1.button("⏭ 결과만 바로 보기", key="tm_final", use_container_width=True, disabled=not has or (on and T["show_mode"] == "final")):
            if act(store.team_show, "final"):
                st.rerun()
        if c2.button("⏹ 대기 판으로", key="tm_off", use_container_width=True, disabled=not on):
            _go({"mode": "board"})
    if not has:
        return

    # ④ 현장 변경
    with st.expander("✏️ 현장 변경 · 늦게 온 사람 / 빠진 사람 / 이름 오타"):
        md('<div class="mx mx-note">바꾸면 배정·투표 명단·스크린 결과 화면에 바로 반영돼요. 늦게 온 사람은 <b>인원이 가장 적은 분임</b>에 들어갑니다(같으면 무작위).</div>')
        with st.form("tm_add", clear_on_submit=True):
            nm = st.text_input("늦게 온 사람 이름", max_chars=20)
            if st.form_submit_button("➕ 넣기", use_container_width=True):
                try:
                    g = store.team_add(nm)
                    _tm_done(f"{nm.strip()} → {S['names'][g - 1]}에 넣었습니다.")
                except store.StoreError as e:
                    st.error(str(e))
        names = sorted(n for n, _g in T["seq"])
        c1, c2 = st.columns(2)
        with c1:
            rm = st.selectbox("빠진 사람", ["(고르기)"] + names)
            if rm != "(고르기)" and confirm_button("➖ 배정에서 빼기", "tm_rm", f"{rm} 님을 배정과 투표 명단에서 뺍니다."):
                g = store.team_remove(rm)
                _tm_done(f"{rm} 님을 {S['names'][g - 1]}에서 뺐습니다." if g else "이미 빠져 있어요.")
        with c2:
            with st.form("tm_rename", clear_on_submit=True):
                old = st.selectbox("이름 고칠 사람", names)
                new = st.text_input("바른 이름", max_chars=20)
                if st.form_submit_button("이름 고치기", use_container_width=True):
                    try:
                        store.team_rename(old, new)
                        _tm_done(f"{old} → {new.strip()}(으)로 고쳤습니다.")
                    except store.StoreError as e:
                        st.error(str(e))

    # ⑤ 저녁 세션(오락실)
    md('<div class="mx mx-sec">🌙 저녁 세션(오락실)에 같은 팀 넣기</div>')
    st.download_button("📥 팀 배정 엑셀 내려받기 (.xlsx)", store.team_xlsx(S), file_name=f"분임배정_{kst(T['at'], '%m%d_%H%M')}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="tm_xlsx", type="primary", use_container_width=True)
    md('<div class="mx mx-note"><b>엑셀로 한 번에</b>: 오락실 앱(<b>수정판 27</b>부터) 운영 화면 → <b>[01 · 팀명 / 구호]</b> → <b>[📂 엑셀로 명단 불러오기]</b> → 이 파일 고르기 '
       '→ 7개 분임 팀원 명단이 한꺼번에 채워지고 저장돼요(팀명·구호는 그대로).<br>'
       '엑셀에는 <b>분임 명단</b>(분임번호·분임·이름, 한 줄에 한 명) 시트와 인쇄용 <b>한눈에 보기</b>(분임별 칸) 시트가 있어요. 엑셀에서 이름을 고쳐 저장한 파일도 그대로 불러올 수 있어요.<br>'
       '<b>복사로</b>(파일을 내려받을 수 없는 PC): 각 분임 칸의 <b>[팀원 명단 (선택)]</b>을 열고, 아래 상자 오른쪽 위 <b>복사</b> 버튼으로 복사해 '
       '<b>같은 번호</b> 분임 칸에 붙여 넣기 → 7개 다 넣은 뒤 <b>[팀 정보 저장]</b>. (오락실 앱도 1분임~7분임 순서 그대로예요)</div>')
    cols = st.columns(4)
    for i, g in enumerate(range(1, store.N_GROUPS + 1)):
        with cols[i % 4]:
            ns = sorted(T["groups"].get(g, []))
            st.caption(f"{g}분임 · {S['names'][g - 1]} · {len(ns)}명" if S["names"][g - 1] != f"{g}분임" else f"{g}분임 · {len(ns)}명")
            st.code("\n".join(ns) or " ", language=None)
    with st.expander("📋 전체 명단 한 번에 복사 (단톡방 공지용)"):
        st.code("\n".join(f"[{S['names'][g - 1]}] " + ", ".join(sorted(T["groups"].get(g, []))) for g in range(1, store.N_GROUPS + 1)), language=None)
    md("<hr>")
    if confirm_button("🧹 배정 지우기 (연습한 뒤에)", "tm_clear", "배정과 투표 명단의 1~7분임 칸을 지웁니다. 참가자 명단은 남아요."):
        store.team_clear()
        _tm_done("배정을 지웠습니다.")


# ───────────────────────── 시사회 진행
def _step_label(step: dict, S: dict) -> str:
    m, g = step["mode"], step.get("g")
    if m == "intro":
        return f"{S['names'][g - 1]} 소개 화면"
    if m == "play":
        return f"{S['names'][g - 1]} 영상 틀기"
    if m == "end":
        return "투표 화면 (QR)"
    if m == "result":
        return "투표 결과 발표 화면"
    if m == "deck":
        return "발표 자료"
    if m == "sort":
        return "분임 배정식"
    return "대기 판"


def _go(step: dict):
    if act(store.screen_go, step):
        if step.get("mode") == "end" and store.vote_state() == "ready":
            store.set_vote_state("open")          # 투표 QR을 띄우면 투표도 같이 열림
        st.rerun()


@st.fragment(run_every=4)
def deck_panel():
    steps = deck_steps()
    if not steps:
        md('<div class="mx mx-note">발표 자료 파일이 없어요. GitHub 저장소에 <b>deck</b> 폴더(슬라이드 그림·영상·deck.json)를 그대로 올려 주세요.</div>')
        return
    S = store.get_settings()
    scr = store.screen_get()
    on = scr["mode"] == "deck"
    n = min(scr["n"], len(steps) - 1) if on else 0
    total = steps[-1].get("slide", len(steps))
    lab = lambda i: f'{steps[i].get("slide", i + 1)}장 · {steps[i]["title"]}'
    md('<div class="mx mx-note">PPT 대신 <b>스크린 화면</b>(' + ESC(base_url() or "앱주소") + '/?view=screen)에 발표 자료를 띄웁니다. '
       '넘기기는 여기 버튼, 또는 스크린 PC에서 <b>→ / ← · 스페이스 · 프레젠터 리모컨 · 화면 클릭</b> 아무거나 쓰면 돼요. '
       '영상이 있는 장(2장·3장)은 한 번 더 넘기면 영상이 화면 가득 나오고, 영상이 끝나면 다시 넘기면 됩니다. '
       '발표가 끝나면 <b>[🎞 시사회]</b> 탭으로 넘어가세요.</div>')
    if not on:
        md(f'<div class="mx mx-card" style="margin-top:.6rem"><div class="mx-note">지금 스크린</div><div class="mx-h1" style="font-size:1.5rem">📺 {ESC(_step_label(scr, S))}</div>'
           f'<div class="mx-note">발표 자료 {total}장 준비됨</div></div>')
        start = st.selectbox("시작할 장", list(range(len(steps))), format_func=lab, key="dk_start")
        if st.button("📽 발표 자료 띄우기", key="dk_on", type="primary", use_container_width=True):
            _go({"mode": "deck", "n": start})
        return
    x = steps[n]
    nx = steps[n + 1] if n + 1 < len(steps) else None
    md(f'<div class="mx mx-card" style="margin-top:.6rem"><div class="mx-note">지금 스크린 · 📽 발표 자료</div>'
       f'<div class="mx-h1" style="font-size:1.5rem">{x.get("slide", n + 1)} / {total}장 · {ESC(x["title"])}</div></div>')
    with st.container(key="row_dk_nav"):
        c1, c2 = st.columns(2)
        if c1.button("◀ 이전", key="dk_prev", use_container_width=True, disabled=n == 0):
            _go({"mode": "deck", "n": n - 1})
        if c2.button("다음 ▶", key="dk_next", type="primary", use_container_width=True, disabled=nx is None):
            _go({"mode": "deck", "n": n + 1})
    with st.container(key="row_dk_ctl"):
        c1, c2 = st.columns(2)
        if c1.button("⏮ 처음으로", key="dk_first", use_container_width=True, disabled=n == 0):
            _go({"mode": "deck", "n": 0})
        if c2.button("⏹ 대기 판으로", key="dk_off", use_container_width=True):
            _go({"mode": "board"})
    with st.container(key="row_dk_view"):
        c1, c2 = st.columns([3, 2])
        with c1:
            md('<div class="mx mx-note">지금 화면</div>')
            if x.get("video"):
                md(f'<div class="mx mx-card mx-note">🎬 {ESC(x["title"])}<br>스크린에서 영상이 나오는 중</div>')
            else:
                st.image(x["path"], use_container_width=True)
        with c2:
            md('<div class="mx mx-note">다음</div>')
            if nx is None:
                md('<div class="mx mx-card mx-note">마지막 장이에요</div>')
            elif nx.get("video"):
                md(f'<div class="mx mx-card mx-note">🎬 {ESC(nx["title"])}</div>')
            else:
                st.image(nx["path"], use_container_width=True)
    if x.get("notes"):
        md(f'<div class="mx mx-card mx-note"><b>발표 메모</b><br>{ESC(x["notes"])}</div>')
    jump = st.selectbox("바로 가기", list(range(len(steps))), index=n, format_func=lab)
    if jump != n:
        _go({"mode": "deck", "n": jump})


@st.fragment(run_every=5)
def premiere_panel():
    S = store.get_settings()
    scr = store.screen_get()
    L = store.lineup(S)
    in_line = {x["g"]: x["clip"] for x in L}
    url = base_url()
    md('<div class="mx mx-note">스크린 PC(프로젝터)에서 <b>' + ESC(url or "앱주소") + '/?view=screen</b>을 열고 화면을 <b>한 번 클릭</b>해 두세요(소리 허용). '
       '발표 자료도 같은 스크린 화면에 띄워요(<b>[📽 발표]</b> 탭). 발표가 끝나면 여기서 시작하면 됩니다.<br>'
       '아래 <b>[▶ 다음]</b>만 누르면 <b>분임 소개 화면 → 영상 → 다음 분임 소개</b> 순서로 넘어가고, 마지막 영상 뒤에는 <b>투표 화면(QR)</b>이 뜨면서 투표가 열립니다. '
       '소개 화면에는 기획서의 영상 제목·형식·역할·발표 한마디가 자동으로 나오고, 영상은 그 분임이 <b>가장 최근에 올린 영상</b>이 나옵니다. '
       '결과물이 없는 분임은 건너뜁니다.</div>')
    now = _step_label(scr, S) if scr["mode"] != "play" else f"{S['names'][scr['g'] - 1]} 영상 상영 중" if scr["g"] else "대기 판"
    md(f'<div class="mx mx-card" style="margin-top:.6rem"><div class="mx-note">지금 스크린</div><div class="mx-h1" style="font-size:1.7rem">📺 {ESC(now)}</div>'
       f'<div class="mx-note">상영할 영상 {len(L)}편 / {store.N_GROUPS}개 분임</div></div>')
    nxt = store.screen_next(S)
    if st.button(f"▶ 다음: {_step_label(nxt, S)}", key="pm_next", type="primary", use_container_width=True, disabled=not L):
        _go(nxt)
    with st.container(key="row_pm_ctl"):
        c1, c2 = st.columns(2)
        if c1.button("⏹ 대기 판으로", key="pm_board", use_container_width=True, disabled=scr["mode"] == "board"):
            _go({"mode": "board"})
        if c2.button("🗳 투표 화면 (QR)", key="pm_end", use_container_width=True, disabled=scr["mode"] == "end"):
            _go({"mode": "end"})
    md('<div class="mx mx-sec">상영 순서</div>')
    for i, g in enumerate(store.screen_order(S), 1):
        d = store.get_request(g)["data"]
        clip = in_line.get(g)
        here = scr["g"] == g and scr["mode"] in ("intro", "play")
        roles = " · ".join(f"{lab} {ESC(d[k])}" for k, lab in store.ROLES if d[k].strip())
        info = (f'🎬 {ESC(clip["name"])} · {kst(clip["at"])}' if clip else '<span style="color:#9a8a72">아직 결과물 없음 → 건너뜀</span>')
        with st.container(border=True, key=f"row_pm_{g}"):
            c1, c2, c3 = st.columns([3.2, 1, 1], vertical_alignment="center")
            c1.markdown(f'<div class="mx mx-note"><b style="font-size:1.1rem">{i}. {ESC(S["names"][g - 1])}</b> {ESC(d["title"] or d["topic"])}'
                        + (' · <b style="color:#cf4430">스크린에 나오는 중</b>' if here else "")
                        + f'<br>{info}' + (f'<br><span style="font-size:.85rem">{roles}</span>' if roles else "") + "</div>", unsafe_allow_html=True)
            if c2.button("🎤 소개", key=f"pm_intro_{g}", use_container_width=True):
                _go({"mode": "intro", "g": g})
            if c3.button("▶ 영상", key=f"pm_play_{g}", use_container_width=True, disabled=not clip):
                _go({"mode": "play", "rid": clip["id"]})
    with st.form("pm_order"):
        order = st.text_input("상영 순서 바꾸기 (분임 번호를 쉼표로, 예: 3,1,5 — 빠진 분임은 번호 순으로 뒤에. 비우면 1분임부터)", S["order"], max_chars=40)
        if st.form_submit_button("순서 저장"):
            store.save_settings(order=order.strip())
            st.rerun()


# ───────────────────────── 투표 진행(관리팀)
VSTATE = {"ready": ("준비 · 아직 안 열림", "#8a7a62", "#efe6cf"), "open": ("투표 중", "#1f7a3c", "#dcf2e1"),
          "closed": ("마감", "#b3261e", "#fbdedb")}


def _glabel(g: int, S: dict) -> str:
    return "분임 없음" if g == 0 else S["names"][g - 1]


def _title(g: int) -> str:
    d = store.get_request(g)["data"]
    return (d["title"] or d["topic"]).strip()


@st.fragment(run_every=5)
def vote_live():
    S = store.get_settings()
    t, fg, bg = VSTATE[store.vote_state()]
    roster = store.get_roster()
    vs = store.voters()
    done: dict[int, int] = {}
    for v in vs:
        done[v["voter_g"]] = done.get(v["voter_g"], 0) + 1
    tally = store.vote_tally()
    rows = []
    for g in list(range(1, store.N_GROUPS + 1)) + [0]:
        if g == 0 and not roster[0] and not done.get(0):
            continue
        rows.append(f'<tr><td><b>{ESC(_glabel(g, S))}</b></td><td>{done.get(g, 0)}' + (f' / {len(roster[g])}명' if any(roster.values()) else '명') + '</td>'
                    f'<td>{"" if g == 0 else str(tally[g]) + "표"}</td></tr>')
    md(f'<div class="mx mx-top" style="margin:.3rem 0 .5rem"><span class="mx-badge" style="color:{fg};background:{bg}">{t}</span>'
       f'<div class="mx-h1" style="font-size:1.6rem">참여 {len(vs)}' + (f' / {store.roster_total()}명' if store.roster_total() else '명') + '</div></div>')
    md('<table class="mx mx-tbl"><tr><th>분임</th><th>투표한 사람</th><th>받은 표</th></tr>' + "".join(rows) + "</table>")
    st.caption(f"5초마다 자동으로 새로 고칩니다 · {kst(time.time(), '%H:%M:%S')} 기준 · 누가 누구를 골랐는지는 저장만 하고 보여 주지 않습니다")


def vote_panel():
    S = store.get_settings()
    stt = store.vote_state()
    scr = store.screen_get()
    roster = store.get_roster()
    total = sum(len(v) for v in roster.values())
    md('<div class="mx mx-note">각자 휴대폰으로 <b>' + ESC(base_url() or "앱주소") + '/?view=vote</b>에 들어와 <b>내 이름</b>을 쓰고, '
       '<b>우리 분임을 뺀 작품 중 한 편</b>을 고릅니다(1인 1표). 같은 이름으로 두 번은 못 합니다.<br>'
       '· <b>명단을 비워 두면(자유 입력)</b>: 이름과 <b>우리 분임</b>을 각자 직접 고릅니다 — 현장에서 자리를 자유롭게 앉을 때.<br>'
       '· <b>명단을 넣으면</b>: 명단에 있는 이름만 투표할 수 있고, 분임은 명단대로 정해집니다.<br>'
       '스크린 투표 화면에 QR이 크게 나옵니다. 시사회 탭에서 마지막 영상 뒤 [▶ 다음]을 누르면 투표 화면이 뜨면서 투표가 자동으로 열립니다.</div>')
    if not total:
        st.info("지금은 명단이 비어 있어서 '자유 입력' 투표예요. 각자 이름과 우리 분임을 직접 골라요.")
    vote_live()
    with st.container(key="row_vt_ctl"):
        c1, c2 = st.columns(2)
        if c1.button("🗳 투표 열기 + 스크린에 QR" if stt != "closed" else "🗳 투표 다시 열기 + 스크린에 QR", key="vt_open",
                     use_container_width=True, disabled=stt == "open"):
            store.set_vote_state("open")
            _go({"mode": "end"})
        if c2.button("⏹ 투표 마감", key="vt_close", use_container_width=True, disabled=stt != "open"):
            store.set_vote_state("closed")
            st.rerun()

    md('<div class="mx mx-sec">결과 발표</div>')
    steps = store.award_steps(S)
    n = scr["n"] if scr["mode"] == "result" else -1
    if n < 0:
        lab = "🏆 결과 발표 화면 띄우기 (두구두구)"
    elif n < len(steps):
        lab = f"🎉 {steps[n]['award']} 공개! (축하 음악)"
    else:
        lab = "🏆 공개했습니다"
    md('<div class="mx mx-note">투표를 <b>마감한 뒤</b> 누르세요. 처음 누르면 스크린에 <b>두구두구…</b> 화면과 <b>드럼롤</b>이 계속 울리고, 분위기가 오르면 한 번 더 눌러 '
       '<b>최우수 분임</b>을 공개하세요. 심벌 “짠!”과 함께 캐럴·꽃가루가 터집니다(스크린 화면을 한 번 클릭해 둬야 소리가 나요). 표가 같으면 공동 1위로 함께 나옵니다.</div>')
    if st.button(lab, key="vt_reveal", type="primary", use_container_width=True, disabled=stt != "closed" or not steps or n >= len(steps)):
        _go({"mode": "result", "n": n + 1})
    if scr["mode"] == "result" and st.button("↺ 결과 화면 처음부터", key="vt_reveal0", use_container_width=True):
        _go({"mode": "result", "n": 0})
    with st.expander("결과 미리 보기 (관리팀만 · 스크린에는 안 나옴)"):
        rk = store.ranking(S)
        md('<div class="mx mx-note">' + "<br>".join(f'{x["rank"]}위 · <b>{ESC(S["names"][x["g"] - 1])}</b> {ESC(_title(x["g"]))} · {x["votes"]}표'
                                                 for x in rk) + "</div>")
    with st.form("vt_awards"):
        aw = st.text_input("상 이름 (1위 한 팀)", S["awards"].split(",")[0], max_chars=30)
        if st.form_submit_button("상 이름 저장"):
            store.save_settings(awards=aw.strip())
            st.rerun()

    md('<div class="mx mx-sec">분임 명단 등록 <span style="font-size:1rem;color:#CDB8A6">선택 · 비워 두면 자유 입력 · 한 줄에 한 명</span></div>')
    md('<div class="mx mx-note">명단에 있는 이름으로만 투표할 수 있고, 그 사람의 분임 작품은 투표 목록에서 빠집니다. 띄어쓰기는 상관없어요.<br>'
       '같은 이름(동명이인)이 있으면 저장되지 않으니 <b>김민수A, 김민수B</b>처럼 구분하고, 본인에게도 그렇게 쓰라고 알려 주세요.</div>')
    if store.team_get()["seq"]:
        md('<div class="mx mx-warn">🪄 <b>[팀 배정]</b> 결과가 아래 1~7분임 명단에 자동으로 들어가 있어요. 여기서 고치면 투표 명단만 바뀌고 배정(스크린·저녁 세션 명단)은 그대로예요. '
           '사람을 넣거나 뺄 때는 [🪄 팀 배정] 탭의 <b>[✏️ 현장 변경]</b>을 쓰면 둘 다 바뀝니다.</div>')
    with st.form("vt_roster"):
        cols = st.columns(2)
        texts = {}
        for i, g in enumerate(range(1, store.N_GROUPS + 1)):
            texts[g] = cols[i % 2].text_area(f"{g}. {S['names'][g - 1]} 명단", "\n".join(roster[g]), height=150)
        texts[0] = st.text_area("분임 없이 투표하는 사람 (예: 국장님 · 모든 작품에 투표할 수 있음)", "\n".join(roster[0]), height=80)
        if st.form_submit_button("명단 저장", type="primary"):
            try:
                st.success(f"명단 {store.save_roster({g: store.parse_names(t) for g, t in texts.items()})}명을 저장했습니다.")
            except store.StoreError as e:
                st.error(str(e))
    with st.expander("아직 투표하지 않은 사람"):
        voted = {store.name_key(v["name"]) for v in store.voters()}
        lines = []
        for g in list(range(1, store.N_GROUPS + 1)) + [0]:
            if roster[g]:
                left = [n for n in roster[g] if store.name_key(n) not in voted]
                lines.append(f'<b>{ESC(_glabel(g, S))}</b> · {ESC(", ".join(left)) or "모두 투표함"}')
        md('<div class="mx mx-note">' + ("<br>".join(lines) or "명단이 없습니다.") + "</div>")
    if confirm_button("🧹 투표만 다시 하기 (리허설 뒤에)", "vt_reset", "모든 표를 지우고 투표를 '준비' 상태로 돌립니다. 명단은 남습니다."):
        store.reset_votes()
        st.success("투표를 초기화했습니다.")


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


def entry_qr(url: str, scale: int = 10) -> str:
    """행사 공통 QR(앱 첫 화면 = 분임 고르기) 그림 주소."""
    try:
        import segno
        return segno.make(url + "/", error="m").svg_data_uri(scale=scale, border=1, dark="#000000", light="#ffffff")
    except Exception:
        return ""


def poster_html(url: str, S: dict) -> str:
    """행사 메인 포스터(A4 세로): 윈터 매직 디자인 + 공통 QR 하나."""
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{ESC(S["event"])} 행사 포스터</title><style>
{FONTS}{TWINKLE}
@page{{size:A4;margin:0}}*{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
body{{margin:0;background:#2a1418;font-family:"Noto Sans KR","Malgun Gothic",sans-serif}}
.tip{{max-width:210mm;margin:10px auto;padding:10px 14px;background:#fff8e6;border-radius:6px;font-size:14px}}@media print{{.tip{{display:none}}body{{background:#6B1F2C}}}}
.page{{position:relative;width:210mm;height:297mm;margin:0 auto;background:#6B1F2C;overflow:hidden;color:#F4EAD5}}
.f1{{position:absolute;inset:6mm;border:.35mm solid #D6B676}}.f2{{position:absolute;inset:8.5mm;border:.3mm solid #8E6F45}}
.gar{{position:absolute;left:12mm;right:12mm;top:11mm}}.gar svg{{width:100%;height:auto;overflow:visible;display:block}}
.tree{{position:absolute;right:12mm;bottom:12mm;height:74mm;width:55.5mm}}.sl{{position:absolute;left:24mm;bottom:25mm;width:66mm;height:46mm}}
.tree svg,.sl svg{{width:100%;height:100%;overflow:visible;display:block}}
.c{{position:absolute;left:0;right:0;top:32mm;display:flex;flex-direction:column;align-items:center;text-align:center}}
.orn{{display:flex;align-items:center;gap:4mm;width:120mm;font-family:"Cormorant Garamond",serif;font-weight:600;font-size:11pt;letter-spacing:.32em;color:#D6B676}}
.orn:before,.orn:after{{content:"";flex:1;height:.3mm;background:#D6B676}}
h1{{margin:7mm 0 0;font-family:"Noto Serif KR",serif;font-weight:600;font-size:32pt;line-height:1.2}}
.sub{{margin-top:2mm;font-family:"Noto Serif KR",serif;font-weight:500;font-size:13pt;letter-spacing:.16em;color:#D6B676}}
.qr{{margin-top:9mm;width:84mm;height:84mm;box-sizing:border-box;padding:5mm;background:#fff;border-radius:1mm;box-shadow:0 0 0 .35mm #D6B676,0 0 0 2.6mm #6B1F2C,0 0 0 2.9mm #8E6F45}}
.qr img{{width:100%;height:100%;display:block}}
.steps{{margin-top:9mm;font-family:"Noto Serif KR",serif;font-size:13pt;line-height:1.85;word-break:keep-all}}.steps b{{color:#D6B676;font-weight:600}}
.url{{margin-top:3mm;font-size:9pt;color:#CDB8A6}}
.merry{{position:absolute;left:0;right:0;bottom:13mm;text-align:center;font-family:"Cormorant Garamond",serif;font-style:italic;font-size:14pt;color:#D6B676}}
</style></head><body><div class="tip">이 파일을 연 상태에서 <b>Ctrl + P</b> → 용지 <b>A4</b>, 여백 <b>없음</b>, <b>배경 그래픽 켜기</b>로 인쇄하세요. (이 안내는 인쇄되지 않습니다)</div>
<div class="page"><div class="f1"></div><div class="f2"></div><div class="gar">{garland_svg().replace('<div class="sc-garland">', "").replace("</svg></div>", "</svg>")}</div>
<div class="sl">{_SLEIGH}</div><div class="tree">{tree_svg("pt")}</div>
<div class="c"><div class="orn">WINTER PREMIERE</div><h1>{ESC(S["event"])}</h1><div class="sub">AI 모션그래픽 광고제</div>
<div class="qr"><img src="{entry_qr(url, 12)}" alt="행사 QR"></div>
<div class="steps"><b>①</b> 휴대폰 카메라로 QR을 찍어요<br><b>②</b> 우리 분임을 골라요<br><b>③</b> 처음 들어온 분이 비밀번호(숫자 4자리)를 만들어요</div>
<div class="url">{ESC(url)}</div></div><div class="merry">Merry Christmas &amp; Happy New Year</div></div></body></html>'''


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
    md('<div class="mx mx-sec">🎄 행사 공통 QR</div>'
       '<div class="mx mx-note">QR <b>하나</b>로 모두 들어옵니다. 찍으면 <b>분임 고르기</b> 화면이 열리고, 우리 분임을 고른 뒤 비밀번호를 넣습니다. '
       '스크린 <b>대기 판</b>에도 이 QR이 크게 나오고, 아래 포스터를 인쇄해 입구나 테이블에 두어도 됩니다.</div>')
    c1, c2 = st.columns([1, 2.2], vertical_alignment="center")
    c1.markdown(f'<img src="{entry_qr(url)}" alt="행사 공통 QR" style="width:100%;max-width:220px;background:#fff;padding:8px;border-radius:4px">',
                unsafe_allow_html=True)
    with c2:
        st.download_button("🖨 행사 포스터 내려받기 (A4 · 공통 QR)", poster_html(url, S), file_name="행사포스터_공통QR.html",
                           mime="text/html", type="primary", use_container_width=True)
        md(f'<div class="mx mx-note">QR 주소: <b>{ESC(url)}</b><br>파일을 열고 <b>Ctrl + P</b> → 설정에서 <b>배경 그래픽</b>을 켜고 인쇄하세요.</div>')
    with st.expander("분임별 QR 카드 (필요할 때만)"):
        st.download_button("🖨 분임별 QR 카드 내려받기 (A4 한 장에 2분임)", qr_cards_html(url, S), file_name="분임_QR카드.html",
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
        bgm = st.text_input("관리 화면 배경음악 (유튜브 주소, 비우면 안 나옴)", S.get("bgm", ""), placeholder="https://www.youtube.com/watch?v=…")
        if st.form_submit_button("저장", type="primary"):
            store.save_settings(event=ev.strip() or "워크숍", names=names, notice=notice, public_url=url.strip().rstrip("/"), bgm=bgm.strip())
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
    if confirm_button("🧹 모두 지우고 처음부터 (리허설 뒤에)", "reset", "모든 기획서·자료·결과물·대화·투표와 분임 비밀번호를 지웁니다. 설정(분임 이름 등)·팀 배정·투표 명단은 남습니다."):
        store.reset_all()
        st.success("초기화했습니다.")


# ───────────────────────── 스크린(프로젝터)
def intro_html(g: int, S: dict) -> str:
    """시사회 분임 소개 화면: 기획서에 쓴 제목·형식·역할·발표 한마디가 자동으로 들어감."""
    d = store.get_request(g)["data"]
    gs = [x["g"] for x in store.lineup(S)]
    pos = f"시사회 {gs.index(g) + 1} / {len(gs)}" if g in gs else "시사회"
    title = (d["title"] or d["topic"]).strip()
    credits = "".join(f'<span><i>{lab}</i>{ESC(d[k])}</span>' for k, lab in store.ROLES if d[k].strip())
    pitch = d["pitch"].strip()
    return (f'<div class="sc-intro"><div class="ev">WINTER PREMIERE · {pos}</div>'
            f'<div class="grp">{ESC(S["names"][g - 1])}</div>'
            + (f'<div class="ttl"{" style=font-size:clamp(2.2rem,4.2vw,4.4rem)" if len(title) > 14 else ""}>{ESC(title)}</div>' if title else "")
            + f'<div class="fmt">{ESC(store.format_text(d))}</div>'
            + (f'<div class="cr">{credits}</div>' if credits else "")
            + (f'<div class="pitch"><b>기획 의도 · 관전 포인트</b>{ESC(pitch).replace(chr(10), "<br>")}</div>' if pitch else "")
            + f'<div class="soon">{STAR_SMALL}곧 상영합니다{STAR_SMALL}</div></div>')


def vote_screen_html(S: dict) -> str:
    """스크린 투표 화면: 투표 QR · 참여 수 (마감하면 '집계 중')."""
    stt = store.vote_state()
    total = sum(len(v) for v in store.get_roster().values())
    count = f'<div class="sc-count">참여 {len(store.voters())}' + (f" / {total}명" if total else "명") + "</div>"
    if stt == "closed":
        return (f'<div class="sc-intro"><div class="ev">{ESC(S["event"])}</div><div class="ttl">투표 마감!</div>'
                f'<div style="margin-top:3vh">{count}</div><div class="soon">{STAR_SMALL}곧 결과를 발표합니다{STAR_SMALL}</div></div>')
    url = f"{base_url()}/?view=vote"
    try:
        import segno
        img = f'<img src="{segno.make(url, error="m").svg_data_uri(scale=10, border=1, dark="#000000", light="#ffffff")}" alt="투표 QR">'
    except Exception:
        img = ""
    return (f'<div class="sc-intro wide"><div class="ev" style="max-width:60vw">{ESC(S["event"])} · 1인 1표</div>'
            f'<div class="ttl" style="font-size:clamp(2.6rem,5.4vw,5.8rem)">{"투표 시간!" if stt == "open" else "곧 투표가 열려요"}</div>'
            f'<div class="sc-vote">{img}<div class="side"><div class="how">휴대폰 카메라로 QR을 찍고<br><b>내 이름</b>을 쓴 다음<br>'
            f'우리 분임을 뺀 <b>한 편</b>을 골라 주세요</div>{count}<div class="url">{ESC(url)}</div></div></div></div>')


DECK_DIR = os.path.join(store.BASE, "deck")            # 발표 자료: 슬라이드 그림(01.jpg…)·영상·deck.json


def deck_steps() -> list[dict]:
    """발표 자료를 넘길 순서(deck/deck.json). 영상이 있는 장은 '장 그림 → 영상(전체 화면)' 두 단계."""
    try:
        with open(os.path.join(DECK_DIR, "deck.json"), encoding="utf-8") as f:
            steps = json.load(f)["steps"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    out = []
    for x in steps:
        p = os.path.join(DECK_DIR, os.path.basename(str(x.get("img") or x.get("video") or "")))
        if os.path.isfile(p):
            out.append(dict(x, path=p))
    return out


DECK_KEYS_JS = """<script>
(function () {
  var P = window.parent; if (!P || !P.document) return;
  var D = P.document, last = 0;
  if (P.__deckKey) D.removeEventListener('keydown', P.__deckKey, true);
  P.__deckKey = function (e) {
    var t = e.target || {}, tag = (t.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || t.isContentEditable) return;
    var k = e.key, dir = null;
    if (k === 'ArrowRight' || k === 'ArrowDown' || k === 'PageDown' || k === ' ' || k === 'Spacebar' || k === 'Enter') dir = 'next';
    else if (k === 'ArrowLeft' || k === 'ArrowUp' || k === 'PageUp' || k === 'Backspace') dir = 'prev';
    if (!dir) return;
    var b = D.querySelector('.st-key-deck_' + dir + ' button');
    if (!b) return;                       // 발표 자료 화면이 아닐 때는 키를 건드리지 않음
    e.preventDefault(); e.stopPropagation();
    var now = Date.now(); if (now - last < 350) return; last = now;
    if (!b.disabled) b.click();
    if (D.activeElement && D.activeElement.blur) D.activeElement.blur();
  };
  D.addEventListener('keydown', P.__deckKey, true);
})();
</script>"""


def deck_keys():
    """스크린 PC 키보드·프레젠터 리모컨(→ ← 스페이스 PageDown/PageUp)으로 발표 자료 넘기기."""
    try:
        from streamlit.components.v1 import html as _html
    except Exception:
        return
    with st.container(key="deck_keys"):
        _html(DECK_KEYS_JS, height=0)


def deck_go(n: int):
    steps = deck_steps()
    if steps:
        store.screen_go({"mode": "deck", "n": min(max(0, int(n)), len(steps) - 1)})
    st.rerun()


def deck_screen(n: int):
    """발표 자료 한 장을 화면 가득. 클릭·→·스페이스 = 다음, ← = 이전."""
    steps = deck_steps()
    n = min(max(0, n), len(steps) - 1)
    x = steps[n]
    nxt = steps[n + 1] if n + 1 < len(steps) else None
    md('<style>.stApp{background:#000!important}.stApp::before,.stApp::after{display:none!important}.block-container{padding:0!important}</style>')
    with st.container(key="deck_view"):
        if x.get("video"):
            st.video(x["path"], format="video/mp4", autoplay=True)
        else:
            st.image(x["path"], use_container_width=True)
    if nxt and nxt.get("img"):
        with st.container(key="deck_pre"):        # 다음 장 그림을 미리 받아 둠(넘길 때 바로 뜨게)
            st.image(nxt["path"])
    if not x.get("video"):
        with st.container(key="deck_hit"):        # 화면 아무 곳이나 누르면 다음 장
            if st.button("다음 장", key="deck_hit_btn", disabled=nxt is None):
                deck_go(n + 1)
    with st.container(key="deck_nav"):
        c1, c2 = st.columns(2)
        if c1.button("◀", key="deck_prev", use_container_width=True, disabled=n == 0):
            deck_go(n - 1)
        if c2.button("▶", key="deck_next", use_container_width=True, disabled=nxt is None):
            deck_go(n + 1)
    md(f'<div class="sc-deckno">{x.get("slide", n + 1)} / {steps[-1].get("slide", len(steps))}</div>')


def sort_html(S: dict, T: dict) -> str:
    """배정식 그림에 넣을 값: 분임 이름·색, 날아가는 순서, 화면 단계, 시작한 뒤 지난 초(서버 시계)."""
    since = max(0.0, time.time() - T["show_at"] / 1000) if T["show_at"] else 0.0
    data = {"event": S["event"], "title": "마법의 분임 배정식",
            "groups": [{"label": S["names"][i], "color": SORT_COLORS[i % len(SORT_COLORS)]} for i in range(store.N_GROUPS)],
            "seq": [] if T["show_mode"] == "idle" else [[n, g - 1] for n, g in T["seq"]],      # 준비 화면엔 이름을 안 실음(미리 안 보이게)
            "mode": T["show_mode"], "since": round(since, 2)}
    return SORT_HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))


def sort_screen(S: dict):
    """마법의 분임 배정식: 화면 가득(캔버스 그림 + 효과음). 끝나면 결과 화면이 그대로 남음."""
    md('<style>.stApp{background:#07061A!important}.stApp::before,.stApp::after{display:none!important}.block-container{padding:0!important}</style>')
    try:
        from streamlit.components.v1 import html as _html
    except Exception:
        md('<div class="sc-intro"><div class="ttl">분임 배정식</div></div>')
        return
    with st.container(key="sort_view"):
        _html(sort_html(S, store.team_get()), height=640)


# 배정식 그림(1920×1080 캔버스): 이름이 떠오름 → 마법진 소용돌이에 섞임 → 처음 4명은 가운데서 크게 호명 → 분임 깃발로 날아가 꽂힘 → 배정 완료
# 효과음은 브라우저에서 직접 만듦(WebAudio). __DATA__ 자리에 sort_html()이 값을 넣음.
SORT_HTML = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@1,600&family=Noto+Serif+KR:wght@600;900&family=Noto+Sans+KR:wght@500;700&display=swap" rel="stylesheet">
<style>
html,body{margin:0;height:100%;background:#07061A;overflow:hidden}
#wrap{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:#07061A}
canvas{display:block}
#snd{position:fixed;right:14px;bottom:12px;font:500 14px "Noto Sans KR","Noto Sans CJK KR",sans-serif;color:#D6B676;background:rgba(20,14,40,.75);border:1px solid rgba(214,182,118,.5);border-radius:999px;padding:6px 14px;cursor:pointer;display:none}
</style></head>
<body><div id="wrap"><canvas id="c" width="1920" height="1080"></canvas></div><div id="snd">🔈 소리 켜기</div>
<script>
/* 마법의 분임 배정식 — 이름이 마법진 소용돌이에 섞였다가 분임 깃발로 날아가 꽂힘.
   DATA = {event, title, groups:[{label, color}], seq:[[이름, 분임 index], …(나가는 순서)], mode:'idle'|'play'|'final',
           since: 관리팀이 [배정식 시작]을 누른 뒤 지난 초(서버 시계로 잼 — 스크린 PC 시계가 틀려도 괜찮게)} */
const DATA = __DATA__;
const W = 1920, H = 1080;
const IDLE = DATA.mode === 'idle';
let AMB = 0;                                   // 배경(별·촛불·마법진 회전)은 늘 흐르는 시계
const cv = document.getElementById('c'); let ctx = cv.getContext('2d');
const SERIF = '"Noto Serif KR","Noto Serif CJK KR","Nanum Myeongjo",serif';
const SANS = '"Noto Sans KR","Noto Sans CJK KR",sans-serif';
const ITAL = '"Cormorant Garamond","Playfair Display",serif';
const GOLD = '#E9C77B', IVORY = '#FFF4D6';

function fit() {
  const s = Math.min(innerWidth / W, innerHeight / H);
  cv.style.width = (W * s) + 'px'; cv.style.height = (H * s) + 'px';
}
addEventListener('resize', fit); fit();

/* ── 난수·보간 ── */
function rng(seed) { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const seg = (t, a, b) => clamp((t - a) / (b - a));
const eOut = t => 1 - Math.pow(1 - t, 3);
const eIO = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const eBack = t => { const s = 1.7; return t <= 0 ? 0 : 1 + (s + 1) * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2); };
function bez(p0, p1, p2, p3, t) { const u = 1 - t; return [u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0], u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1]]; }

/* ── 일정표 ── */
const seq = DATA.seq || [], N = seq.length, G = Math.max(1, (DATA.groups || []).length);
const T_APPEAR0 = .9, T_APPEAR1 = 2.6, T_SWIRL = 3.1, T_VORTEX = 7.0, T_SORT = 7.6, CALL = .5, FLY = .82;
const CALLS = Math.min(4, N);
const exits = [], lands = [], slot = [], cnt = new Array(G).fill(0);
{ let tc = T_SORT;
  for (let k = 0; k < N; k++) {
    exits.push(tc);
    lands.push(tc + (k < CALLS ? CALL : 0) + FLY);
    slot.push(cnt[seq[k][1]]++);
    tc += k < CALLS ? 1.3 : Math.max(.2, .72 * Math.pow(.85, k - CALLS));
  } }
const T_FIN = (N ? Math.max(...lands) : T_SORT) + .6;
const MAXPER = Math.max(1, ...cnt);

/* ── 깃발 배치 ── */
const BX0 = 56, BWT = 1808, GAP = 16, BW = (BWT - GAP * (G - 1)) / G;
const ROD = 594, BTOP = 600, BBOT = 1070, STOP = 728, SBOT = 1030;
const COLS = MAXPER > 11 ? 2 : 1;
const ROWS = Math.ceil(MAXPER / COLS);
const SLH = Math.min(42, (SBOT - STOP) / ROWS);
const NFS = Math.min(30, SLH * .74) * (COLS === 2 ? .92 : 1);
function slotXY(g, s) {
  const bx = BX0 + g * (BW + GAP);
  const col = COLS === 2 ? (s % 2) : 0, row = COLS === 2 ? Math.floor(s / 2) : s;
  const x = COLS === 2 ? bx + BW * (col ? .75 : .25) : bx + BW / 2;
  return [x, STOP + SLH * (row + .5)];
}

/* ── 소용돌이 ── */
const CF = [960, 488];                 // 마법진(바닥) 중심
const R = rng(20261127);
const P = seq.map((x, i) => ({
  name: x[0], g: x[1],
  p0: [lerp(150, 1770, R()), lerp(190, 540, R())],
  r: lerp(150, 330, R()), lift: lerp(60, 200, R()), th0: R() * Math.PI * 2, w: lerp(.82, 1.22, R()),
  ph: R() * 6.28, fl: R() * 6.28,
  app: T_APPEAR0 + (T_APPEAR1 - T_APPEAR0) * R()
}));
const SPIN_A = Math.PI * 2 * 1.7, SPIN_W = 2 * SPIN_A / (T_VORTEX - T_SWIRL);
function spin(t) {
  if (t < T_SWIRL) return 0;
  if (t < T_VORTEX) { const u = (t - T_SWIRL) / (T_VORTEX - T_SWIRL); return SPIN_A * u * u; }
  return SPIN_A + SPIN_W * (t - T_VORTEX);
}
function vortex(p, t) {
  const th = p.th0 + spin(t) * p.w;
  const lift = p.lift + 16 * Math.sin(1.6 * t + p.ph);
  return { x: CF[0] + p.r * Math.cos(th), y: CF[1] - lift + p.r * .27 * Math.sin(th), d: (1 + Math.sin(th)) / 2 };
}
function floatPos(p, t) { return [p.p0[0] + 10 * Math.sin(.9 * t + p.fl), p.p0[1] + 8 * Math.cos(1.1 * t + p.fl)]; }

/* 이름 하나의 상태(위치·크기·밝기) */
function nameState(k, t) {
  const p = P[k], e = exits[k], L = lands[k];
  if (IDLE || t < p.app) return null;
  if (t >= L) { const [x, y] = slotXY(p.g, slot[k]); return { x, y, fs: NFS, a: 1, phase: 'landed' }; }
  if (t < e) {
    const a = eOut(seg(t, p.app, p.app + .35)), pop = .6 + .4 * eBack(seg(t, p.app, p.app + .45));
    const b = eIO(seg(t, T_SWIRL, T_VORTEX));
    const f = floatPos(p, t), v = vortex(p, t);
    const depth = lerp(1, v.d, b);
    return { x: lerp(f[0], v.x, b), y: lerp(f[1], v.y, b), fs: 31 * pop * lerp(1, .72 + .38 * depth, b), a: a * lerp(1, .45 + .55 * depth, b), depth, phase: 'orbit', blur: b };
  }
  const v0 = vortex(p, e), start = [v0.x, v0.y], sfs = 31 * (.72 + .38 * v0.d);
  const [sx, sy] = slotXY(p.g, slot[k]);
  if (k < CALLS && t < e + CALL) {           // 호명: 가운데로 크게
    const u = eOut(seg(t, e, e + CALL));
    return { x: lerp(start[0], 960, u), y: lerp(start[1], 330, u), fs: lerp(sfs, 92, u), a: 1, phase: 'call', u };
  }
  const f0 = k < CALLS ? [960, 330] : start, fs0 = k < CALLS ? 92 : sfs, t0 = k < CALLS ? e + CALL : e;
  const u = eIO(seg(t, t0, L));
  const c1 = [f0[0] + (sx - f0[0]) * .15, f0[1] - 170], c2 = [sx, sy - 260];
  const [x, y] = bez(f0, c1, c2, [sx, sy], u);
  return { x, y, fs: lerp(fs0, NFS, u), a: 1, phase: 'fly', u, t0, f0, c1, c2, sx, sy };
}

/* ── 고정 그림(한 번만) ── */
function offscreen(w, h, fn) { const c = document.createElement('canvas'); c.width = w; c.height = h; fn(c.getContext('2d')); return c; }
const BG = offscreen(W, H, g => {
  const gr = g.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, '#0A0820'); gr.addColorStop(.55, '#1A1240'); gr.addColorStop(1, '#2A1430');
  g.fillStyle = gr; g.fillRect(0, 0, W, H);
  const r2 = g.createRadialGradient(960, 480, 40, 960, 480, 900); r2.addColorStop(0, 'rgba(120,80,190,.35)'); r2.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = r2; g.fillRect(0, 0, W, H);
  const fog = g.createLinearGradient(0, 760, 0, H); fog.addColorStop(0, 'rgba(214,182,118,0)'); fog.addColorStop(1, 'rgba(214,182,118,.10)');
  g.fillStyle = fog; g.fillRect(0, 760, W, H - 760);
});
const RS = rng(7);
const STARS = Array.from({ length: 170 }, () => ({ x: RS() * W, y: RS() * 620, r: .6 + RS() * 1.8, ph: RS() * 6.28, sp: .8 + RS() * 2.2 }));
const CANDLES = [];
{ const rc = rng(11);
  const xs = [90, 190, 300, 400, 500, 1420, 1520, 1620, 1730, 1830];
  xs.forEach((x, i) => CANDLES.push({ x: x + (rc() - .5) * 40, y: 70 + rc() * 190, s: .65 + rc() * .55, ph: rc() * 6.28 })); }
const CANDLE = offscreen(60, 160, g => {
  const body = g.createLinearGradient(18, 0, 42, 0); body.addColorStop(0, '#E8DCC2'); body.addColorStop(.5, '#FFF8E8'); body.addColorStop(1, '#D9CBAE');
  g.fillStyle = body; g.beginPath(); g.roundRect(18, 52, 24, 100, 4); g.fill();
  g.fillStyle = '#F5ECD8'; g.beginPath(); g.ellipse(30, 52, 12, 4, 0, 0, Math.PI * 2); g.fill();
  g.strokeStyle = '#3A2A1A'; g.lineWidth = 2; g.beginPath(); g.moveTo(30, 52); g.lineTo(30, 44); g.stroke();
});
const BANNER = [];
function buildBanners() {
  BANNER.length = 0;
  (DATA.groups || []).forEach((gp, gi) => {
    BANNER.push(offscreen(Math.ceil(BW) + 20, BBOT - ROD + 20, g => {
      const w = BW, x0 = 10, y0 = 6, h = BBOT - BTOP, notch = 34;
      const path = () => { g.beginPath(); g.moveTo(x0, y0); g.lineTo(x0 + w, y0); g.lineTo(x0 + w, y0 + h); g.lineTo(x0 + w / 2, y0 + h - notch); g.lineTo(x0, y0 + h); g.closePath(); };
      g.save(); g.shadowColor = 'rgba(0,0,0,.5)'; g.shadowBlur = 18; g.shadowOffsetY = 8; path(); g.fillStyle = gp.color; g.fill(); g.restore();
      const gr = g.createLinearGradient(0, y0, 0, y0 + h); gr.addColorStop(0, 'rgba(255,255,255,.18)'); gr.addColorStop(.35, 'rgba(255,255,255,0)'); gr.addColorStop(1, 'rgba(0,0,0,.38)');
      path(); g.fillStyle = gr; g.fill();
      g.save(); path(); g.clip(); g.globalAlpha = .06; g.strokeStyle = '#fff'; g.lineWidth = 1;
      for (let d = -h; d < w + h; d += 7) { g.beginPath(); g.moveTo(x0 + d, y0); g.lineTo(x0 + d - h, y0 + h); g.stroke(); }
      g.restore();
      g.save(); g.translate(0, 0);
      const inset = 9; g.beginPath(); g.moveTo(x0 + inset, y0 + inset); g.lineTo(x0 + w - inset, y0 + inset); g.lineTo(x0 + w - inset, y0 + h - inset - 4); g.lineTo(x0 + w / 2, y0 + h - notch - inset + 2); g.lineTo(x0 + inset, y0 + h - inset - 4); g.closePath();
      g.strokeStyle = 'rgba(233,199,123,.85)'; g.lineWidth = 2.5; g.stroke(); g.restore();
      g.fillStyle = 'rgba(0,0,0,.22)'; g.fillRect(x0 + 16, y0 + 118, w - 32, 2);
      g.fillStyle = 'rgba(233,199,123,.9)'; g.fillRect(x0 + 16, y0 + 116, w - 32, 2);
      // 문장(마름모 + 별)
      g.save(); g.translate(x0 + w / 2, y0 + 24); g.fillStyle = 'rgba(233,199,123,.95)';
      g.beginPath(); g.moveTo(0, -12); g.lineTo(10, 0); g.lineTo(0, 12); g.lineTo(-10, 0); g.closePath(); g.fill();
      g.fillStyle = gp.color; g.beginPath(); g.arc(0, 0, 4, 0, Math.PI * 2); g.fill(); g.restore();
      let fs = 36; g.font = `900 ${fs}px ${SERIF}`;
      while (g.measureText(gp.label).width > w - 36 && fs > 18) { fs -= 1; g.font = `900 ${fs}px ${SERIF}`; }
      g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = IVORY; g.shadowColor = 'rgba(0,0,0,.45)'; g.shadowBlur = 6;
      g.fillText(gp.label, x0 + w / 2, y0 + 60);
    }));
  });
}

/* ── 그리기 조각 ── */
function txtGlow(s, x, y, fs, a, glow, font, color) {
  ctx.font = `${font || '600'} ${fs}px ${SERIF}`;
  ctx.globalAlpha = a; ctx.shadowColor = glow || 'rgba(255,200,100,.95)'; ctx.shadowBlur = fs * .55;
  ctx.fillStyle = color || IVORY; ctx.fillText(s, x, y);
  ctx.shadowBlur = 0; ctx.globalAlpha = 1;
}
function fitFs(s, fs, maxw, weight) { ctx.font = `${weight || 600} ${fs}px ${SERIF}`; const w = ctx.measureText(s).width; return w > maxw ? fs * maxw / w : fs; }
function drawStars() {
  const t = AMB; ctx.fillStyle = '#FFF6DA';
  for (const s of STARS) { ctx.globalAlpha = .25 + .55 * (.5 + .5 * Math.sin(t * s.sp + s.ph)); ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.283); ctx.fill(); }
  ctx.globalAlpha = 1;
}
function drawCandles() {
  const t = AMB;
  for (const c of CANDLES) {
    const y = c.y + 7 * Math.sin(t * .8 + c.ph);
    ctx.save(); ctx.translate(c.x, y); ctx.scale(c.s, c.s);
    ctx.globalCompositeOperation = 'lighter';
    const fl = 1 + .12 * Math.sin(t * 13 + c.ph) + .08 * Math.sin(t * 21 + c.ph * 2);
    const gl = ctx.createRadialGradient(0, -14, 2, 0, -14, 70 * fl); gl.addColorStop(0, 'rgba(255,200,110,.55)'); gl.addColorStop(1, 'rgba(255,170,60,0)');
    ctx.fillStyle = gl; ctx.beginPath(); ctx.arc(0, -14, 70 * fl, 0, 6.283); ctx.fill();
    ctx.globalCompositeOperation = 'source-over';
    ctx.drawImage(CANDLE, -30, -48);
    ctx.fillStyle = '#FFE9A8'; ctx.beginPath(); ctx.ellipse(0, -14 + 44 - 44, 5 * fl, 12 * fl, 0, 0, 6.283); ctx.fill();
    ctx.fillStyle = '#FFFFFF'; ctx.beginPath(); ctx.ellipse(0, -11, 2.4, 6, 0, 0, 6.283); ctx.fill();
    ctx.restore();
  }
}
const GLYPHS = Array.from({ length: 40 }, (_, i) => i);
function glyph(i) {                            // 마법진 테두리의 기호(지어낸 모양)
  const k = i % 6; ctx.beginPath();
  if (k === 0) { ctx.moveTo(-7, 8); ctx.lineTo(0, -9); ctx.lineTo(7, 8); }
  else if (k === 1) { ctx.arc(0, 0, 6, 0, 6.283); ctx.moveTo(0, -10); ctx.lineTo(0, 10); }
  else if (k === 2) { ctx.moveTo(-7, -8); ctx.lineTo(7, -8); ctx.lineTo(-7, 8); ctx.lineTo(7, 8); }
  else if (k === 3) { ctx.moveTo(0, -9); ctx.lineTo(0, 9); ctx.moveTo(-6, -3); ctx.lineTo(6, 3); }
  else if (k === 4) { ctx.moveTo(-7, 0); ctx.lineTo(0, -8); ctx.lineTo(7, 0); ctx.lineTo(0, 8); ctx.closePath(); }
  else { ctx.moveTo(-6, -8); ctx.lineTo(-6, 8); ctx.moveTo(-6, 0); ctx.lineTo(6, -8); ctx.moveTo(-6, 0); ctx.lineTo(6, 8); }
  ctx.stroke();
}
function power(t) {                            // 마법진 밝기
  if (IDLE) return .3 + .1 * Math.sin(AMB * 1.6);
  if (t < 1) return .25 * seg(t, 0, 1);
  if (t < T_SWIRL) return .25 + .1 * seg(t, 1, T_SWIRL);
  if (t < T_VORTEX) return .35 + .65 * seg(t, T_SWIRL, T_VORTEX);
  if (t < T_FIN) return .9 + .1 * Math.sin(t * 7);
  return lerp(1, .38, seg(t, T_FIN, T_FIN + 2.5));
}
/* 마법진: 빛번짐(shadowBlur)을 기울인·납작한 그림에 매 장면 그리면 컴퓨터에 따라 아주 느려짐(초당 3장) →
   처음에 한 번만 그려 두고(MC), 매 장면엔 그려 둔 그림을 밝기만 바꿔 얹음 */
const MC = {};
function buildCircle() {
  const ring = (blur) => offscreen(720, 280, g => {          // 고리 4개: 화면 모양(납작한 타원) 그대로 그려 둠 → 빛번짐도 화면과 같음
    g.translate(360, 140); g.scale(1, .3);
    g.strokeStyle = 'rgb(240,205,130)'; g.shadowColor = 'rgba(255,200,110,.9)'; g.shadowBlur = blur;
    for (const [r, lw] of [[300, 4], [272, 2], [230, 3], [150, 2]]) { g.lineWidth = lw; g.beginPath(); g.arc(0, 0, r, 0, 6.283); g.stroke(); }
  });
  MC.ringLo = ring(6); MC.ringHi = ring(20);
  MC.halo = offscreen(880, 300, g => {
    g.translate(440, 150); g.scale(1, .3);
    const h = g.createRadialGradient(0, 0, 40, 0, 0, 420); h.addColorStop(0, 'rgba(255,210,120,.32)'); h.addColorStop(1, 'rgba(255,190,90,0)');
    g.fillStyle = h; g.beginPath(); g.arc(0, 0, 420, 0, 6.283); g.fill();
  });
  const S = 600, keep = ctx;                                   // 도는 기호 고리·별(납작하게 하기 전 모양)
  MC.glyph = offscreen(S, S, g => {
    g.translate(S / 2, S / 2); g.strokeStyle = 'rgb(240,205,130)'; g.lineWidth = 2.2; g.lineCap = 'round'; g.lineJoin = 'round';
    g.shadowColor = 'rgba(255,200,110,.9)'; g.shadowBlur = 8;
    ctx = g;
    for (const i of GLYPHS) { const a = i / GLYPHS.length * 6.283; g.save(); g.translate(Math.cos(a) * 251, Math.sin(a) * 251); g.rotate(a + Math.PI / 2); glyph(i); g.restore(); }
    ctx = keep;
  });
  MC.hex = offscreen(S, S, g => {
    g.translate(S / 2, S / 2); g.strokeStyle = 'rgb(240,205,130)'; g.lineWidth = 2.5; g.lineJoin = 'round';
    g.shadowColor = 'rgba(255,200,110,.9)'; g.shadowBlur = 8;
    for (const off of [0, Math.PI / 3]) { g.beginPath(); for (let j = 0; j < 4; j++) { const a = off + j * 2 * Math.PI / 3; const x = Math.cos(a) * 228, y = Math.sin(a) * 228; j ? g.lineTo(x, y) : g.moveTo(x, y); } g.stroke(); }
  });
  MC.col = offscreen(640, 460, g => {                          // 빛기둥
    const ox = 320, oy = 450;
    const c = g.createLinearGradient(0, oy - 430, 0, oy); c.addColorStop(0, 'rgba(255,214,140,0)'); c.addColorStop(1, 'rgba(255,214,140,.2)');
    g.fillStyle = c; g.beginPath(); g.moveTo(ox - 300, oy); g.bezierCurveTo(ox - 250, oy - 200, ox - 120, oy - 380, ox - 60, oy - 440);
    g.lineTo(ox + 60, oy - 440); g.bezierCurveTo(ox + 120, oy - 380, ox + 250, oy - 200, ox + 300, oy); g.closePath(); g.fill();
  });
}
function drawCircle(t) {
  const pw = power(t), ra = .35 + .6 * pw;
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  ctx.globalAlpha = clamp(pw); ctx.drawImage(MC.halo, CF[0] - 440, CF[1] - 150);
  ctx.globalAlpha = ra * (1 - clamp(pw)); ctx.drawImage(MC.ringLo, CF[0] - 360, CF[1] - 140);
  ctx.globalAlpha = ra * clamp(pw); ctx.drawImage(MC.ringHi, CF[0] - 360, CF[1] - 140);
  ctx.globalAlpha = ra;
  ctx.translate(CF[0], CF[1]); ctx.scale(1, .3);
  ctx.save(); ctx.rotate(AMB * .22); ctx.drawImage(MC.glyph, -300, -300); ctx.restore();
  ctx.save(); ctx.rotate(-AMB * .14); ctx.drawImage(MC.hex, -300, -300); ctx.restore();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = clamp(pw); ctx.drawImage(MC.col, CF[0] - 320, CF[1] - 450);
  ctx.restore();
}
function sparkleDot(x, y, r, a, col) {
  ctx.globalAlpha = a; ctx.fillStyle = col || '#FFE7A6';
  ctx.beginPath(); ctx.moveTo(x, y - r * 2.2); ctx.lineTo(x + r * .5, y - r * .5); ctx.lineTo(x + r * 2.2, y); ctx.lineTo(x + r * .5, y + r * .5);
  ctx.lineTo(x, y + r * 2.2); ctx.lineTo(x - r * .5, y + r * .5); ctx.lineTo(x - r * 2.2, y); ctx.lineTo(x - r * .5, y - r * .5); ctx.closePath(); ctx.fill();
  ctx.globalAlpha = 1;
}
const VSP = Array.from({ length: 90 }, (_, i) => { const r = rng(300 + i); return { r: lerp(110, 380, r()), lift: lerp(30, 300, r()), th: r() * 6.28, w: lerp(.7, 1.5, r()), s: .8 + r() * 1.6, ph: r() * 6.28 }; });
function drawVortexSparkles(t, front) {
  const amt = seg(t, T_SWIRL, T_VORTEX) * (1 - seg(t, T_FIN - .4, T_FIN + .6));
  if (amt <= 0) return;
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (const s of VSP) {
    const th = s.th + spin(t) * s.w * 1.1, d = (1 + Math.sin(th)) / 2;
    if ((d >= .5) !== front) continue;
    const x = CF[0] + s.r * Math.cos(th), y = CF[1] - s.lift - 10 * Math.sin(t * 2 + s.ph) + s.r * .27 * Math.sin(th);
    sparkleDot(x, y, s.s * (.6 + .6 * d), amt * (.35 + .65 * d) * (.5 + .5 * Math.sin(t * 9 + s.ph)));
  }
  ctx.restore();
}
function drawTrail(st, k, t) {
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const col = DATA.groups[P[k].g].color;
  for (let j = 1; j <= 14; j++) {
    const tt = t - j * .022; if (tt < st.t0) break;
    const u = eIO(seg(tt, st.t0, lands[k]));
    const [x, y] = bez(st.f0, st.c1, st.c2, [st.sx, st.sy], u);
    sparkleDot(x + Math.sin(j * 7.1 + k) * 6, y + Math.cos(j * 5.3 + k) * 6, 2.6 - j * .13, .75 * (1 - j / 15), j % 3 ? '#FFE3A0' : col);
  }
  ctx.restore();
}
function drawBursts(t) {
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (let k = 0; k < N; k++) {
    const dt = t - lands[k]; if (dt < 0 || dt > .9) continue;
    const [x, y] = slotXY(P[k].g, slot[k]); const r = rng(900 + k);
    for (let j = 0; j < 14; j++) {
      const a = r() * 6.283, sp = 90 + r() * 170, px = x + Math.cos(a) * sp * dt * (1 - dt / 1.8), py = y + Math.sin(a) * sp * dt * (1 - dt / 1.8) + 40 * dt * dt;
      sparkleDot(px, py, 1.6 + r() * 2, (1 - dt / .9), j % 2 ? '#FFE7A6' : DATA.groups[P[k].g].color);
    }
  }
  ctx.restore();
}
function bannerClip(bx, dy) {
  const x0 = bx, y0 = BTOP + dy, w = BW, h = BBOT - BTOP, notch = 34;
  ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x0 + w, y0); ctx.lineTo(x0 + w, y0 + h); ctx.lineTo(x0 + w / 2, y0 + h - notch); ctx.lineTo(x0, y0 + h); ctx.closePath();
}
function lastLand(g, t) { let m = -9; for (let k = 0; k < N; k++) if (P[k].g === g && lands[k] <= t && lands[k] > m) m = lands[k]; return m; }
function drawBanners(t) {
  const rise = g => eOut(seg(t, .2 + g * .07, .9 + g * .07));
  ctx.save();
  // 금빛 막대
  for (let g = 0; g < G; g++) {
    const r = rise(g); if (r <= 0) continue;
    const bx = BX0 + g * (BW + GAP), dy = (1 - r) * 520;
    ctx.globalAlpha = r;
    ctx.drawImage(BANNER[g], bx - 10, ROD + dy);
    const rod = ctx.createLinearGradient(0, ROD + dy - 6, 0, ROD + dy + 6); rod.addColorStop(0, '#FFF0B8'); rod.addColorStop(.5, '#C99A3E'); rod.addColorStop(1, '#7A5A1E');
    ctx.fillStyle = rod; ctx.fillRect(bx - 12, ROD + dy - 5, BW + 24, 11);
    ctx.fillStyle = '#E9C77B'; ctx.beginPath(); ctx.arc(bx - 12, ROD + dy, 8, 0, 6.283); ctx.arc(bx + BW + 12, ROD + dy, 8, 0, 6.283); ctx.fill();
    // 인원 수
    const n = P.filter((p, k) => p.g === g && lands[k] <= t).length;
    ctx.font = `500 21px ${SANS}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = 'rgba(255,244,214,.78)';
    ctx.fillText(`${n}명`, bx + BW / 2, ROD + dy + 101);
    // 착지 번쩍
    const fl = 1 - seg(t - lastLand(g, t), 0, .45);
    if (fl > 0 && fl < 1) { ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = fl * .35 * r; ctx.fillStyle = '#FFE3A0'; bannerClip(bx, dy); ctx.fill(); ctx.globalCompositeOperation = 'source-over'; }
    // 끝난 뒤 은은한 숨쉬기
    const fin = seg(t, T_FIN, T_FIN + .8);
    if (fin > 0) { ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = fin * (.06 + .05 * Math.sin(t * 2.2 + g)); ctx.fillStyle = '#FFE3A0'; bannerClip(bx, dy); ctx.fill(); ctx.globalCompositeOperation = 'source-over'; }
  }
  ctx.restore(); ctx.globalAlpha = 1;
}
function drawTitle(t) {
  const a = eOut(seg(t, 0, 1.1));
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.globalAlpha = a * .9; ctx.font = `600 22px ${SANS}`; ctx.fillStyle = GOLD;
  if (ctx.letterSpacing !== undefined) ctx.letterSpacing = '8px';
  ctx.fillText(DATA.event || '', 960, 36);
  if (ctx.letterSpacing !== undefined) ctx.letterSpacing = '0px';
  const tg = ctx.createLinearGradient(0, 62, 0, 124); tg.addColorStop(0, '#FFF3C4'); tg.addColorStop(.55, '#E9C77B'); tg.addColorStop(1, '#B98A35');
  ctx.globalAlpha = a; ctx.font = `900 66px ${SERIF}`; ctx.shadowColor = 'rgba(255,190,90,.55)'; ctx.shadowBlur = 24; ctx.fillStyle = tg;
  ctx.fillText(DATA.title || '마법의 분임 배정식', 960, 94); ctx.shadowBlur = 0;
  let msg = '마법진이 깨어나는 중…';
  if (IDLE) { ctx.globalAlpha = a * (.6 + .3 * Math.sin(AMB * 2.2)); ctx.font = `500 32px ${SANS}`; ctx.fillStyle = IVORY; ctx.fillText('곧 마법의 분임 배정식이 시작됩니다', 960, 156); ctx.globalAlpha = 1; return; }
  if (t >= T_APPEAR0) msg = '오늘 함께할 모두의 이름이 떠오릅니다';
  if (t >= T_SWIRL) msg = '이름이 마법진 속으로 섞이는 중…';
  if (t >= T_SORT) msg = '마법이 분임을 정하는 중…';
  if (t >= T_FIN) msg = '';
  if (msg) { ctx.globalAlpha = a * (.65 + .2 * Math.sin(t * 3)); ctx.font = `500 30px ${SANS}`; ctx.fillStyle = IVORY; ctx.fillText(msg, 960, 156); }
  ctx.globalAlpha = 1;
}
function drawFinale(t) {
  const u = seg(t, T_FIN, T_FIN + .9); if (u <= 0) return;
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const rr = rng(77);
  for (let j = 0; j < 110; j++) {                 // 금가루 비
    const st = T_FIN + rr() * 3.2, dur = 2.6 + rr() * 2.2, x = rr() * W, sz = 1.4 + rr() * 2.6, sway = rr() * 6.28;
    const k = (t - st) / dur; if (k < 0) continue; const kk = k % 1;
    const fade = t - st > 6 ? .45 : 1;
    sparkleDot(x + 26 * Math.sin(kk * 6 + sway), -20 + kk * 640, sz, (1 - kk) * fade * (.5 + .5 * Math.sin(t * 8 + j)), j % 4 ? '#FFE7A6' : '#FFFFFF');
  }
  ctx.restore();
  const s = .7 + .3 * eBack(seg(t, T_FIN, T_FIN + .7));
  ctx.save(); ctx.translate(960, 300); ctx.scale(s, s); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  const tg = ctx.createLinearGradient(0, -60, 0, 60); tg.addColorStop(0, '#FFF6D2'); tg.addColorStop(.6, '#EAC777'); tg.addColorStop(1, '#C28F35');
  ctx.globalAlpha = u; ctx.font = `900 128px ${SERIF}`; ctx.shadowColor = 'rgba(255,200,100,.9)'; ctx.shadowBlur = 40; ctx.fillStyle = tg;
  ctx.fillText('배정 완료!', 0, -18); ctx.shadowBlur = 0; ctx.restore();
  const u2 = seg(t, T_FIN + .5, T_FIN + 1.3);
  ctx.globalAlpha = u2; ctx.font = `500 36px ${SANS}`; ctx.fillStyle = IVORY; ctx.textAlign = 'center'; ctx.shadowColor = 'rgba(10,6,30,.95)'; ctx.shadowBlur = 14;
  ctx.fillText('내 이름을 찾아 우리 분임 자리로 모여 주세요', 960, 376); ctx.shadowBlur = 0;
  ctx.globalAlpha = 1;
}

/* ── 한 장면 ── */
function frame(t, amb) {
  AMB = amb === undefined ? t : amb;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
  ctx.drawImage(BG, 0, 0);
  drawStars(); drawCandles(); drawTitle(t);
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  const states = []; for (let k = 0; k < N; k++) { const s = nameState(k, t); if (s) states.push([k, s]); }
  const orbit = states.filter(([, s]) => s.phase === 'orbit').sort((a, b) => a[1].depth - b[1].depth);
  const back = orbit.filter(([, s]) => s.depth < .5), front = orbit.filter(([, s]) => !(s.depth < .5));
  let dim = 1; for (const [, s] of states) if (s.phase === 'call') dim = Math.min(dim, 1 - .6 * Math.sin(Math.PI * Math.min(1, s.u * 1.4)) ** .5);
  for (const [k, s] of states) if (s.phase === 'fly' && k < CALLS) dim = Math.min(dim, .4 + .6 * s.u);
  drawVortexSparkles(t, false);
  for (const [k, s] of back) txtGlow(P[k].name, s.x, s.y, s.fs, s.a * .85 * dim);
  drawCircle(t);
  for (const [k, s] of front) txtGlow(P[k].name, s.x, s.y, s.fs, s.a * dim);
  drawVortexSparkles(t, true);
  drawBanners(t);
  // 꽂힌 이름
  for (const [k, s] of states) if (s.phase === 'landed') {
    const g = P[k].g, ri = eOut(seg(t, .2 + g * .07, .9 + g * .07)); const dy = (1 - ri) * 520;
    const fs = fitFs(P[k].name, s.fs, (COLS === 2 ? BW / 2 : BW) - 22);
    const glow = 1 - seg(t - lands[k], 0, .8);
    txtGlow(P[k].name, s.x, s.y + dy, fs, 1, `rgba(255,214,140,${.25 + .7 * glow})`, '600', glow > 0 ? '#FFFBEA' : IVORY);
  }
  for (const [k, s] of states) {
    if (s.phase === 'fly') { drawTrail(s, k, t); txtGlow(P[k].name, s.x, s.y, s.fs, 1, 'rgba(255,210,120,1)', '900'); }
    if (s.phase === 'call') {
      ctx.save(); ctx.globalCompositeOperation = 'lighter';
      const rr = ctx.createRadialGradient(s.x, s.y, 10, s.x, s.y, 260 * s.u); rr.addColorStop(0, `rgba(255,220,150,${.45 * s.u})`); rr.addColorStop(1, 'rgba(255,200,120,0)');
      ctx.fillStyle = rr; ctx.beginPath(); ctx.arc(s.x, s.y, 260, 0, 6.283); ctx.fill(); ctx.restore();
      txtGlow(P[k].name, s.x, s.y, s.fs, 1, 'rgba(255,210,120,1)', '900');
    }
  }
  drawBursts(t);
  drawFinale(t);
}

/* ── 소리 (WebAudio · 직접 만든 효과음) ── */
const PENTA = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.5, 1174.66, 1318.5];
function bell(ac, out, at, f, v, d) {
  for (const [m, a, dd] of [[1, 1, 1], [2.76, .35, .55], [5.4, .18, .35], [8.93, .08, .22]]) {
    const o = ac.createOscillator(), g = ac.createGain(); o.type = 'sine'; o.frequency.value = f * m;
    g.gain.setValueAtTime(0, at); g.gain.linearRampToValueAtTime(v * a, at + .006); g.gain.exponentialRampToValueAtTime(.0001, at + d * dd);
    o.connect(g); g.connect(out); o.start(at); o.stop(at + d * dd + .05);
  }
}
let NOISE = null;
function noise(ac) { if (NOISE && NOISE.sampleRate === ac.sampleRate) return NOISE; const b = ac.createBuffer(1, ac.sampleRate * 2, ac.sampleRate); const d = b.getChannelData(0); const r = rng(5); for (let i = 0; i < d.length; i++) d[i] = r() * 2 - 1; NOISE = b; return b; }
function whoosh(ac, out, at, dur, f0, f1, v) {
  const s = ac.createBufferSource(); s.buffer = noise(ac); s.loop = true;
  const bp = ac.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 1.4; bp.frequency.setValueAtTime(f0, at); bp.frequency.exponentialRampToValueAtTime(f1, at + dur);
  const g = ac.createGain(); g.gain.setValueAtTime(0, at); g.gain.linearRampToValueAtTime(v, at + dur * .6); g.gain.linearRampToValueAtTime(0, at + dur);
  s.connect(bp); bp.connect(g); g.connect(out); s.start(at); s.stop(at + dur + .05);
}
function schedule(ac, out, base, from) {
  const ev = (t, fn) => { if (t >= from) fn(base + t - from); };
  ev(.2, a => { whoosh(ac, out, a, 1.6, 300, 2400, .18); bell(ac, out, a + 1, 1046.5, .12, 2.2); });
  for (let i = 0; i < 9; i++) ev(T_APPEAR0 + i * .18, a => bell(ac, out, a, PENTA[(i * 3) % 8] * 2, .05, .9));
  ev(T_SWIRL, a => whoosh(ac, out, a, T_VORTEX - T_SWIRL + .6, 160, 3800, .22));
  { let tt = T_SWIRL; let k = 0; while (tt < T_VORTEX + .3) { const u = seg(tt, T_SWIRL, T_VORTEX); const tc = tt; const kk = k; ev(tc, a => bell(ac, out, a, PENTA[kk % 8] * (u > .5 ? 2 : 1), .06 + .05 * u, .8)); tt += lerp(.24, .07, u); k++; } }
  for (let k = 0; k < N; k++) {
    const g = P[k].g;
    if (k < CALLS) ev(exits[k], a => { whoosh(ac, out, a, .55, 600, 3000, .14); bell(ac, out, a + .05, 1567.98, .09, 1.2); });
    else ev(exits[k], a => whoosh(ac, out, a, .5, 900, 2600, .05));
    ev(lands[k], a => bell(ac, out, a, PENTA[g % PENTA.length], .2, 1.5));
  }
  ev(T_FIN, a => { [261.63, 329.63, 392.0, 523.25, 659.25].forEach((f, i) => bell(ac, out, a + i * .03, f, .16, 3.4)); whoosh(ac, out, a, 2.2, 2000, 8000, .12);
    for (let i = 0; i < 14; i++) bell(ac, out, a + .25 + i * .07, PENTA[i % 8] * 2, .06, .9); });
}
function wavB64(buf) {
  const ch = buf.numberOfChannels, len = buf.length, sr = buf.sampleRate, out = new DataView(new ArrayBuffer(44 + len * ch * 2));
  const ws = (o, s) => { for (let i = 0; i < s.length; i++) out.setUint8(o + i, s.charCodeAt(i)); };
  ws(0, 'RIFF'); out.setUint32(4, 36 + len * ch * 2, true); ws(8, 'WAVE'); ws(12, 'fmt '); out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, ch, true);
  out.setUint32(24, sr, true); out.setUint32(28, sr * ch * 2, true); out.setUint16(32, ch * 2, true); out.setUint16(34, 16, true); ws(36, 'data'); out.setUint32(40, len * ch * 2, true);
  const data = []; for (let c = 0; c < ch; c++) data.push(buf.getChannelData(c));
  let o = 44; for (let i = 0; i < len; i++) for (let c = 0; c < ch; c++) { const v = Math.max(-1, Math.min(1, data[c][i])); out.setInt16(o, v * 32767, true); o += 2; }
  let s = ''; const u8 = new Uint8Array(out.buffer); for (let i = 0; i < u8.length; i += 32768) s += String.fromCharCode.apply(null, u8.subarray(i, i + 32768)); return btoa(s);
}
window.__renderAudio = async (secs) => {
  const ac = new OfflineAudioContext(2, Math.ceil(44100 * secs), 44100);
  const comp = ac.createDynamicsCompressor(); comp.connect(ac.destination);
  schedule(ac, comp, 0, 0);
  return wavB64(await ac.startRendering());
};

/* ── 실행 ── */
window.__T_END = T_FIN + 4;
window.__frame = t => frame(t);
async function main() {
  // 한글 웹글꼴은 글자 묶음별로 나뉘어 있어서, 화면에 나올 글자(이름 전부·제목·안내)를 미리 받아 둠(최대 2.5초 기다림)
  const ALL = [DATA.title || '마법의 분임 배정식', DATA.event || '', ...(DATA.groups || []).map(g => g.label), ...seq.map(x => x[0]),
    '마법진이 깨어나는 중… 오늘 함께할 모두의 이름이 떠오릅니다 섞이는 정하는 배정 완료! 내 이름을 찾아 우리 분임 자리로 모여 주세요 곧 시작됩니다 0123456789명'].join(' ');
  const fonts = [`900 66px ${SERIF}`, `600 30px ${SERIF}`, `500 30px ${SANS}`, `600 22px ${SANS}`];
  await Promise.race([Promise.all(fonts.map(f => document.fonts.load(f, ALL).catch(() => 0))), new Promise(r => setTimeout(r, 2500))]);
  buildBanners(); buildCircle();
  if (document.fonts && document.fonts.addEventListener) document.fonts.addEventListener('loadingdone', buildBanners);   // 글꼴이 늦게 와도 깃발 글씨를 다시 그림
  window.__ready = true;
  if (window.__capture) return;
  const since = Math.max(0, +DATA.since || 0);
  const late = !IDLE && (DATA.mode === 'final' || since > T_FIN + 3);   // 끝난 뒤에 다시 열리면(새로 고침 등) 결과만
  const skip = !IDLE && !late && since > 6 ? since : 0;                // 하는 도중에 다시 열리면 그 자리부터 이어서
  const t0 = performance.now();
  const TL = a => IDLE ? Math.min(a, 2) : late ? a + T_FIN + 6 : a + skip;
  if (!late && !IDLE) {
    try {
      const AC = window.AudioContext || window.webkitAudioContext; const ac = new AC();
      const comp = ac.createDynamicsCompressor(); comp.connect(ac.destination);
      const go = () => schedule(ac, comp, ac.currentTime + .05, TL((performance.now() - t0) / 1000));
      if (ac.state === 'running') go();
      else { ac.resume().then(() => { if (ac.state === 'running') go(); }).catch(() => {});
        setTimeout(() => { if (ac.state !== 'running') { const b = document.getElementById('snd'); b.style.display = 'block'; b.onclick = () => { ac.resume().then(go); b.style.display = 'none'; }; } }, 600); }
    } catch (e) {}
  }
  let last = 0;
  const loop = ms => {
    const a = (ms - t0) / 1000, t = TL(a);
    if ((IDLE || t > T_FIN + 8) && ms - last < 33) { requestAnimationFrame(loop); return; }   // 기다리는 중·끝난 뒤에는 30fps로 아껴서
    last = ms; frame(t, a); requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}
main();
</script></body></html>
"""


DRUMROLL = os.path.join(store.BASE, "drumroll.mp3")      # 결과 발표 두구두구 화면에서 반복되는 드럼롤
CELEBRATE = os.path.join(store.BASE, "celebrate.mp3")    # 최우수 공개 때 나오는 축하 음악(심벌 '짠!' + 밴드 버전 Jingle Bells)
_CONF_COLORS = ["#F5C542", "#D8394A", "#2FA35F", "#F4EAD5", "#D6B676", "#6EC6FF", "#FF9BD2"]


def confetti_html(n: int = 130, burst: int = 36) -> str:
    """꽃가루: 양쪽 아래에서 '펑' 터지는 폭죽 + 위에서 쉬지 않고 떨어지는 종이 조각.
    (Streamlit 마크다운은 인라인 CSS 변수(--x)를 망가뜨리므로 움직임은 모두 클래스·keyframes로만 정함)"""
    r = random.Random(2026)
    bits = []
    for k in range(n):
        shape = " r" if k % 4 == 0 else (" s" if k % 4 == 1 else "")
        bits.append(f'<span class="f{k % 6}{shape}" style="left:{r.uniform(0, 100):.1f}%;background:{_CONF_COLORS[k % len(_CONF_COLORS)]};'
                    f'animation-duration:{r.uniform(3.4, 6.8):.2f}s;animation-delay:-{r.uniform(0, 6.8):.2f}s"></span>')
    for k in range(burst):
        side = "bl" if k % 2 == 0 else "br"
        shape = " r" if k % 3 == 0 else ""
        bits.append(f'<span class="{side} b{(k // 2) % 4}{shape}" style="background:{_CONF_COLORS[(k * 3) % len(_CONF_COLORS)]};'
                    f'animation-duration:{r.uniform(1.8, 2.8):.2f}s;animation-delay:{r.uniform(0, 0.35):.2f}s;margin-bottom:{r.uniform(0, 12):.1f}vh"></span>')
    return '<div class="sc-confetti" aria-hidden="true">' + "".join(bits) + "</div>"


def result_html(S: dict, n: int) -> str:
    """결과 발표: 최우수(1위) 한 팀. 처음엔 '두구두구…'로 가리고, 한 번 더 누르면 꽃가루·축하 음악과 함께 공개."""
    steps = store.award_steps(S)
    if not steps:
        return f'<div class="sc-intro"><div class="ev">{ESC(S["event"])}</div><div class="ttl">아직 표가 없어요</div></div>'
    s = steps[0]
    if n < len(steps):
        card = f'<div class="pd hide p1"><div class="aw">{ESC(s["award"])}</div><div class="q">?</div></div>'
        head, extra, cls = "두구두구…", "", ""
    else:
        body = "".join(f'<div class="gn">{ESC(S["names"][x["g"] - 1])}</div><div class="gt">{ESC(_title(x["g"]))}</div>'
                       f'<div class="gv">{x["votes"]}표</div>' for x in s["groups"])
        tie = "공동 " if len(s["groups"]) > 1 else ""
        card = (f'<div class="pd p1 win"><div class="aw">🏆 {ESC(s["award"])}</div><div class="rk">{tie}1위</div>{body}</div>')
        head, extra, cls = "축하합니다!", confetti_html(), " shine"
    return (extra + f'<div class="sc-intro wide"><div class="ev" style="max-width:60vw">{ESC(S["event"])} · 투표 결과 발표</div>'
            f'<div class="ttl{cls}" style="font-size:clamp(2.6rem,5.4vw,5.8rem)">{head}</div><div class="sc-podium">{card}</div></div>')


def screen_view():
    md(SCREEN_CSS)
    S = store.get_settings()
    scr = store.screen_get()
    mode = scr["mode"]
    r = store.get_result(scr["rid"]) if mode == "play" and scr["rid"] else None
    if (mode == "play" and not r) or (mode == "intro" and not scr["g"]):
        mode = "board"
    if mode == "deck" and not deck_steps():
        mode = "board"
    if mode == "sort":
        T = store.team_get()
        if not T["seq"] and T["show_mode"] != "idle":
            mode = "board"
    # 영상을 트는 중에는 '틀 영상'이 바뀔 때만 다시 그림(분임이 기획서를 고쳐도 영상이 처음부터 다시 시작하지 않게). 배정식도 마찬가지
    tok = (lambda: f"play|{store.screen_get()}") if r else (store.sort_token if mode == "sort" else store.board_token)
    st.session_state["scr_tok"] = tok()
    deck_keys()
    if store.rehearsal_info():
        md('<div style="position:fixed;top:.6vh;right:2.4vw;z-index:999;font-family:\'Noto Serif KR\',serif;font-weight:600;color:#3A1F17;background:#D6B676;'
           'border-radius:999px;padding:.1rem .9rem;font-size:clamp(.85rem,1.1vw,1.2rem)">🧪 리허설</div>')
    if mode not in ("play", "deck", "sort"):
        md(garland_svg())
    if mode == "deck":
        deck_screen(scr["n"])
    elif mode == "sort":
        sort_screen(S)
    elif mode == "intro":
        md(f'<div class="sc-sleigh">{_SLEIGH}</div><div class="sc-tree">{tree_svg("tr")}</div>')
        md(intro_html(int(scr["g"]), S))
    elif mode == "end":
        md(vote_screen_html(S))
    elif mode == "result":
        md(result_html(S, scr["n"]))
        steps = store.award_steps(S)
        if steps and scr["n"] >= len(steps):
            if os.path.exists(CELEBRATE):
                with st.container(key="aud_win"):
                    st.audio(CELEBRATE, format="audio/mpeg", autoplay=True)      # 최우수 공개: 짠! + 캐럴 축하 음악(한 번)
        elif steps and os.path.exists(DRUMROLL):
            with st.container(key="aud_roll"):
                st.audio(DRUMROLL, format="audio/mpeg", autoplay=True, loop=True)  # 두구두구: 공개 버튼 누를 때까지 드럼롤 반복
    elif r:
        R = store.get_request(r["g"])
        md(f'<div class="sc-head"><b>{ESC(S["names"][r["g"] - 1])}</b><span>{ESC(R["data"]["title"] or R["data"]["topic"])}</span></div>')
        if r["video"]:
            st.video(r["path"], format="video/" + ("quicktime" if r["ext"] == "mov" else r["ext"]), autoplay=True)
        else:
            st.image(r["path"], use_container_width=True)
    else:
        # 대기 판 = 행사 메인 화면: 공통 QR(찍으면 분임 고르기) + 분임별 진행 상태
        url = base_url()
        cards = []
        for R in store.all_requests():
            g = R["g"]
            cards.append(f'<div class="sc-card"><div class="n">{ESC(S["names"][g - 1])} {badge(R["status"])}</div>'
                         f'<div class="t">{ESC(R["data"]["title"] or R["data"]["topic"])}</div></div>')
        qr = entry_qr(url) if url else ""
        md(f'<div class="sc-sleigh">{_SLEIGH}</div><div class="sc-tree">{tree_svg("tr")}</div>')
        md(f'<div class="sc-intro entry"><div class="ev">WINTER PREMIERE</div><div class="sc-title">{ESC(S["event"])}</div>'
           f'<div class="sc-sub">AI 모션그래픽 광고제</div>'
           + (f'<div class="sc-entry"><img src="{qr}" alt="행사 QR"></div>' if qr else "")
           + '<div class="sc-how">휴대폰 카메라로 QR을 찍고 <b>우리 분임</b>을 골라 주세요</div>'
           + '<div class="sc-board">' + "".join(cards) + "</div></div>")

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
elif view == "vote":
    vote_view()
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

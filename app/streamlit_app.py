"""PlanB Streamlit demo.  Run:  streamlit run app/streamlit_app.py"""
from __future__ import annotations

import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from planb.agent import PlanBAgent  # noqa: E402
from planb.data import load_bookings, load_trip, load_world  # noqa: E402
from planb.llm import LLMClient  # noqa: E402
from planb.models import Activity, Budget, Preferences, new_id  # noqa: E402
from planb.planner import generate_itinerary  # noqa: E402
from planb.repair import build_proposal  # noqa: E402
from planb.store import ApprovalError, TripStore  # noqa: E402

st.set_page_config(page_title="PlanB — AI Travel Copilot", page_icon="🧭", layout="wide")

PRESETS = {
    "🧳 多待一天（Story D）": "我想在东京多待一天，12月13日再回来，之前安排好的景点尽量不要改。",
    "🌧️ 12/11 上午暴雨": "天气预报说12月11日上午8点到下午1点有暴雨，帮我调整一下行程。",
    "🌧️ 12/10 下午大雨": "12月10日下午1点到6点会下大雨，请帮我改一下当天的安排。",
    "🚫 博物馆闭馆": "东京国立博物馆12月12日临时闭馆，帮我换个安排。",
    "🚫 teamLab 闭馆（含门票）": "teamLab Planets 通知12月11日全天闭馆，我的行程和门票怎么办？",
    "🚇 地铁延误": "12月11日早上地铁大面积延误，我10点半之前都到不了任何景点。",
    "🏠 提前一天回国": "家里有事，我需要提前一天回去，改成12月11日晚上的航班。",
    "⛔ 预约冲突（无解）": "teamLab 通知我12月11日的入场时间被改到了晚上18:00，而且不能再改。但我18:30在银座订了寿司，这个不能动。",
}
CHANGE_LABEL = {"keep": "保留", "shift": "调整时间", "replace": "替换", "remove": "删除", "add": "新增", "extend": "随行程延长"}
IMPACT_LABEL = {"unaffected": "不受影响", "change_required": "需要变更", "potentially_affected": "可能受影响",
                "unknown": "未知"}


def yuan(minor) -> str:
    return "未知" if minor is None else f"¥{minor / 100:,.0f}"


def init_state(reset: bool = False) -> None:
    if reset or "store" not in st.session_state:
        world = load_world()
        st.session_state.store = TripStore(load_trip(), load_bookings(), world)
        st.session_state.llm = LLMClient()
        st.session_state.agent = PlanBAgent(st.session_state.store, st.session_state.llm)
        st.session_state.turns = []
        st.session_state.flash = None


init_state()
store: TripStore = st.session_state.store
agent: PlanBAgent = st.session_state.agent
world = store.world


def run_agent(text: str) -> None:
    with st.spinner("PlanB 正在分析…"):
        turn = agent.handle(text)
    st.session_state.turns.append(turn)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("🧭 PlanB")
    st.caption("AI Travel Copilot · 约束感知重规划 + 订单费用分析")
    t = store.trip
    st.markdown(f"**{t.title}**  \n{t.start_date} → {t.end_date}  \nrevision **{t.revision}** · "
                f"{len([a for a in t.activities if a.category in ('visit', 'meal')])} 项活动")
    st.markdown(f"LLM：`{st.session_state.llm.describe()}`")
    if st.session_state.llm.is_mock:
        st.info("未配置 LLM_API_KEY：请求解析使用规则解析器，解释使用模板。确定性引擎完全可用。")
    if st.button("↺ 重置为演示数据", use_container_width=True):
        init_state(reset=True)
        st.rerun()
    st.divider()
    st.caption("⚠️ 所有地点、价格、退改规则均为**模拟演示数据**，不是实时信息。PlanB 不会真实改签、订房或付款。")

st.title("PlanB — AI Travel Copilot")
if st.session_state.flash:
    kind, msg = st.session_state.flash
    getattr(st, kind)(msg)
    st.session_state.flash = None

tab_trip, tab_ai, tab_cmp, tab_book, tab_hist, tab_new = st.tabs(
    ["🗓 行程", "🤖 Copilot / 突发事件", "📋 方案对比与审批", "🧾 订单", "🕘 历史", "🆕 新建行程"])


# ---------------------------------------------------------------------------
# Itinerary
# ---------------------------------------------------------------------------
def day_table(trip, highlight: dict[str, str] | None = None) -> dict:
    days = {}
    for a in trip.sorted_activities():
        p = world.place(a.place_id)
        d = world.local(a.start_at).date()
        days.setdefault(d, []).append({
            "时间": f"{world.local(a.start_at):%H:%M}–{world.local(a.end_at):%H:%M}",
            "活动": a.title,
            "地点": p.name if p else f"❓{a.place_id}",
            "室内": "室内" if p and p.indoor else "户外",
            "锁定": "🔒" if a.is_locked else "",
            "预估门票": yuan(a.estimated_cost_minor) if a.category in ("visit", "meal") else "",
            **({"变化": highlight.get(a.activity_id, "")} if highlight is not None else {}),
            "id": a.activity_id,
        })
    return days


with tab_trip:
    left, right = st.columns([3, 2])
    with left:
        for d, rows in day_table(store.trip).items():
            st.subheader(f"{d:%m月%d日} ({'一二三四五六日'[d.weekday()]})")
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    with right:
        pts = [{"lat": world.place(a.place_id).latitude, "lon": world.place(a.place_id).longitude}
               for a in store.trip.activities if world.place(a.place_id)]
        st.subheader("地图")
        st.map(pd.DataFrame(pts), size=60)

        st.subheader("✏️ 手动编辑")
        st.caption("所有手动修改同样先经过约束验证和订单影响分析，在「方案对比」中确认后才会生效。")
        acts = {f"{world.local(a.start_at):%m-%d %H:%M} {a.title}": a for a in store.trip.sorted_activities()}
        choice = st.selectbox("选择活动", list(acts))
        a = acts[choice]
        mode = st.radio("操作", ["修改时间", "删除", "锁定/解锁"], horizontal=True)
        if mode == "修改时间":
            c1, c2, c3 = st.columns(3)
            nd = c1.date_input("日期", world.local(a.start_at).date())
            ns = c2.time_input("开始", world.local(a.start_at).time(), step=900)
            ne = c3.time_input("结束", world.local(a.end_at).time(), step=900)
            if st.button("生成修改方案"):
                cand = store.trip.model_copy(deep=True)
                act = cand.activity(a.activity_id)
                act.start_at = datetime.combine(nd, ns, tzinfo=world.tz)
                act.end_at = datetime.combine(nd, ne, tzinfo=world.tz)
                p = build_proposal(store.trip, cand, world, store.bookings, label=f"手动修改：{a.title}")
                store.add_proposal(p)
                st.session_state.flash = ("info", "已生成手动修改方案，请到「方案对比与审批」查看验证结果。")
                st.rerun()
        elif mode == "删除":
            if st.button("生成删除方案"):
                cand = store.trip.model_copy(deep=True)
                cand.activities = [x for x in cand.activities if x.activity_id != a.activity_id]
                p = build_proposal(store.trip, cand, world, store.bookings, label=f"手动删除：{a.title}")
                store.add_proposal(p)
                st.session_state.flash = ("info", "已生成删除方案，请到「方案对比与审批」确认。")
                st.rerun()
        else:
            st.write(f"当前：{'🔒 已锁定' if a.is_locked else '未锁定'}")
            if st.button("切换锁定状态"):
                store.trip.activity(a.activity_id).is_locked = not a.is_locked
                st.rerun()

        with st.expander("➕ 添加活动"):
            options = {f"{p.name_zh or p.name}（{'室内' if p.indoor else '户外'}）": p for p in world.places.values()
                       if p.category not in ("airport", "hotel")}
            pl = options[st.selectbox("地点", list(options))]
            c1, c2 = st.columns(2)
            ad = c1.date_input("日期", store.trip.start_date, key="add_d")
            at = c2.time_input("开始", time(15, 0), step=900, key="add_t")
            if st.button("生成添加方案"):
                cand = store.trip.model_copy(deep=True)
                s = datetime.combine(ad, at, tzinfo=world.tz)
                cand.activities.append(Activity(activity_id=new_id("act"), place_id=pl.place_id,
                                                title=pl.name_zh or pl.name, start_at=s,
                                                end_at=s + timedelta(minutes=pl.suggested_visit_minutes),
                                                category="meal" if pl.category == "food" else "visit",
                                                estimated_cost_minor=pl.entry_cost_minor))
                store.add_proposal(build_proposal(store.trip, cand, world, store.bookings,
                                                  label=f"手动添加：{pl.name_zh or pl.name}"))
                st.session_state.flash = ("info", "已生成添加方案，请到「方案对比与审批」确认。")
                st.rerun()


# ---------------------------------------------------------------------------
# Copilot
# ---------------------------------------------------------------------------
with tab_ai:
    st.caption("用自然语言描述变化，或点击模拟事件。PlanB 只会生成候选方案，需要你确认后才会修改行程。")
    cols = st.columns(4)
    for i, (label, text) in enumerate(PRESETS.items()):
        if cols[i % 4].button(label, use_container_width=True):
            run_agent(text)
    prompt = st.chat_input("例如：我想在东京多待一天，12月13日再回来")
    if prompt:
        run_agent(prompt)
    for turn in reversed(st.session_state.turns[-6:]):
        with st.chat_message("user"):
            st.write(turn.user_text)
        with st.chat_message("assistant", avatar="🧭"):
            badge = {"WAITING_FOR_APPROVAL": "✅ 已生成候选方案，等待你确认", "INFEASIBLE": "⛔ 无法在硬约束内完成",
                     "NEEDS_INFORMATION": "❔ 需要更多信息"}.get(turn.state, turn.state)
            st.markdown(f"**{badge}**")
            st.markdown(turn.message)
            if turn.state == "WAITING_FOR_APPROVAL":
                st.caption("👉 到「📋 方案对比与审批」查看差异、订单影响和费用明细。")
            with st.expander("Agent 执行轨迹（后端状态机）"):
                if turn.event:
                    st.json(turn.event.model_dump(mode="json", exclude_none=True))
                st.dataframe(pd.DataFrame([{"状态": s.state, "工具": s.tool or "", "说明": s.detail,
                                            "耗时 ms": round(s.duration_ms, 1)} for s in turn.steps]),
                             hide_index=True, use_container_width=True)
                u = turn.usage
                st.caption(f"LLM 调用 {u.calls} 次 · tokens {u.prompt_tokens + u.completion_tokens}")


# ---------------------------------------------------------------------------
# Proposal comparison & approval
# ---------------------------------------------------------------------------
with tab_cmp:
    pending = store.pending()
    if not pending:
        st.info("暂无待确认的方案。在「Copilot」中提出修改，或在「行程」中手动编辑。")
    else:
        names = {f"{p.label or '方案'} · {p.proposal_id}": p for p in pending}
        p = names[st.radio("待确认方案", list(names), horizontal=True)]
        v = p.validation
        c1, c2, c3, c4 = st.columns(4)
        status_txt = {"valid": "✅ 已知硬约束全部通过", "invalid": "⛔ 违反硬约束", "unknown": "⚠️ 部分条件无法验证"}
        c1.metric("约束验证", status_txt[v.feasibility_status].split(" ")[0])
        c1.caption(status_txt[v.feasibility_status][2:])
        c2.metric("改动活动数", p.score.get("n_changes", 0))
        ce = p.cost_estimate
        c3.metric("新增支出（订单相关）", yuan(ce.total_additional_minor) if ce.is_complete else f"已知 {yuan(ce.known_additional_minor)} + 未知")
        c3.caption("费用完整" if ce.is_complete else f"{len(ce.unknown_components)} 项费用未知，不计为 0")
        c4.metric("不可退损失（非现金）", yuan(ce.forfeited_minor))

        for vv in v.hard_violations:
            st.error(f"[{vv.rule}] {vv.message}")
        for vv in v.unknown_constraints:
            st.warning(f"[未验证 {vv.rule}] {vv.message}")
        for vv in v.soft_warnings:
            st.caption(f"提示 [{vv.rule}] {vv.message}")

        st.subheader("原计划 vs 新方案")
        change_of = {c.activity_id: CHANGE_LABEL[c.change_type] for c in p.changes}
        lc, rc = st.columns(2)
        with lc:
            st.markdown("**原计划**")
            for d, rows in day_table(store.trip, {k: v for k, v in change_of.items()}).items():
                st.caption(f"{d:%m-%d}")
                st.dataframe(pd.DataFrame(rows)[["时间", "活动", "锁定", "变化"]], hide_index=True,
                             use_container_width=True)
        with rc:
            st.markdown("**新方案**")
            for d, rows in day_table(p.proposed_trip, change_of).items():
                st.caption(f"{d:%m-%d}")
                df = pd.DataFrame(rows)[["时间", "活动", "锁定", "变化"]]
                df["变化"] = df["变化"].replace("", "新增")
                st.dataframe(df.style.apply(lambda r: ["background-color: rgba(255,200,0,.18)" if r["变化"] not in ("保留",) else "" for _ in r], axis=1),
                             hide_index=True, use_container_width=True)

        st.subheader("订单影响")
        st.dataframe(pd.DataFrame([{"订单": store.find_booking(i.booking_id).title, "影响": IMPACT_LABEL[i.status],
                                    "需要的操作": i.required_action or "", "原因": i.reason}
                                   for i in p.booking_impacts]), hide_index=True, use_container_width=True)

        st.subheader("费用明细（相对原计划的增量）")
        if ce.components:
            st.dataframe(pd.DataFrame([{"项目": c.kind, "订单": c.booking_id, "金额": yuan(c.amount_minor),
                                        "类型": "现金" if c.cash else "经济损失(非现金)", "依据": c.basis}
                                       for c in ce.components]), hide_index=True, use_container_width=True)
        else:
            st.write("无订单相关费用变化。")
        for a in ce.assumptions:
            st.caption(f"· {a}")

        if p.explanation:
            st.subheader("PlanB 的解释")
            st.markdown(p.explanation)

        b1, b2, _ = st.columns([1, 1, 4])
        if b1.button("✅ 批准并更新行程", type="primary", disabled=bool(v.hard_violations)):
            try:
                store.approve(p.proposal_id)
                todo = [f"{store.find_booking(i.booking_id).title}（{i.required_action}）"
                        for i in p.booking_impacts if i.status == "change_required"]
                msg = f"已更新 PlanB 行程（revision {store.trip.revision}）。"
                if todo:
                    msg += " ⚠️ PlanB **没有**真实改签/续住/取消，请自行在供应商处办理：" + "；".join(todo)
                st.session_state.flash = ("success", msg)
            except ApprovalError as e:
                st.session_state.flash = ("error", str(e))
            st.rerun()
        if b2.button("❌ 拒绝"):
            store.reject(p.proposal_id)
            st.session_state.flash = ("info", "已拒绝该方案，行程未改变。")
            st.rerun()


# ---------------------------------------------------------------------------
# Bookings & history
# ---------------------------------------------------------------------------
with tab_book:
    for b in store.bookings:
        with st.expander(f"{b.title} · 已付 {yuan(b.paid_minor)} · 状态 {b.booking_status}"):
            st.write(f"服务时间：{world.local(b.service_start):%m-%d %H:%M} → {world.local(b.service_end):%m-%d %H:%M}"
                     if b.service_start else "服务时间未知")
            st.write("退改规则：", b.policy.conditions or "—")
            st.json(b.policy.model_dump(mode="json", exclude_none=True))
            if b.quotes:
                st.dataframe(pd.DataFrame([{"报价": q.quote_id, "类型": q.action, "目标": f"{q.target_start}",
                                            "金额": yuan(q.amount_minor), "可用": q.available, "说明": q.notes}
                                           for q in b.quotes]), hide_index=True, use_container_width=True)

with tab_hist:
    if not store.history:
        st.info("暂无已确认的变更。")
    for h in reversed(store.history):
        with st.expander(f"rev {h.revision_before} → {h.revision_after} · {h.reason} · {h.committed_at:%H:%M:%S}"):
            for c in h.changes:
                st.write(f"- {CHANGE_LABEL[c.change_type]}：{(c.before or c.after or {}).get('title')} {c.reason}")
            for a in h.booking_actions:
                st.write(f"- 待办（外部）：{a}")


# ---------------------------------------------------------------------------
# New trip (Story A)
# ---------------------------------------------------------------------------
with tab_new:
    st.caption("根据偏好从本地东京地点库生成初始行程（确定性排程，保证可验证）。生成后会替换当前演示行程，且不含订单。")
    c1, c2 = st.columns(2)
    sd = c1.date_input("出发日期", date(2026, 12, 10))
    ed = c2.date_input("返程日期", date(2026, 12, 12))
    interests = st.multiselect("兴趣", ["photography", "nature", "culture", "art", "shopping", "anime", "food",
                                         "city_view", "science"], ["photography", "nature"])
    pace = st.select_slider("节奏", ["relaxed", "normal", "packed"], "relaxed")
    budget = st.number_input("预算（元，不含机酒）", 0, 100000, 3000, step=500)
    c3, c4 = st.columns(2)
    arr = c3.time_input("到达机场时间（第一天）", time(11, 30))
    dep = c4.time_input("返程起飞时间（最后一天）", time(18, 0))
    if st.button("生成初始行程", type="primary"):
        trip = generate_itinerary(world, "Tokyo", sd, ed, Preferences(interests=interests, pace=pace),
                                  Budget(amount_minor=budget * 100),
                                  arrival_at=datetime.combine(sd, arr, tzinfo=world.tz),
                                  departure_at=datetime.combine(ed, dep, tzinfo=world.tz))
        st.session_state.store = TripStore(trip, [], world)
        st.session_state.agent = PlanBAgent(st.session_state.store, st.session_state.llm)
        st.session_state.turns = []
        st.session_state.flash = ("success", f"已生成 {len(trip.activities)} 项活动的初始行程。")
        st.rerun()

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import random
import re
import time
from typing import Any

from pydantic import BaseModel, Field

from app.services.graph.state import AgentState, validate_task_plan_items

try:
    from app.services.graph.metrics import NodeMetrics, inc_counter
except ImportError:
    class NodeMetrics:
        def __init__(self, *a, **kw):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
    def inc_counter(*a, **kw):
        pass

logger = logging.getLogger(__name__)

LLM_MODE = os.getenv("LLM_MODE", "mock")

TASK_STEP_MAX_RETRY = int(os.getenv("TASK_STEP_MAX_RETRY", "2"))
TASK_STEP_TIMEOUT_S = int(os.getenv("TASK_STEP_TIMEOUT_S", "300"))
TASK_MIN_OUTPUT_LEN = int(os.getenv("TASK_MIN_OUTPUT_LEN", "50"))
MAX_REMEDY_STEPS = int(os.getenv("MAX_REMEDY_STEPS", "3"))


def _get_traced_execution():
    try:
        from app.services.observability.tracing import traced_execution
        return traced_execution
    except Exception:
        from contextlib import contextmanager

        @contextmanager
        def _mock_span(span_name: str, attributes: dict[str, Any]):
            class Dummy:
                def set_attribute(self, *a, **kw):
                    pass
            yield Dummy()

        return _mock_span


async def _detect_intent(raw_query: str) -> tuple[str, float]:
    if LLM_MODE == "real":
        try:
            from app.services.llm.client import detect_intent_llm
            return await detect_intent_llm(raw_query)
        except Exception as e:
            logger.warning(f"LLM调用失败降级mock: {e}")
    return await _mock_detect_intent(raw_query)


async def _extract_entities(raw_query: str, intent: str) -> dict[str, Any]:
    if LLM_MODE == "real":
        try:
            from app.services.llm.client import extract_entities_llm
            return await extract_entities_llm(raw_query, intent)
        except Exception as e:
            logger.warning(f"LLM调用失败降级mock: {e}")
    return await _mock_extract_entities(raw_query, intent)


async def _route_via_llm(raw_query: str) -> tuple[str, dict[str, Any], float]:
    if LLM_MODE == "real":
        try:
            from app.services.llm.client import route_via_llm_real
            return await route_via_llm_real(raw_query)
        except Exception as e:
            logger.warning(f"LLM调用失败降级mock: {e}")
    return await _mock_route_via_llm(raw_query)


async def _rewrite_query_pipeline(raw_query: str, entities: dict) -> tuple[str, list[str]]:
    if LLM_MODE == "real":
        try:
            from app.services.llm.client import rewrite_query_pipeline_real
            return await rewrite_query_pipeline_real(raw_query, entities)
        except Exception as e:
            logger.warning(f"LLM调用失败降级mock: {e}")
    return await _mock_rewrite_query(raw_query, entities)


async def _mock_detect_intent(raw_query: str) -> tuple[str, float]:
    q = raw_query.lower()
    if "启动" in q or "打开" in q:
        return "app_launch", 0.92
    elif "结束" in q or "杀掉" in q:
        return "app_kill", 0.90
    return "unknown", 0.4


async def _mock_extract_entities(raw_query: str, intent: str) -> dict[str, Any]:
    return {"raw": raw_query, "hint": "mock_entities"}


async def _mock_route_via_llm(raw_query: str) -> tuple[str, dict[str, Any], float]:
    q = raw_query.lower()
    if "启动" in q or "打开" in q:
        return "app_launch_agent_node", {"action": "launch", "path": "C:\\Windows\\notepad.exe"}, 0.91
    elif "结束" in q or "杀掉" in q:
        return "app_launch_agent_node", {"action": "kill", "name": "notepad.exe"}, 0.88
    elif "监控" in q or "cpu" in q or "内存" in q or "进程" in q:
        return "system_clean_agent_node", {"action": "scan"}, 0.85
    elif "清理" in q or "优化" in q or "垃圾" in q:
        return "system_clean_agent_node", {"action": "scan"}, 0.85
    elif "搜代码" in q or "找代码" in q or "code search" in q or "代码搜索" in q:
        return "code_search_node", {"query": raw_query, "search_type": ""}, 0.85
    elif "撰写" in q or "简报" in q or "报告" in q or "方案" in q:
        return "planning_node", {"task": raw_query}, 0.90
    elif "搭建" in q or "规划" in q or "面试" in q or "论文" in q or "材料" in q or "包" in q and "面试" in q:
        return "planning_node", {"task": raw_query}, 0.90
    elif "并行" in q or "对比摘要" in q:
        return "planning_node", {"task": raw_query}, 0.90
    elif "查文档" in q or "检索" in q or "知识库" in q or "rag" in q:
        return "rag_retrieve_node", {"query": raw_query}, 0.85
    elif "搜索" in q or "查一下" in q or "百度" in q:
        return "browser_agent_node", {"action": "search", "query": raw_query}, 0.85
    elif "安装" in q or "卸载" in q or "应用商店" in q:
        return "store_agent_node", {"action": "search", "query": raw_query}, 0.85
    elif "生成" in q or "写" in q or "创建项目" in q or "写代码" in q:
        return "content_gen_agent_node", {"action": "generate", "task": raw_query}, 0.85
    cultural_keywords = [
        "recommend", "like", "taste", "music", "movie", "film", "restaurant",
        "dining", "fashion", "travel", "artist", "brand", "book", "podcast",
        "推荐", "喜欢", "品味", "音乐", "电影", "餐厅", "美食", "时尚", "旅行",
        "歌手", "导演", "品牌", "书", "播客", "文化", "similar",
    ]
    if any(kw in q for kw in cultural_keywords):
        return "qloo_cultural_recommend_node", {"action": "cultural_recommend", "query": raw_query}, 0.88
    return "clarification_node", {}, 0.35


async def _mock_build_clarification_message(raw_query: str, intent: str, conf: float) -> dict[str, str]:
    return {"message": f"我没有理解你的指令，请重新描述。输入:{raw_query}，置信度{conf:.2f}"}


async def _mock_rewrite_query(raw_query: str, entities: dict) -> tuple[str, list[str]]:
    standalone = raw_query
    retrieval = [raw_query]
    if "记事本" in raw_query:
        standalone = "启动记事本应用程序"
        retrieval.append("启动记事本 notepad.exe")
    return standalone, retrieval


async def detect_intent_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("detect_intent"):
        traced_execution = _get_traced_execution()
        raw_query = state.get("raw_query", "")
        fb_mode = state.get("fast_brain_mode", "")
        fb_result = state.get("fast_brain_result", "")
        fb_confidence = state.get("fast_brain_confidence", 0.0)
        fb_intent = state.get("fast_brain_intent", "")
        try:
            review_hint = ""
            if fb_mode == "review_by_slow" and fb_result:
                review_hint = (
                    f"\n[快脑复核] 快脑初步判断: {fb_result}, "
                    f"置信度={fb_confidence:.2f}, 意图={fb_intent}。"
                    f"请优先校验快脑结论是否正确，可采纳、修正或推翻。"
                )
            with traced_execution("chat", {"gen_ai.operation.name": "chat", "gen_ai.node": "detect_intent", "gen_ai.user.query": raw_query[:200]}):
                intent, confidence = await _detect_intent(raw_query + review_hint)
            updates: dict[str, Any] = {"intent": intent, "intent_confidence": confidence}
            if fb_mode == "review_by_slow":
                updates["fast_brain_mode"] = "review_done"
            return updates
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"detect_intent异常:{str(e)}", "error_type": "business"}


async def extract_entities_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("extract_entities"):
        traced_execution = _get_traced_execution()
        raw_query = state.get("raw_query", "")
        intent = state.get("intent", "")
        try:
            with traced_execution("chat", {"gen_ai.node": "extract_entities"}):
                entities = await _extract_entities(raw_query, intent)
                standalone_q, retrieval_q_list = await _rewrite_query_pipeline(raw_query, entities)
            return {"entities": entities, "standalone_query": standalone_q, "retrieval_queries": retrieval_q_list}
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"extract_entities异常:{str(e)}", "error_type": "business"}


async def route_llm_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("route_llm"):
        traced_execution = _get_traced_execution()
        raw_query = state.get("raw_query", "")
        try:
            with traced_execution("chat", {"gen_ai.node": "route_llm"}):
                agent_name, agent_args, route_confidence = await _route_via_llm(raw_query)
            tool_search_q = agent_name.replace("_node", "").replace("_agent", "")
            return {
                "route_target": agent_name,
                "route_confidence": route_confidence,
                "agent_input": agent_args,
                "tool_search_query": tool_search_q,
            }
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"route_llm异常:{str(e)}", "error_type": "business"}


async def clarification_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("clarification_node"):
        inc_counter("graph_clarification_trigger_total")
        raw_query = state.get("raw_query", "")
        intent = state.get("intent", "")
        conf = state.get("intent_confidence", 0.0)
        try:
            msg = await _mock_build_clarification_message(raw_query, intent, conf)
            return {
                "needs_clarification": True,
                "clarification_message": msg["message"],
                # B6: 纯文本降级路径也提供结构化外壳（原因码 + 空选项按钮）
                "clarification_reason_code": "UNABLE_TO_PARSE",
                "clarification_options": [],
                "standalone_query": raw_query,
                "task_plan_enabled": False,
                "correction_signal": {},
            }
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"clarification异常:{str(e)}", "error_type": "business"}


async def risk_check_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("risk_check_node"):
        from app.services.graph.checkers import risk_check_node as _risk
        try:
            return _risk(state)
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"risk_check异常:{str(e)}", "error_type": "business"}


async def rag_retrieve_node(state: AgentState) -> dict[str, Any]:
    """
    RAG在线检索节点:
    R6: 向量+BM25混搭
    R7: 原查询永不替换
    R8: 鉴权前置ACL过滤
    R9: RRF重排+交叉编码器精排
    R10: 证据回溯+压幻觉
    R12: 矛盾片段检测
    """
    with NodeMetrics("rag_retrieve_node"):
        try:
            from app.services.rag import get_rag_service
            rag = get_rag_service()
            query = state.get("rag_query", "") or state.get("standalone_query", "") or state.get("raw_query", "")
            rewrite_queries = state.get("rag_rewrite_queries", [])
            user_acl = state.get("rag_user_acl", []) or (["admin"] if state.get("user_id", "") == "admin" else ["public"])
            result = await rag.query(
                query=query,
                user_acl_tags=user_acl,
                rewrite_queries=rewrite_queries if rewrite_queries else None,
                top_k=5,
                rerank_top_k=3,
                enable_rerank=False,
            )
            context_data = result.get("context", {})
            contradiction = result.get("contradiction", {})
            return {
                "rag_query": query,
                "rag_results": result.get("retrieval", {}).get("results", []),
                "rag_context": context_data.get("context", ""),
                "rag_evidence_ids": context_data.get("evidence_ids", []),
                "rag_evidence_map": result.get("retrieval", {}).get("evidence_map", {}),
                "rag_contradiction": contradiction,
                "rag_should_refuse": context_data.get("should_refuse", False),
                "evidence": {
                    "rag_context": context_data.get("context", "")[:500],
                    "rag_evidence_count": len(context_data.get("evidence_ids", [])),
                    "rag_contradiction": contradiction.get("has_contradiction", False),
                },
            }
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"rag_retrieve异常:{str(e)}", "error_type": "business"}


async def evolve_feedback_node(state: AgentState) -> dict[str, Any]:
    """
    自进化Agent节点:
    E1: 经验驱动 — 从任务反馈学习
    E2: 四类演化闭环
    E4: 评估/回滚/权限/供应链
    """
    with NodeMetrics("evolve_feedback_node"):
        try:
            from app.services.evolve import get_evolve_engine, EvolveLevel
            engine = get_evolve_engine()
            tool_result = state.get("tool_result", {})
            raw_query = state.get("raw_query", "")
            level = EvolveLevel(state.get("evolve_level", 1))
            record = engine.evolve_from_feedback(
                task_id=state.get("session_id", ""),
                task_result=tool_result,
                user_correction="",
                evaluation_score=1.0 if tool_result.get("ok") else 0.3,
                level=level,
            )
            context = engine.get_context_for_task(raw_query)
            return {
                "evolve_record_id": record.record_id,
                "evolve_level": int(record.level),
                "evolve_context": context,
                "evidence": {
                    "evolve_record_id": record.record_id,
                    "evolve_level": record.level.name,
                    "eval_passed": record.evaluation_passed,
                    "eval_score": record.evaluation_score,
                },
            }
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"evolve_feedback异常:{str(e)}", "error_type": "business"}


async def code_search_node(state: AgentState) -> dict[str, Any]:
    """
    智能代码搜索节点:
    S1: 搜索策略路由
    S2: 三类引擎(Glob/Grep/Semantic)
    S3: 权限检查+实时索引
    S7: 聚合输出
    """
    with NodeMetrics("code_search_node"):
        try:
            from app.services.code_search import get_code_search_service
            svc = get_code_search_service()
            query = state.get("raw_query", "")
            tool_args = state.get("tool_args", {})
            root_dir = tool_args.get("root_dir", ".")
            search_type = tool_args.get("search_type", "")
            file_glob = tool_args.get("file_glob", "")
            user_acl = ["admin"] if state.get("user_id", "") == "admin" else ["public"]
            result = await svc.search(
                query=query,
                root_dir=root_dir,
                search_type=search_type,
                file_glob=file_glob,
                max_results=20,
                user_acl=user_acl,
            )
            return {
                "code_search_type": result["search_type"],
                "code_search_results": result["results"],
                "code_search_stats": result["stats"],
                "evidence": {
                    "search_type": result["search_type"],
                    "result_count": len(result["results"]),
                    "stats": result["stats"],
                },
            }
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"code_search异常:{str(e)}", "error_type": "business"}


async def planning_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("planning_node"):
        raw_query = state.get("raw_query", "")
        intent = state.get("intent", "")
        route_target = state.get("route_target", "")
        taste_context = state.get("qloo_taste_context", "")
        try:
            if LLM_MODE == "real":
                from app.services.llm.client import plan_steps_llm
                is_multi, steps = await plan_steps_llm(raw_query, intent, route_target, taste_context=taste_context)
            else:
                is_multi, steps = _mock_plan_steps(raw_query, intent, route_target)
            if is_multi and steps:
                inc_counter("plan_multi_step_total")
                return {"is_multi_step": True, "plan_steps": steps, "current_step_index": 0, "step_results": []}
            return {"is_multi_step": False, "plan_steps": [], "current_step_index": 0}
        except Exception as e:
            logger.exception(e)
            return {"is_multi_step": False, "plan_steps": [], "current_step_index": 0}


def _mock_plan_steps(raw_query: str, intent: str, route_target: str) -> tuple[bool, list[dict[str, Any]]]:
    """ONLY FOR LOCAL DEBUG, REMOVE IN PROD
    Mock生成初始计划，全部清空agent/action字段，避免旧路由泄露到step_loop_node
    注意：撰写/简报/报告/方案/搭建/面试类query交由task_planner_node的task_plan_global_llm生成计划，
    此处返回空plan_steps，避免plan_steps覆盖task_plan_global_llm的mock返回值。
    """
    q = raw_query.lower()
    if any(k in q for k in ("撰写", "简报", "报告", "方案", "搭建", "面试", "材料包", "规划", "并行", "对比摘要")):
        return False, []
    if "写" in q or "生成" in q or "创建项目" in q:
        steps = [
            {"step_index": 0, "agent": "", "action": "", "description": f"搜索相关资料：{raw_query}", "depends_on": []},
            {"step_index": 1, "agent": "", "action": "", "description": f"根据资料生成内容：{raw_query}", "depends_on": [0]},
        ]
        return True, steps
    if ("查" in q or "搜索" in q) and ("装" in q or "安装" in q):
        steps = [
            {"step_index": 0, "agent": "", "action": "", "description": f"搜索相关信息：{raw_query}", "depends_on": []},
            {"step_index": 1, "agent": "", "action": "", "description": f"安装所需工具：{raw_query}", "depends_on": [0]},
        ]
        return True, steps
    if ("清理" in q or "优化" in q) and ("监控" in q or "查看" in q or "状态" in q):
        steps = [
            {"step_index": 0, "agent": "", "action": "", "description": "先查看系统状态", "depends_on": []},
            {"step_index": 1, "agent": "", "action": "", "description": "根据状态执行清理", "depends_on": [0]},
        ]
        return True, steps
    return False, []


async def step_loop_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("step_loop_node"):
        plan_steps = state.get("plan_steps", [])
        current_idx = state.get("current_step_index", 0)
        step_results = list(state.get("step_results", []))
        if current_idx >= len(plan_steps):
            return {"route_target": "memory_persist_node"}
        step = plan_steps[current_idx]
        agent = step.get("agent", "clarification_node")
        action = step.get("action", "")
        description = step.get("description", "")
        agent_input: dict[str, Any] = {"action": action, "_step_description": description}
        if current_idx > 0 and step_results:
            prev_result = step_results[-1]
            agent_input["_prev_step_result"] = prev_result
        if agent == "browser_agent_node":
            raw_query = state.get("raw_query", "")
            agent_input["query"] = raw_query
        elif agent == "rag_retrieve_node":
            raw_query = state.get("raw_query", "")
            agent_input["query"] = raw_query
        elif agent == "code_search_node":
            raw_query = state.get("raw_query", "")
            agent_input["query"] = raw_query
        elif agent == "content_gen_agent_node":
            raw_query = state.get("raw_query", "")
            agent_input["task"] = raw_query
            if current_idx > 0 and step_results:
                prev = step_results[-1]
                if isinstance(prev, dict) and "tool_result" in prev:
                    agent_input["_reference"] = str(prev["tool_result"])[:2000]
        elif agent == "store_agent_node":
            raw_query = state.get("raw_query", "")
            agent_input["query"] = raw_query
        inc_counter("step_loop_advance_total")
        return {
            "route_target": agent,
            "agent_input": agent_input,
            "tool_search_query": agent.replace("_agent_node", "").replace("_node", ""),
        }


def route_after_planning(state: AgentState) -> str:
    if state.get("task_plan_enabled", True):
        return "task_planner_node"
    if state.get("is_multi_step", False):
        return "step_loop_node"
    return "guard_pre_check"


def route_after_step_execute(state: AgentState) -> str:
    plan_steps = state.get("plan_steps", [])
    current_idx = state.get("current_step_index", 0)
    if state.get("last_error"):
        return "error_fallback_node"
    if current_idx >= len(plan_steps):
        return "memory_persist_node"
    return "step_loop_node"


async def app_launch_agent_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("app_launch_agent_node"):
        agent_input = dict(state.get("agent_input", {}))
        raw_query = state.get("raw_query", "")
        try:
            action = agent_input.get("action", "")
            if not action:
                q = raw_query.lower()
                if "结束" in q or "杀掉" in q or "关闭" in q or "关掉" in q:
                    action = "kill"
                else:
                    action = "launch"
            if action == "launch":
                tool_name = "app:launch"
                path = agent_input.get("path", "")
                if not path:
                    app_name = agent_input.get("app_name", agent_input.get("name", ""))
                    if app_name:
                        APP_EXE_MAP = {
                            "微信": "WeChat.exe", "记事本": "notepad.exe", "计算器": "calc.exe",
                            "画图": "mspaint.exe", "word": "WINWORD.EXE", "excel": "EXCEL.EXE",
                            "chrome": "chrome.exe", "edge": "msedge.exe", "vscode": "Code.exe",
                            "cursor": "Cursor.exe", "qq": "QQ.exe", "飞书": "Feishu.exe",
                            "钉钉": "DingTalk.exe", "wps": "wps.exe", "notepad": "notepad.exe",
                            "浏览器": "msedge.exe", "ppt": "POWERPNT.EXE", "powerpoint": "POWERPNT.EXE",
                        }
                        path = APP_EXE_MAP.get(app_name.lower(), app_name)
                tool_args = {"path": path}
            elif action == "kill":
                tool_name = "process:kill"
                name = agent_input.get("name", agent_input.get("app_name", ""))
                tool_args = {"name": name}
            else:
                logger.warning(f"app_launch_agent降级: 未知action={action}, 降级为launch")
                tool_name = "app:launch"
                tool_args = {"path": agent_input.get("path", agent_input.get("app_name", ""))}
            return {"tool_name": tool_name, "tool_args": tool_args}
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"app_launch_agent异常:{str(e)}", "error_type": "business"}


async def system_monitor_agent_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("system_monitor_agent_node"):
        return {"last_error": "system_monitor_agent已移除，请使用system_clean_agent_node", "error_type": "business"}


async def system_clean_agent_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("system_clean_agent_node"):
        agent_input = dict(state.get("agent_input", {}))
        try:
            action = agent_input.get("action", "scan")
            max_items = agent_input.get("max_items", 50)
            if action in ("cleanup", "scan_and_cleanup"):
                tool_name = "disk:cleanup"
                tool_args = {"max": max_items}
            else:
                tool_name = "temp:scan"
                tool_args = {"max": max_items}
            return {"tool_name": tool_name, "tool_args": tool_args}
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"system_clean_agent异常:{str(e)}", "error_type": "business"}


async def browser_agent_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("browser_agent_node"):
        agent_input = dict(state.get("agent_input", {}))
        try:
            action = agent_input.get("action", "search")
            if action in ("search", "query", "find", "lookup", "search_web", "web_search", "browse"):
                tool_name = "browser:search"
                tool_args = {"query": agent_input.get("query", "")}
            elif action in ("request", "http", "fetch"):
                tool_name = "network:request"
                tool_args = {"url": agent_input.get("url", ""), "method": agent_input.get("method", "GET")}
            else:
                logger.warning(f"browser_agent降级: 未知action={action}, 降级为search")
                tool_name = "browser:search"
                tool_args = {"query": agent_input.get("query", agent_input.get("task", ""))}
            return {"tool_name": tool_name, "tool_args": tool_args}
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"browser_agent异常:{str(e)}", "error_type": "business"}


async def store_agent_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("store_agent_node"):
        agent_input = dict(state.get("agent_input", {}))
        try:
            action = agent_input.get("action", "list")
            if action == "search":
                tool_name = "store:search"
                tool_args = {"query": agent_input.get("query", "")}
            elif action == "install":
                tool_name = "store:install"
                tool_args = {"package_id": agent_input.get("package_id", "")}
                if agent_input.get("app_name"):
                    tool_args["app_name"] = agent_input["app_name"]
            elif action == "uninstall":
                tool_name = "store:uninstall"
                tool_args = {"package_id": agent_input.get("package_id", "")}
            elif action == "list":
                tool_name = "store:list"
                tool_args = {}
            else:
                logger.warning(f"store_agent降级: 未知action={action}, 降级为search")
                tool_name = "store:search"
                tool_args = {"query": agent_input.get("query", agent_input.get("task", ""))}
            return {"tool_name": tool_name, "tool_args": tool_args}
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"store_agent异常:{str(e)}", "error_type": "business"}


async def content_gen_agent_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("content_gen_agent_node"):
        agent_input = dict(state.get("agent_input", {}))
        try:
            action = agent_input.get("action", "generate")
            if action in ("generate", "generate_and_open", "generate_code", "generate_document", "write", "create", "write_document", "write_paper", "compose", "draft"):
                tool_name = "content:generate"
                tool_args = {
                    "task": agent_input.get("task", ""),
                    "content_type": agent_input.get("content_type", "document"),
                    "auto_open": action == "generate_and_open",
                }
                for key in ("theme", "style", "length", "output_path"):
                    if agent_input.get(key):
                        tool_args[key] = agent_input[key]
            elif action == "ide_create":
                tool_name = "ide:launch"
                tool_args = {
                    "ide": agent_input.get("ide", "vscode"),
                    "action": "create_project",
                    "project_name": agent_input.get("project_name", "untitled"),
                }
            else:
                logger.warning(f"content_gen_agent降级: 未知action={action}, 降级为generate")
                tool_name = "content:generate"
                tool_args = {
                    "task": agent_input.get("task", ""),
                    "content_type": agent_input.get("content_type", "document"),
                    "auto_open": False,
                }
            return {"tool_name": tool_name, "tool_args": tool_args}
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"content_gen_agent异常:{str(e)}", "error_type": "business"}


async def image_agent_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("image_agent_node"):
        agent_input = dict(state.get("agent_input", {}))
        try:
            action = agent_input.get("action", "screenshot")
            if action in ("screenshot", "capture", "截图"):
                tool_name = "image:screenshot"
                tool_args = {
                    "region": agent_input.get("region", ""),
                    "output_path": agent_input.get("output_path", ""),
                }
            elif action in ("ocr", "recognize", "识别", "文字识别"):
                tool_name = "image:ocr"
                tool_args = {
                    "image_path": agent_input.get("image_path", ""),
                    "lang": agent_input.get("lang", "chi_sim+eng"),
                }
            elif action in ("understand", "理解", "语义", "图片理解", "描述图片", "看图"):
                tool_name = "image:understand"
                tool_args = {
                    "image_path": agent_input.get("image_path", ""),
                    "question": agent_input.get("question", agent_input.get("task", "")),
                }
            elif action in ("resize", "缩放", "调整大小"):
                tool_name = "image:resize"
                tool_args = {
                    "image_path": agent_input.get("image_path", ""),
                    "width": agent_input.get("width", 0),
                    "height": agent_input.get("height", 0),
                    "output_path": agent_input.get("output_path", ""),
                }
            elif action in ("crop", "裁剪"):
                tool_name = "image:crop"
                tool_args = {
                    "image_path": agent_input.get("image_path", ""),
                    "box": agent_input.get("box", ""),
                    "output_path": agent_input.get("output_path", ""),
                }
            elif action in ("convert", "转换", "格式转换"):
                tool_name = "image:convert"
                tool_args = {
                    "image_path": agent_input.get("image_path", ""),
                    "target_format": agent_input.get("target_format", "png"),
                    "output_path": agent_input.get("output_path", ""),
                }
            elif action in ("filter", "滤镜", "处理"):
                tool_name = "image:filter"
                tool_args = {
                    "image_path": agent_input.get("image_path", ""),
                    "filter_type": agent_input.get("filter_type", "grayscale"),
                    "output_path": agent_input.get("output_path", ""),
                }
            elif action in ("analyze", "分析", "图像分析"):
                tool_name = "image:analyze"
                tool_args = {
                    "image_path": agent_input.get("image_path", ""),
                    "analyze_type": agent_input.get("analyze_type", "histogram"),
                }
            elif action in ("read_qr", "二维码", "扫码"):
                tool_name = "image:read_qr"
                tool_args = {
                    "image_path": agent_input.get("image_path", ""),
                }
            elif action in ("compare", "对比", "比较"):
                tool_name = "image:compare"
                tool_args = {
                    "image_path_a": agent_input.get("image_path_a", ""),
                    "image_path_b": agent_input.get("image_path_b", ""),
                }
            else:
                logger.warning(f"image_agent降级: 未知action={action}, 降级为screenshot")
                tool_name = "image:screenshot"
                tool_args = {"region": agent_input.get("region", ""), "output_path": agent_input.get("output_path", "")}
            return {"tool_name": tool_name, "tool_args": tool_args}
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"image_agent异常:{str(e)}", "error_type": "business"}


async def algorithm_agent_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("algorithm_agent_node"):
        agent_input = dict(state.get("agent_input", {}))
        try:
            action = agent_input.get("action", "calculate")
            if action in ("calculate", "计算", "求值"):
                tool_name = "algo:calculate"
                tool_args = {
                    "expression": agent_input.get("expression", ""),
                }
            elif action in ("encrypt", "加密"):
                tool_name = "algo:encrypt"
                tool_args = {
                    "text": agent_input.get("text", ""),
                    "method": agent_input.get("method", "aes"),
                    "key": agent_input.get("key", ""),
                }
            elif action in ("decrypt", "解密"):
                tool_name = "algo:decrypt"
                tool_args = {
                    "text": agent_input.get("text", ""),
                    "method": agent_input.get("method", "aes"),
                    "key": agent_input.get("key", ""),
                }
            elif action in ("compress", "压缩"):
                tool_name = "algo:compress"
                tool_args = {
                    "source_path": agent_input.get("source_path", ""),
                    "output_path": agent_input.get("output_path", ""),
                    "format": agent_input.get("format", "zip"),
                }
            elif action in ("decompress", "解压", "解压缩"):
                tool_name = "algo:decompress"
                tool_args = {
                    "archive_path": agent_input.get("archive_path", ""),
                    "output_path": agent_input.get("output_path", ""),
                }
            elif action in ("convert_data", "数据转换", "格式转换"):
                tool_name = "algo:convert_data"
                tool_args = {
                    "input_path": agent_input.get("input_path", ""),
                    "input_format": agent_input.get("input_format", ""),
                    "output_format": agent_input.get("output_format", ""),
                    "output_path": agent_input.get("output_path", ""),
                }
            elif action in ("generate", "生成", "随机"):
                tool_name = "algo:generate"
                tool_args = {
                    "gen_type": agent_input.get("gen_type", "uuid"),
                    "count": agent_input.get("count", 1),
                }
            elif action in ("hash", "哈希", "摘要"):
                tool_name = "algo:hash"
                tool_args = {
                    "text": agent_input.get("text", ""),
                    "algorithm": agent_input.get("algorithm", "sha256"),
                }
            elif action in ("plot", "画图", "可视化", "绘图", "visualize", "chart", "graph"):
                tool_name = "algo:plot"
                tool_args = {
                    "data_path": agent_input.get("data_path", ""),
                    "chart_type": agent_input.get("chart_type", "bar"),
                    "title": agent_input.get("title", ""),
                    "output_path": agent_input.get("output_path", ""),
                }
            else:
                logger.warning(f"algorithm_agent降级: 未知action={action}, 降级为calculate")
                tool_name = "algo:calculate"
                tool_args = {"expression": agent_input.get("expression", agent_input.get("task", ""))}
            return {"tool_name": tool_name, "tool_args": tool_args}
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"algorithm_agent异常:{str(e)}", "error_type": "business"}


AGENT_NODE_MAP = {
    "app_launch_agent_node": "app_launch_agent_node",
    "system_clean_agent_node": "system_clean_agent_node",
    "browser_agent_node": "browser_agent_node",
    "store_agent_node": "store_agent_node",
    "content_gen_agent_node": "content_gen_agent_node",
    "image_agent_node": "image_agent_node",
    "algorithm_agent_node": "algorithm_agent_node",
    "rag_retrieve_node": "rag_retrieve_node",
    "code_search_node": "code_search_node",
}


async def agent_dispatch_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("agent_dispatch_node"):
        route_target = state.get("route_target", "")
        if route_target in AGENT_NODE_MAP:
            return {"route_target": route_target}
        intent = state.get("intent", "")
        q = state.get("raw_query", "").lower()
        if any(k in q for k in ("搜代码", "找代码", "code search", "代码搜索")):
            return {"route_target": "code_search_node"}
        if any(k in q for k in ("查文档", "检索", "知识库", "rag")):
            return {"route_target": "rag_retrieve_node"}
        if any(k in q for k in ("写", "生成", "创建", "论文", "文档")):
            return {"route_target": "content_gen_agent_node"}
        if any(k in q for k in ("搜索", "查", "资料")):
            return {"route_target": "browser_agent_node"}
        logger.warning(f"agent_dispatch: 未知route_target={route_target}，降级到content_gen")
        return {"route_target": "content_gen_agent_node"}


def route_after_dispatch(state: AgentState) -> str:
    return state.get("route_target", "app_launch_agent_node")


async def tool_execute_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("tool_execute_node"):
        traced_execution = _get_traced_execution()

        tool_name = state.get("tool_name", "")
        tool_args = state.get("tool_args", {})
        args_hash = hashlib.sha256(str(tool_args).encode()).hexdigest()[:16]
        try:
            with traced_execution("execute_tool", {"gen_ai.tool.name": tool_name, "gen_ai.tool.args_hash": args_hash}) as span:
                from app.services.tools.executor import _execute_single_tool
                result = await _execute_single_tool(tool_name, tool_args)
                span.set_attribute("gen_ai.tool.ok", str(result.get("ok")))
            updates = {"tool_result": result}
            if not result.get("ok"):
                updates["last_error"] = result.get("error", "unknown error")
            return updates
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"tool_execute异常:{str(e)}", "error_type": "business"}


async def step_collect_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("step_collect_node"):
        is_multi = state.get("is_multi_step", False)
        if not is_multi:
            return {}
        current_idx = state.get("current_step_index", 0)
        step_results = list(state.get("step_results", []))
        tool_result = state.get("tool_result", {})
        tool_name = state.get("tool_name", "")
        step_results.append({
            "step_index": current_idx,
            "tool_name": tool_name,
            "tool_result": tool_result,
        })
        next_idx = current_idx + 1
        return {"step_results": step_results, "current_step_index": next_idx}


def route_after_tool_exec_or_step(state: AgentState) -> str:
    is_multi = state.get("is_multi_step", False)
    if is_multi:
        task_plan_status = state.get("task_plan_status", "")
        if task_plan_status in ("executing", "planning", "blocked"):
            return "task_plan_collect_node"
        return "step_collect_node"
    err = state.get("last_error")
    auto_diag = state.get("enable_auto_diagnose", False)
    if err and auto_diag:
        return "supervisor_diagnose_node"
    return "post_validate_gate"


async def post_validate_gate_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("post_validate_gate_node"):
        from app.services.graph.checkers import post_validate_gate
        try:
            return post_validate_gate(state)
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"validate_gate异常:{str(e)}", "error_type": "business"}


async def error_fallback_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("error_fallback_node"):
        inc_counter("fallback_triggered_total")
        err = state.get("last_error", "未知错误")
        return {"tool_result": {
            "status": "error",
            "summary": f"任务降级: {err}",
            "data": {"ok": False, "error": err, "fallback": True},
            "meta": {"hit_count": 0, "missing_info": [], "confidence": 0.0},
            "error": {"type": state.get("error_type", "execution"), "suggestion": "任务执行失败，已降级处理"},
            "fallback": True,
        }}


async def memory_persist_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("memory_persist_node"):
        from app.services.graph.memory_store import (
            EVIDENCE_LEVEL_A,
            EVIDENCE_LEVEL_B,
            EVIDENCE_LEVEL_C,
            EVIDENCE_LEVEL_D,
            get_memory_store,
        )

        store = get_memory_store()
        raw_query = state.get("raw_query", "")
        standalone_query = state.get("standalone_query", "")
        retrieval_queries = state.get("retrieval_queries", [])
        trace_id = state.get("trace_id", "")
        tool_name = state.get("tool_name", "")
        tool_args = state.get("tool_args", {})
        tool_result = state.get("tool_result", {})
        user_id = state.get("user_id") or state.get("session_id", "default")

        try:
            store.put_evidence_a(user_id, raw_query, tool_result, trace_id)
            args_hash = hashlib.sha256(str(tool_args).encode()).hexdigest()[:16]
            store.put_evidence_b(user_id, tool_name, args_hash, tool_result, trace_id)

            ts = int(time.time() * 1000)
            store.put(
                user_id,
                key=f"user_utterance_C_{ts}",
                value={"raw_query": raw_query, "trace_id": trace_id},
                level=EVIDENCE_LEVEL_C,
                owner="user",
            )

            model_inference = {
                k: state.get(k)
                for k in ("intent", "intent_confidence", "standalone_query",
                          "retrieval_queries", "route_target", "route_confidence")
                if state.get(k) not in (None, "", [])
            }
            if model_inference:
                store.put(
                    user_id,
                    key=f"model_inference_D_{ts}",
                    value=model_inference,
                    level=EVIDENCE_LEVEL_D,
                    owner="llm",
                )

            # M15/H13 执行闭环：把独立验证结果(completion_evidence/task_verified)作为
            # C级"系统实证"证据落盘，后续任务可读取，避免世界模型只存"以为的结果"。
            completion_evidence = state.get("completion_evidence", {}) or {}
            task_verified = bool(state.get("task_verified", False))
            if completion_evidence:
                store.put(
                    user_id,
                    key=f"task_verification_C_{ts}",
                    value={
                        "tool_name": tool_name,
                        "task_verified": task_verified,
                        "evidence_level": completion_evidence.get("evidence_level", ""),
                        "source": completion_evidence.get("source", ""),
                        "checks": completion_evidence.get("checks", {}),
                        "trace_id": trace_id,
                    },
                    level=EVIDENCE_LEVEL_C,
                    owner="system",
                )
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"memory_persist异常:{str(e)}", "error_type": "business"}

        evidence = {
            "raw_query": raw_query,
            "standalone_query": standalone_query,
            "retrieval_queries": retrieval_queries,
            "intent": state.get("intent"),
            "tool_name": tool_name,
            "tool_result_ok": tool_result.get("ok", False),
            "task_verified": bool(state.get("task_verified", False)),
            "completion_evidence": state.get("completion_evidence", {}) or {},
            "timestamp": time.time(),
        }

        return {"evidence": evidence}


async def tool_search_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("tool_search_node"):
        from app.services.graph.tool_search import tool_search_instance

        q = state.get("tool_search_query", "")
        retrieval_queries = state.get("retrieval_queries", [])
        search_terms = [q] if q and q.strip() else []
        for rq in retrieval_queries:
            if rq and rq.strip() and rq not in search_terms:
                search_terms.append(rq)

        if not search_terms:
            return {"tool_search_hit_list": [], "tool_loaded_schema": tool_search_instance.get_current_loaded_schema()}

        seen_names: set[str] = set()
        hit_names: list[str] = []
        for term in search_terms:
            hits = tool_search_instance.search_tool(term, top_k=3)
            for h in hits:
                if h.name not in seen_names:
                    seen_names.add(h.name)
                    hit_names.append(h.name)
                    tool_search_instance.load_tool_schema(h.name)

        loaded_schema = tool_search_instance.get_current_loaded_schema()
        inc_counter("tool_search_invoked_total")
        if len(hit_names) == 0:
            inc_counter("tool_search_zero_hit_total")

        return {"tool_search_hit_list": hit_names, "tool_loaded_schema": loaded_schema, "tool_search_query": ""}


async def governor_scan_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("governor_scan_node"):
        from app.services.graph.memory_store import get_governing_store, SIGNAL_STATUS_OPEN, SIGNAL_STATUS_PROCESSING, SIGNAL_STATUS_RESOLVED

        mem_store = get_governing_store()
        trigger = state.get("governor_trigger", "")
        user_id = state.get("session_id", "default")
        scan_res = None
        try:
            open_signals = mem_store.get_open_signals(user_id)
            if open_signals:
                logger.info(f"Governor: 发现 {len(open_signals)} 个待处理校正信号")
                for sig in open_signals[:3]:
                    sig_id = sig.get("signal_id", "")
                    mem_store.update_signal_status(sig_id, SIGNAL_STATUS_PROCESSING, owner="governor", comment="自动认领处理")
                    sig_type = sig.get("signal_type", "")
                    if sig_type == "pollution":
                        related = sig.get("related_keys", [])
                        for rk in related:
                            mem_store.delete(user_id, rk)
                        mem_store.update_signal_status(sig_id, SIGNAL_STATUS_RESOLVED, owner="governor", comment="污染记忆已清除")
                        logger.info(f"Governor: 处理污染信号 {sig_id}, 清除 {len(related)} 条记忆")
                    elif sig_type == "conflict":
                        mem_store.update_signal_status(sig_id, SIGNAL_STATUS_RESOLVED, owner="governor", comment="冲突信号已标记")
                        logger.info(f"Governor: 处理冲突信号 {sig_id}")
                    else:
                        mem_store.update_signal_status(sig_id, SIGNAL_STATUS_RESOLVED, owner="governor", comment="未知信号类型，直接关闭")

            if trigger == "full":
                scan_res = mem_store.full_scan(user_id=user_id)
                inc_counter("governor_full_scan_total")
            elif trigger == "light":
                scan_res = mem_store.put_memory(user_id, "governor_light_scan", {"trigger": "light"}, evidence_level="C", source="governor_light_scan")
                inc_counter("governor_light_scan_total")
            if scan_res and (len(scan_res.get("conflict", [])) > 0 or len(scan_res.get("expired", [])) > 0):
                inc_counter("governor_signal_generated_total")
                inc_counter("signal_status_open_total")
            return {"governor_scan_result": scan_res or {}, "governor_trigger": ""}
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"governor_scan异常:{str(e)}", "error_type": "business"}


async def supervisor_diagnose_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("supervisor_diagnose_node"):
        from app.services.graph.memory_store import get_governing_store

        mem_store = get_governing_store()
        trace_id = state.get("diagnose_trace_id", "")
        user_id = state.get("session_id", "default")
        enable_auto = state.get("enable_auto_diagnose", False)
        last_error = state.get("last_error", "")
        sig_id = ""
        try:
            if enable_auto and trace_id and last_error:
                elow = last_error.lower()
                if any(k in elow for k in ("intent", "route", "confidence")):
                    sig_id = mem_store.generate_correction_signal(user_id, "pollution", [], f"Supervisor诊断 trace_id={trace_id},err={last_error}")
                    inc_counter("supervisor_diagnose_signal_total")
            return {"correction_signal_id": sig_id, "correction_signal_status": "open" if sig_id else "", "diagnose_trigger": False}
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"supervisor_diagnose异常:{str(e)}", "error_type": "business"}


async def rewrite_agent_input_node(state: AgentState) -> dict[str, Any]:
    """
    自校正循环节点：拿到上一轮error信息，让LLM重写agent_input
    埋点：触发、成功、超时；失败自动生成pollution类型correction_signal
    """
    with NodeMetrics("rewrite_agent_input_node"):
        import asyncio as _asyncio

        from app.services.graph.memory_store import get_governing_store

        mem_store = get_governing_store()
        traced_execution = _get_traced_execution()
        raw_query = state.get("raw_query", "")
        old_agent_input = state.get("agent_input", {})
        last_err = state.get("last_error", "")
        user_id = state.get("user_id") or state.get("session_id", "default")
        loop_cnt = state.get("correction_loop_count", 0)
        new_loop = loop_cnt + 1

        correction_start = state.get("correction_start_time", 0)
        if correction_start == 0:
            correction_start = time.time()
        correction_timeout_s = float(os.getenv("CORRECTION_LOOP_TIMEOUT_S", "30"))
        if time.time() - correction_start > correction_timeout_s:
            NodeMetrics.count_correction_timeout()
            return {
                "correction_loop_count": new_loop,
                "correction_reason": f"correction loop total timeout ({correction_timeout_s}s)",
                "last_error": f"自校正超时({correction_timeout_s}s)，停止循环",
                "error_type": "business",
            }

        NodeMetrics.count_correction_trigger()

        import yaml
        cfg_path = os.getenv("SECURITY_CONFIG_PATH", "config/security.yaml")
        rewrite_timeout = 10.0
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    sec_cfg = yaml.safe_load(f)
                    rewrite_timeout = float(sec_cfg.get("llm_rewrite_timeout", 10.0))
            except Exception:
                pass

        try:
            with traced_execution("chat", {"gen_ai.node": "rewrite_agent_input"}):
                if LLM_MODE == "real":
                    from app.services.llm.client import rewrite_agent_input_llm
                    new_agent_input = await rewrite_agent_input_llm(
                        raw_query, old_agent_input, last_err,
                        rewrite_timeout=rewrite_timeout,
                    )
                else:
                    new_agent_input = old_agent_input

            NodeMetrics.count_correction_success()
            return {
                "agent_input": new_agent_input,
                "correction_loop_count": new_loop,
                "correction_reason": last_err,
                "correction_start_time": correction_start,
                "last_error": None,
                "error_type": "",
            }

        except _asyncio.TimeoutError:
            NodeMetrics.count_correction_timeout()
            sig_id = mem_store.generate_correction_signal(
                user_id=user_id,
                signal_type="pollution",
                related_keys=[],
                detail=f"自校正LLM重写超时，loop={loop_cnt}, raw_query={raw_query}, error={last_err}",
            )
            return {
                "correction_loop_count": new_loop,
                "correction_reason": f"rewrite timeout: {last_err}",
                "correction_signal_id": sig_id,
                "correction_signal_status": "open",
                "last_error": "rewrite_agent_input: llm rewrite timeout",
                "error_type": "business",
            }

        except Exception as e:
            logger.exception(f"rewrite_agent_input_node exception {e}")
            sig_id = mem_store.generate_correction_signal(
                user_id=user_id,
                signal_type="pollution",
                related_keys=[],
                detail=f"自校正重写异常，loop={loop_cnt}, raw_query={raw_query}, exc={str(e)}",
            )
            return {
                "correction_loop_count": new_loop,
                "correction_reason": last_err,
                "correction_signal_id": sig_id,
                "correction_signal_status": "open",
                "last_error": f"rewrite_agent_input异常:{str(e)}",
                "error_type": "business",
            }


def _render_task_plan_md(items: list[dict[str, Any]]) -> str:
    lines = ["## 📋 任务规划清单"]
    for item in items:
        idx = item.get("step_index", 0)
        status = item.get("status", "pending")
        priority = item.get("priority", "P1")
        desc = item.get("description", "")
        depends = item.get("depends_on", [])
        deliverable = item.get("deliverable", "")
        dep_str = str(depends) if depends else "无"
        if status == "done":
            mark = "[x]"
        elif status == "blocked":
            mark = "[-]"
        else:
            mark = "[ ]"
        line = f"- {mark} ({priority}) 任务{idx}: {desc} | 依赖：{dep_str} | 交付物：{deliverable}"
        if status == "blocked" and item.get("blocked_reason"):
            line += f" 【阻塞：{item['blocked_reason']}】"
        lines.append(line)
    return "\n".join(lines)


def _find_next_executable(items: list[dict[str, Any]]) -> int | None:
    done_indices = {it["step_index"] for it in items if it.get("status") == "done"}
    pending = [it for it in items if it.get("status") == "pending"]
    if not pending:
        return None
    pending.sort(key=lambda x: (0 if x.get("priority") == "P0" else 1 if x.get("priority") == "P1" else 2, x.get("step_index", 0)))
    for it in pending:
        deps = it.get("depends_on", [])
        if all(d in done_indices for d in deps):
            return it["step_index"]
    return None


async def task_planner_node(state: AgentState) -> dict[str, Any]:
    """
    Task-Planner 规划-分步执行-迭代交付节点（LLM驱动版）
    - 首次进入: 调用LLM生成全局总计划(task_plan_global_llm)
    - 后续进入: 找到第一个pending任务 → 调用LLM生成本轮子计划(task_plan_sub_plan_llm)
               → 调用LLM执行子计划产出内容(task_execute_llm) → 标记完成
    - 全部完成: 标记completed, 汇总交付物
    """
    with NodeMetrics("task_planner_node"):
        state["route_target"] = ""
        plan_enabled = state.get("task_plan_enabled", True)
        if not plan_enabled:
            return {"route_target": ""}

        items = validate_task_plan_items(list(state.get("task_plan_items", [])))
        plan_status = state.get("task_plan_status", "")
        plan_steps = state.get("plan_steps", [])
        history_log = list(state.get("history_log", []))
        raw_query = state.get("raw_query", "")

        # ========== 首次进入：生成全局总计划 ==========
        if not items and plan_steps:
            items = []
            for step in plan_steps:
                items.append({
                    "step_index": step.get("step_index", 0),
                    "agent": "",
                    "action": "",
                    "description": step.get("description", ""),
                    "depends_on": step.get("depends_on", []),
                    "priority": step.get("priority", "P1"),
                    "deliverable": step.get("deliverable", ""),
                    "status": "pending",
                    "retry_count": 0,
                })
            items = validate_task_plan_items(items)
            md = _render_task_plan_md(items)
            logger.info(f"Task-Planner: 从plan_steps生成规划清单\n{md}")
            inc_counter("task_plan_created_total")
            history_log.append("plan_global: 从plan_steps创建全局任务计划")
            return {
                "task_plan_items": items,
                "task_plan_status": "planning",
                "task_plan_current_idx": 0,
                "task_plan_results": [],
                "history_log": history_log,
                "memory_summary": md,
                "route_target": "",
            }

        if not items and not plan_steps:
            try:
                from app.services.llm.client import task_plan_global_llm
                global_items = await asyncio.wait_for(
                    task_plan_global_llm(raw_query),
                    timeout=TASK_STEP_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                logger.warning(f"task_plan_global_llm超时({TASK_STEP_TIMEOUT_S}s), 降级到单步执行")
                global_items = []
            except Exception as e:
                logger.warning(f"task_plan_global_llm失败, 降级到plan_steps: {e}")
                global_items = []
            if global_items:
                items = []
                for idx, gi in enumerate(global_items):
                    items.append({
                        "step_index": gi.get("step_index", idx + 1),
                        "agent": "",
                        "action": "",
                        "description": gi.get("description", ""),
                        "depends_on": [],
                        "priority": "P1",
                        "deliverable": gi.get("expected_output", ""),
                        "expected_output": gi.get("expected_output", ""),
                        "status": "pending",
                        "retry_count": 0,
                    })
                items = validate_task_plan_items(items)
                md = _render_task_plan_md(items)
                logger.info(f"Task-Planner: LLM生成全局计划\n{md}")
                inc_counter("task_plan_created_total")
                history_log.append("plan_global: LLM创建全局任务计划")
                return {
                    "task_plan_items": items,
                    "task_plan_status": "planning",
                    "task_plan_current_idx": 0,
                    "task_plan_results": [],
                    "history_log": history_log,
                    "memory_summary": md,
                    "route_target": "",
                }
            logger.warning("Task-Planner: 全局计划生成失败, 降级到单步执行")
            return {
                "task_plan_status": "completed",
                "all_finished": True,
                "route_target": "",
            }

        if plan_status == "completed":
            return {"route_target": ""}

        # ========== 找到第一个pending任务 ==========
        pending_items = [it for it in items if it.get("status") == "pending"]
        if not pending_items:
            all_done = all(it.get("status") in ("done", "completed", "failed") for it in items)
            if all_done:
                results = list(state.get("task_plan_results", []))
                md = _render_task_plan_md(items)
                summary = f"✅ 全部任务执行完毕\n\n{md}\n\n交付物汇总：\n"
                for it in items:
                    if it.get("deliverable") or it.get("expected_output"):
                        summary += f"  - 任务{it['step_index']}: {it.get('deliverable') or it.get('expected_output')}\n"
                failed_items = [it for it in items if it.get("status") == "failed"]
                if failed_items:
                    summary += f"\n⚠️ 失败任务：\n"
                    for it in failed_items:
                        summary += f"  - 任务{it['step_index']}: {it.get('blocked_reason', 'unknown')}\n"
                logger.info(summary)
                inc_counter("task_plan_completed_total")
                history_log.append("plan_global: 全部任务完成")
                return {
                    "task_plan_status": "completed",
                    "all_finished": True,
                    "history_log": history_log,
                    "memory_summary": summary,
                    "route_target": "",
                }
            blocked_items = [it for it in items if it.get("status") == "blocked"]
            if blocked_items:
                md = _render_task_plan_md(items)
                return {
                    "task_plan_items": items,
                    "task_plan_status": "blocked",
                    "history_log": history_log,
                    "memory_summary": md,
                    "route_target": "",
                }
            return {"task_plan_status": "completed", "all_finished": True, "route_target": ""}

        target_item = pending_items[0]
        next_idx = target_item["step_index"]
        description = target_item.get("description", "")
        expected_output = target_item.get("expected_output", target_item.get("deliverable", ""))
        step_retry = target_item.get("retry_count", 0)

             # ========== 生成本轮子执行计划（带重试熔断） ==========
        sub_plan = {"target": description, "steps": []}
        sub_plan_ok = False
        for attempt in range(TASK_STEP_MAX_RETRY + 1):
            try:
                from app.services.llm.client import task_plan_sub_plan_llm
                sub_plan = await asyncio.wait_for(
                    task_plan_sub_plan_llm(
                        {"step_index": next_idx, "description": description, "expected_output": expected_output},
                        history_log,
                    ),
                    timeout=TASK_STEP_TIMEOUT_S,
                )
                sub_plan_ok = True
                break
            except asyncio.TimeoutError:
                logger.warning(f"task_plan_sub_plan_llm超时 attempt={attempt+1}/{TASK_STEP_MAX_RETRY+1} step={next_idx}")
                inc_counter("task_plan_step_timeout_total")
            except Exception as e:
                logger.warning(f"task_plan_sub_plan_llm失败 attempt={attempt+1}/{TASK_STEP_MAX_RETRY+1} step={next_idx}: {e}")
            if attempt < TASK_STEP_MAX_RETRY:
                await asyncio.sleep(2 * (attempt + 1) + random.uniform(0, 1))
        if not sub_plan_ok:
            sub_plan = {"target": description, "steps": []}
            logger.warning(f"Task-Planner: 子计划生成全部重试失败 step={next_idx}, 降级为空子计划继续执行")
        history_log.append(f"plan_step: 生成子计划，目标={sub_plan.get('target', description)}")
        # ========== 执行子计划（带重试熔断） ==========
        results = list(state.get("task_plan_results", []))
        agent_result = ""
        exec_ok = False
        for attempt in range(TASK_STEP_MAX_RETRY + 1):
            try:
                from app.services.llm.client import task_execute_llm
                agent_result = await asyncio.wait_for(
                    task_execute_llm(description, sub_plan, expected_output, results),
                    timeout=TASK_STEP_TIMEOUT_S,
                )
                if len(agent_result) >= TASK_MIN_OUTPUT_LEN:
                    exec_ok = True
                    break
                logger.warning(f"task_execute_llm产出过短({len(agent_result)}<{TASK_MIN_OUTPUT_LEN}), attempt={attempt+1}")
            except asyncio.TimeoutError:
                logger.warning(f"task_execute_llm超时 attempt={attempt+1}/{TASK_STEP_MAX_RETRY+1} step={next_idx}")
                inc_counter("task_plan_step_timeout_total")
            except Exception as e:
                logger.warning(f"task_execute_llm失败 attempt={attempt+1}/{TASK_STEP_MAX_RETRY+1} step={next_idx}: {e}")
            if attempt < TASK_STEP_MAX_RETRY:
                await asyncio.sleep(2 * (attempt + 1) + random.uniform(0, 1))
        # ========== 更新任务状态：成功/失败熔断 ==========
        for it in items:
            if it["step_index"] == next_idx:
                if exec_ok:
                    it["status"] = "completed"
                    it["retry_count"] = 0
                else:
                    it["retry_count"] = step_retry + 1
                    if it["retry_count"] > TASK_STEP_MAX_RETRY:
                        it["status"] = "failed"
                        it["blocked_reason"] = f"执行重试{it['retry_count']}次仍失败, 熔断跳过"
                        logger.warning(f"Task-Planner: 任务{next_idx}熔断跳过, retry_count={it['retry_count']}")
                        inc_counter("task_plan_step_max_retry_total")
                    else:
                        it["status"] = "pending"
                        logger.warning(f"Task-Planner: 任务{next_idx}执行失败, retry_count={it['retry_count']}, 下轮重试")
                break

        results.append({
            "step_index": next_idx,
            "tool_name": "llm:execute",
            "tool_result": {"ok": exec_ok, "content_length": len(agent_result), "data": agent_result[:500] if exec_ok else ""},
        })

        history_log.append(f"execute_step: {'成功' if exec_ok else '失败'} 产出长度{len(agent_result)}")

        # ========== 工具调用触发：根据任务描述/预期输出判断是否需要调用工具 ==========
        tool_call_result = None
        if exec_ok:
            desc_lower = description.lower()
            output_lower = expected_output.lower()
            need_file_gen = any(k in desc_lower or k in output_lower for k in (
                "生成文档", "生成文件", "word", "ppt", "html", "文档", "材料包", "面试材料",
                "简历", "架构图", "mermaid", "流程图",
            ))
            need_plot = any(k in desc_lower or k in output_lower for k in (
                "绘图", "画图", "可视化", "图表", "柱状图", "折线图", "饼图", "chart", "plot",
            ))
            need_image = any(k in desc_lower or k in output_lower for k in (
                "截图", "截屏", "screenshot",
            ))
            if need_file_gen:
                tool_name_triggered = "content:generate"
                content_type = "word" if "word" in output_lower else "ppt" if "ppt" in output_lower else "html" if "html" in output_lower else "document"
                tool_args_triggered = {"task": description, "content_type": content_type}
                tool_call_result = {"tool_name": tool_name_triggered, "tool_args": tool_args_triggered}
                history_log.append(f"tool_trigger: 任务{next_idx}触发content:generate, content_type={content_type}")
            elif need_plot:
                tool_name_triggered = "algo:plot"
                chart_type = "bar"
                if "折线" in desc_lower or "折线" in output_lower or "line" in desc_lower:
                    chart_type = "line"
                elif "饼" in desc_lower or "饼" in output_lower or "pie" in desc_lower:
                    chart_type = "pie"
                tool_args_triggered = {"chart_type": chart_type, "title": description[:100]}
                tool_call_result = {"tool_name": tool_name_triggered, "tool_args": tool_args_triggered}
                history_log.append(f"tool_trigger: 任务{next_idx}触发algo:plot, chart_type={chart_type}")
            elif need_image:
                tool_name_triggered = "image:screenshot"
                tool_args_triggered = {"region": "", "output_path": ""}
                tool_call_result = {"tool_name": tool_name_triggered, "tool_args": tool_args_triggered}
                history_log.append(f"tool_trigger: 任务{next_idx}触发image:screenshot")

        if tool_call_result and exec_ok:
            try:
                from app.services.tools.executor import _execute_single_tool
                _tr = await _execute_single_tool(
                    tool_call_result["tool_name"], tool_call_result["tool_args"]
                )
                tool_call_result["tool_result"] = _tr
                history_log.append(f"tool_exec: {tool_call_result['tool_name']} ok={_tr.get('ok')}")
            except Exception as _te:
                tool_call_result["tool_result"] = {"ok": False, "error": str(_te)}
                history_log.append(f"tool_exec: {tool_call_result['tool_name']} error={str(_te)[:200]}")

        remaining = [it for it in items if it.get("status") == "pending"]
        all_done = len(remaining) == 0

        md = _render_task_plan_md(items)
        if all_done:
            summary = f"✅ 全部任务执行完毕\n\n{md}\n\n交付物汇总：\n"
            for it in items:
                if it.get("deliverable") or it.get("expected_output"):
                    summary += f"  - 任务{it['step_index']}: {it.get('deliverable') or it.get('expected_output')}\n"
            failed_items = [it for it in items if it.get("status") == "failed"]
            if failed_items:
                summary += f"\n⚠️ 失败任务：\n"
                for it in failed_items:
                    summary += f"  - 任务{it['step_index']}: {it.get('blocked_reason', 'unknown')}\n"
            logger.info(summary)
            inc_counter("task_plan_completed_total")
            history_log.append("plan_global: 全部任务完成")
            return {
                "task_plan_items": items,
                "task_plan_current_idx": next_idx,
                "task_plan_results": results,
                "task_plan_status": "completed",
                "all_finished": True,
                "agent_result": agent_result,
                "current_sub_plan": sub_plan,
                "history_log": history_log,
                "memory_summary": summary,
                "tool_name": tool_call_result["tool_name"] if tool_call_result else "",
                "tool_args": tool_call_result["tool_args"] if tool_call_result else {},
                "tool_result": tool_call_result.get("tool_result", {}) if tool_call_result else {},
                "route_target": "",
            }

        logger.info(f"🔁 Task-Planner: 任务{next_idx}{'完成' if exec_ok else '失败'}, 还有{len(remaining)}项待执行\n{md}")
        inc_counter("task_plan_step_exec_total")
        return {
            "task_plan_items": items,
            "task_plan_current_idx": next_idx,
            "task_plan_results": results,
            "task_plan_status": "executing",
            "agent_result": agent_result,
            "current_sub_plan": sub_plan,
            "history_log": history_log,
            "memory_summary": md,
            "tool_name": tool_call_result["tool_name"] if tool_call_result else "",
            "tool_args": tool_call_result["tool_args"] if tool_call_result else {},
            "tool_result": tool_call_result.get("tool_result", {}) if tool_call_result else {},
            "route_target": "",
        }


async def task_plan_collect_node(state: AgentState) -> dict[str, Any]:
    """
    Task-Planner 步骤收集: 执行完一步后校验交付物有效性, 标记done/blocked, 回到task_planner_node继续
    校验规则:
      1. tool_result.ok=False → blocked
      2. tool_result.degraded=True → blocked(降级检测)
      3. 交付物有效性: content_length<200 → blocked(疑似占位输出)
      4. 前置依赖交付物无效 → 后续任务blocked
    """
    with NodeMetrics("task_plan_collect_node"):
        items = list(state.get("task_plan_items", []))
        current_idx = state.get("task_plan_current_idx", 0)
        results = list(state.get("task_plan_results", []))
        tool_result = state.get("tool_result", {})
        tool_name = state.get("tool_name", "")

        results.append({
            "step_index": current_idx,
            "tool_name": tool_name,
            "tool_result": tool_result,
        })

        for it in items:
            if it["step_index"] == current_idx:
                if it.get("status") == "failed":
                    logger.info(f"Task-Planner: 任务{current_idx}已是failed状态, 跳过collect处理")
                    break
                is_ok = tool_result.get("ok", False)
                is_degraded = tool_result.get("degraded", False)
                degradation_type = tool_result.get("degradation_type", "")
                content_length = tool_result.get("content_length", 0)
                warning = tool_result.get("warning", "")

                if not is_ok:
                    err = tool_result.get("error", "unknown")
                    it["retry_count"] = it.get("retry_count", 0) + 1
                    if it["retry_count"] > TASK_STEP_MAX_RETRY:
                        it["status"] = "failed"
                        it["blocked_reason"] = f"执行失败(重试{it['retry_count']}次): {err}"
                        logger.warning(f"Task-Planner: 任务{current_idx}重试耗尽, 标记failed, retry_count={it['retry_count']}")
                    else:
                        it["status"] = "blocked"
                        it["blocked_reason"] = f"执行失败: {err}"
                        logger.warning(f"Task-Planner: 任务{current_idx}执行失败: {err}, retry_count={it['retry_count']}")
                    remedy_count = sum(1 for x in items if "解决任务" in x.get("description", "") or "修复任务" in x.get("description", ""))
                    if remedy_count < MAX_REMEDY_STEPS:
                        new_idx = max(x["step_index"] for x in items) + 1 if items else 0
                        items.append({
                            "step_index": new_idx,
                            "agent": "clarification_node",
                            "action": "clarify",
                            "description": f"解决任务{current_idx}执行失败: {err}",
                            "depends_on": [],
                            "priority": "P0",
                            "deliverable": f"修复任务{current_idx}",
                            "status": "pending",
                        })
                    else:
                        logger.warning(f"Task-Planner: 补救步骤已达上限({MAX_REMEDY_STEPS}), 不再追加, 任务{current_idx}标记failed")
                        it["status"] = "failed"
                        it["blocked_reason"] = f"执行失败且补救上限耗尽: {err}"
                    inc_counter("task_plan_blocked_total")
                elif is_degraded:
                    it["status"] = "blocked"
                    it["blocked_reason"] = f"工具降级: {degradation_type or warning or 'unknown degradation'}"
                    logger.warning(f"Task-Planner: 任务{current_idx}工具降级阻塞: {degradation_type}")
                    remedy_count = sum(1 for x in items if "解决任务" in x.get("description", "") or "修复任务" in x.get("description", ""))
                    if remedy_count < MAX_REMEDY_STEPS:
                        new_idx = max(x["step_index"] for x in items) + 1 if items else 0
                        items.append({
                            "step_index": new_idx,
                            "agent": "clarification_node",
                            "action": "clarify",
                            "description": f"修复任务{current_idx}工具降级: {degradation_type}",
                            "depends_on": [],
                            "priority": "P0",
                            "deliverable": f"解除任务{current_idx}降级({degradation_type})",
                            "status": "pending",
                        })
                    else:
                        logger.warning(f"Task-Planner: 补救步骤已达上限({MAX_REMEDY_STEPS}), 不再追加降级补救")
                        it["status"] = "failed"
                        it["blocked_reason"] = f"工具降级且补救上限耗尽: {degradation_type}"
                    inc_counter("task_plan_degraded_total")
                elif content_length > 0 and content_length < 200:
                    it["status"] = "blocked"
                    it["blocked_reason"] = f"交付物过短({content_length}chars), 疑似占位输出"
                    logger.warning(f"Task-Planner: 任务{current_idx}交付物过短({content_length}chars), 标记阻塞")
                    inc_counter("task_plan_deliverable_invalid_total")
                else:
                    it["status"] = "done"
                    if content_length > 0:
                        it["deliverable_size"] = content_length
                break

        # ========== 动态重新规划：根据工具返回结果调整后续任务 ==========
        dynamic_added = []
        if tool_result.get("ok", False):
            tool_output_data = tool_result.get("data", "")
            tool_output_path = tool_result.get("output_path", "")
            remaining_after = [it for it in items if it.get("status") == "pending"]
            has_embed_step = any("嵌入" in it.get("description", "") or "插入图表" in it.get("description", "") for it in remaining_after)
            has_text_fallback = any("文字版" in it.get("description", "") or "降级" in it.get("description", "") for it in remaining_after)

            if tool_name == "algo:plot" and tool_output_path and not has_embed_step:
                new_idx = max(x["step_index"] for x in items) + 1 if items else 0
                embed_step = {
                    "step_index": new_idx,
                    "description": f"将图表({tool_output_path})嵌入到项目简报文档中",
                    "depends_on": [current_idx],
                    "priority": "P1",
                    "deliverable": "含图表的简报文档",
                    "expected_output": "HTML简报文档(含嵌入图表)",
                    "status": "pending",
                    "retry_count": 0,
                }
                items.append(embed_step)
                dynamic_added.append(embed_step)
                logger.info(f"Task-Planner: 动态重新规划 - 绘图成功, 新增步骤{new_idx}: 嵌入图表到文档")

            if tool_name == "rag_retrieve_node" and tool_output_data:
                output_lower = str(tool_output_data).lower()
                data_incomplete = any(k in output_lower for k in ("数据不全", "缺失", "未找到", "no result", "empty"))
                if data_incomplete and not has_text_fallback:
                    new_idx = max(x["step_index"] for x in items) + 1 if items else 0
                    supplement_step = {
                        "step_index": new_idx,
                        "description": "补充检索缺失的项目数据(预算明细/设备部署数据)",
                        "depends_on": [],
                        "priority": "P0",
                        "deliverable": "补充数据",
                        "expected_output": "完整项目数据",
                        "status": "pending",
                        "retry_count": 0,
                    }
                    items.append(supplement_step)
                    dynamic_added.append(supplement_step)
                    logger.info(f"Task-Planner: 动态重新规划 - RAG数据不全, 新增步骤{new_idx}: 补充检索")
        else:
            remaining_after = [it for it in items if it.get("status") == "pending"]
            has_text_fallback = any("文字版" in it.get("description", "") or "降级" in it.get("description", "") for it in remaining_after)
            if tool_name == "algo:plot" and not has_text_fallback:
                new_idx = max(x["step_index"] for x in items) + 1 if items else 0
                fallback_step = {
                    "step_index": new_idx,
                    "description": "绘图工具失败降级: 在文档中插入文字版数据说明替代图表",
                    "depends_on": [],
                    "priority": "P1",
                    "deliverable": "文字版数据说明",
                    "expected_output": "文字版预算占比说明",
                    "status": "pending",
                    "retry_count": 0,
                }
                items.append(fallback_step)
                dynamic_added.append(fallback_step)
                logger.info(f"Task-Planner: 动态重新规划 - 绘图失败, 新增步骤{new_idx}: 文字版降级")

        for it in items:
            if it.get("status") != "pending":
                continue
            deps = it.get("depends_on", [])
            if not deps:
                continue
            for dep_idx in deps:
                dep_item = next((x for x in items if x["step_index"] == dep_idx), None)
                if dep_item and dep_item.get("status") in ("blocked",):
                    it["status"] = "blocked"
                    it["blocked_reason"] = f"前置依赖任务{dep_idx}阻塞"
                    logger.warning(f"Task-Planner: 任务{it['step_index']}因前置依赖{dep_idx}阻塞而阻塞")
                    inc_counter("task_plan_dep_blocked_total")
                    break

        remaining = [it for it in items if it.get("status") == "pending"]
        all_done = all(it.get("status") == "done" for it in items if it.get("status") != "blocked")

        if remaining or not all_done:
            md = _render_task_plan_md(items)
            logger.info(f"🔁 Task-Planner: 任务{current_idx}完成, 还有{len(remaining)}项待执行\n{md}")
            blocked_items = [it for it in items if it.get("status") == "blocked"]
            update: dict[str, Any] = {
                "task_plan_items": items,
                "task_plan_results": results,
                "task_plan_status": "executing",
                "memory_summary": md,
                "tool_name": "",
                "tool_result": {},
            }
            if blocked_items:
                worst = blocked_items[0]
                update["correction_signal"] = {
                    "signal_type": "pollution",
                    "reason": worst.get("blocked_reason", "unknown block"),
                    "error_type": "business",
                    "step_index": worst["step_index"],
                }
                update["correction_loops"] = state.get("correction_loops", 0) + 1
                inc_counter("graph_correction_exhaust_total")
                try:
                    from app.services.audit.signal_audit import write_signal_audit, SignalAuditRecord
                    write_signal_audit(SignalAuditRecord(
                        session_id=state.get("session_id", "unknown"),
                        user_id=state.get("user_id", "unknown"),
                        trace_id=state.get("trace_id"),
                        signal_type="pollution",
                        signal_reason=worst.get("blocked_reason", "unknown block"),
                        correction_loops=update["correction_loops"],
                    ))
                except Exception as audit_err:
                    logger.warning(f"审计日志写入失败(非致命): {audit_err}")
            return update

        md = _render_task_plan_md(items)
        summary = f"✅ 全部任务执行完毕\n\n{md}\n\n交付物汇总：\n"
        for it in items:
            if it.get("deliverable"):
                size_info = f" ({it.get('deliverable_size', '?')}chars)" if it.get("deliverable_size") else ""
                summary += f"  - 任务{it['step_index']}: {it['deliverable']}{size_info}\n"
        logger.info(summary)
        inc_counter("task_plan_completed_total")
        return {
            "task_plan_items": items,
            "task_plan_results": results,
            "task_plan_status": "completed",
            "memory_summary": summary,
            "correction_signal": {},
            "tool_name": "",
            "tool_result": {},
        }


_TASK_PLAN_ALLOWED_TARGETS = frozenset({
    "app_launch_agent_node", "system_clean_agent_node",
    "browser_agent_node", "store_agent_node", "content_gen_agent_node",
    "image_agent_node", "algorithm_agent_node", "rag_retrieve_node",
    "code_search_node", "memory_persist_node", "clarification_node",
})


def route_after_task_plan(state: AgentState) -> str:
    plan_status = state.get("task_plan_status", "")
    tool_name = state.get("tool_name", "")
    if plan_status == "completed":
        if tool_name:
            return "task_plan_collect_node"
        if state.get("last_error"):
            return "post_validate_gate"
        return "memory_persist_node"
    if plan_status in ("executing", "planning"):
        if tool_name:
            return "task_plan_collect_node"
        route_target = state.get("route_target", "")
        if route_target and route_target in _TASK_PLAN_ALLOWED_TARGETS:
            return route_target
        if route_target:
            logger.warning(f"route_after_task_plan: route_target={route_target}不在白名单, 降级到task_planner_node")
        return "task_planner_node"
    if plan_status == "blocked":
        return "task_planner_node"
    return "memory_persist_node"


def route_after_task_plan_exec(state: AgentState) -> str:
    plan_status = state.get("task_plan_status", "")
    if plan_status == "completed":
        if state.get("last_error"):
            return "post_validate_gate"
        return "memory_persist_node"
    return "task_planner_node"


_GOVERNOR_MAX_CORRECTION_LOOPS = int(os.getenv("GOVERNOR_MAX_CORRECTION_LOOPS", "3"))
_GOVERNOR_HITL_SIGNAL_TYPES = frozenset({"pollution"})


async def governor_node(state: AgentState) -> dict[str, Any]:
    """
    Governor治理节点:
    1. 读取correction_signal, 判断信号类型
    2. 校正循环次数保护, 超过MAX_CORRECTION_LOOPS直接终止
    3. pollution信号触发HITL人工等待, 暂停图执行
    4. 更新metrics, 更新state内信号状态
    """
    with NodeMetrics("governor_node"):
        correction_signal = state.get("correction_signal", {})
        correction_loops = state.get("correction_loops", 0)
        task_plan_enabled = state.get("task_plan_enabled", False)

        if not correction_signal:
            return {
                "correction_signal": {},
                "needs_hitl": False,
                "task_plan_enabled": task_plan_enabled,
            }

        signal_type = correction_signal.get("signal_type", "unknown")
        inc_counter(f"graph_correction_signal_{signal_type}_total")

        if correction_loops >= _GOVERNOR_MAX_CORRECTION_LOOPS:
            logger.warning(f"Governor: 校正循环达到上限({_GOVERNOR_MAX_CORRECTION_LOOPS}), 任务强制终止")
            inc_counter("graph_correction_exhaust_total")
            try:
                from app.services.audit.signal_audit import write_signal_audit, SignalAuditRecord
                write_signal_audit(SignalAuditRecord(
                    session_id=state.get("session_id", "unknown"),
                    user_id=state.get("user_id", "unknown"),
                    trace_id=state.get("trace_id"),
                    signal_type="terminated",
                    signal_reason=f"校正循环次数超过最大阈值({_GOVERNOR_MAX_CORRECTION_LOOPS}), 任务终止",
                    correction_loops=correction_loops,
                ))
            except Exception as audit_err:
                logger.warning(f"审计日志写入失败(非致命): {audit_err}")
            return {
                "correction_signal": {
                    **correction_signal,
                    "signal_type": "terminated",
                    "reason": f"校正循环次数超过最大阈值({_GOVERNOR_MAX_CORRECTION_LOOPS}), 任务终止",
                },
                "needs_hitl": False,
                "task_plan_enabled": False,
                "needs_clarification": True,
                "clarification_message": f"校正尝试{correction_loops}次仍然失败, 任务终止, 请人工排查问题",
            }

        if signal_type in _GOVERNOR_HITL_SIGNAL_TYPES:
            logger.info(f"Governor: 收到{signal_type}信号, 进入HITL人工等待, signal={correction_signal}")
            return {
                "correction_signal": correction_signal,
                "needs_hitl": True,
                "task_plan_enabled": task_plan_enabled,
                "needs_clarification": True,
                "clarification_message": f"任务阻塞, 生成{signal_type}信号, 等待人工ack/resolve处理",
            }

        return {
            "correction_signal": correction_signal,
            "needs_hitl": False,
            "task_plan_enabled": task_plan_enabled,
        }


async def hitl_approval_node(state: AgentState) -> dict[str, Any]:
    """
    HITL人工审批节点
    图会在进入此节点前interrupt_before, 暂停等待外部API写入hitl_decision
    approve: 清空信号, 继续任务循环
    reject: 关闭任务, 停止规划循环, 标记任务终止
    """
    with NodeMetrics("hitl_approval_node"):
        hitl_decision = state.get("hitl_decision", "")
        hitl_comment = state.get("hitl_comment", "")
        correction_signal = state.get("correction_signal", {})

        if not hitl_decision:
            return {}

        if hitl_decision == "approve":
            return {
                "correction_signal": {},
                "needs_hitl": False,
                "hitl_decision": "",
                "hitl_comment": hitl_comment,
                "needs_clarification": False,
            }
        elif hitl_decision == "reject":
            logger.warning(f"HITL人工拒绝任务, signal: {correction_signal}, comment={hitl_comment}")
            inc_counter("graph_hitl_reject_total")
            return {
                "task_plan_enabled": False,
                "needs_hitl": False,
                "hitl_decision": "",
                "hitl_comment": hitl_comment,
                "correction_signal": {
                    **correction_signal,
                    "signal_type": "rejected",
                    "reason": f"人工拒绝任务, 备注: {hitl_comment}",
                },
                "needs_clarification": True,
                "clarification_message": "人工审批拒绝, 任务终止。",
            }
        else:
            logger.error(f"非法HITL decision: {hitl_decision}")
            return {}


def route_after_governor(state: AgentState) -> str:
    needs_hitl = state.get("needs_hitl", False)
    task_plan_enabled = state.get("task_plan_enabled", False)
    if needs_hitl:
        return "hitl_approval_node"
    if task_plan_enabled:
        return "task_planner_node"
    return "memory_persist_node"


def route_after_hitl(state: AgentState) -> str:
    hitl_decision = state.get("hitl_decision", "")
    task_plan_enabled = state.get("task_plan_enabled", False)
    if hitl_decision == "approve":
        return "task_planner_node"
    if hitl_decision == "reject" or not task_plan_enabled:
        return "memory_persist_node"
    return "hitl_approval_node"


async def qloo_cultural_recommend_node(state: AgentState) -> dict[str, Any]:
    """Qloo cultural anchor resolution + taste recommendation node.

    This node is the SINGLE entry point for Qloo grounding in the agent
    pipeline: it is (a) wired into the full LangGraph StateGraph and (b) also
    awaited directly by the /chat/agent endpoint, so every live recommendation
    actually executes inside the agent framework's node implementation.

    Every Qloo HTTP call is individually fault-tolerant: a failure in one call
    degrades to an empty result instead of failing the whole node, so a mock or
    flaky network can never break the chat path.
    """
    with NodeMetrics("qloo_cultural_recommend_node"):
        try:
            from app.services.qloo.client import get_qloo_client
            from app.services.qloo.taste import (
                search_cultural_entities,
                get_taste_based_recommendations,
                get_cross_domain_discovery,
                build_cultural_context_for_llm,
            )
            client = get_qloo_client()
            if not client.enabled:
                return {"qloo_enabled": False, "qloo_taste_context": ""}
            # P3 DI: /chat/agent injects the session's FeedbackStore via
            # node_state["feedback_store"]; when the node runs outside that
            # endpoint, fall back to the registry keyed by session_id.
            store = state.get("feedback_store")
            if store is None:
                from app.services.qloo.feedback import get_feedback_store

                store = get_feedback_store(state.get("session_id"))
            raw_query = state.get("raw_query", "")
            entities = state.get("entities", {})
            if not isinstance(entities, dict):
                entities = {}
            taste_entities = state.get("taste_entities", [])
            if not isinstance(taste_entities, list):
                taste_entities = []
            seed_names = entities.get("cultural_likes", []) if isinstance(entities.get("cultural_likes"), list) else []
            if not isinstance(seed_names, list):
                seed_names = []
            seed_names = [str(s) for s in seed_names if s]
            target_domain = entities.get("target_domain", "") or ""
            if not isinstance(target_domain, str):
                target_domain = ""
            # Multi-domain support: a combined "eat + wear" request carries ALL
            # matched target domains so fashion (and other secondary asks) are
            # never truncated away by the old single-domain detection.
            raw_domains = entities.get("target_domains", [])
            if not isinstance(raw_domains, list):
                raw_domains = [raw_domains] if raw_domains else []
            target_domains: list[str] = [str(d) for d in raw_domains if d]
            if not target_domains and target_domain:
                target_domains = [target_domain]
            # Geographic signal ("in New York") plumbed to Qloo's
            # filter.location.query so recommendations respect the user's city.
            location_query = entities.get("location_query", "") or ""
            if not isinstance(location_query, str):
                location_query = ""
            # Qloo structured-template excludes: seed-level blacklist (exact /
            # substring) + whole-class result keywords ("italian pop").
            exclude_seeds = entities.get("exclude_seeds", [])
            exclude_seeds = [str(s) for s in exclude_seeds] if isinstance(exclude_seeds, list) else []
            exclude_keywords = entities.get("exclude_keywords", [])
            exclude_keywords = (
                [str(k).lower() for k in exclude_keywords]
                if isinstance(exclude_keywords, list)
                else []
            )
            blocked_set = {s.strip().lower() for s in exclude_seeds}
            keyword_set = {k for k in exclude_keywords if k}
            if not seed_names:
                seed_names = [raw_query]
            seed_entity_ids: list[str] = []
            # Blocked anchors are never used as signals; when they still resolve,
            # their entity IDs are collected so Qloo's filter.exclude.entities can
            # keep them (and their off-theme neighbors) out of the results.
            exclude_entity_ids: list[str] = []
            # Resolved taste-entity names (already grounded) are skipped in the
            # per-seed search loop below. NOTE: build the set in an isolated
            # statement — `name in (...) for te in taste_entities` inside any()
            # is unreliable under CPython 3.13's inlined-comprehension handling.
            resolved_taste_names: set[str] = set()
            resolved_entities: list[dict[str, Any]] = []
            if taste_entities:
                for te in taste_entities:
                    if not isinstance(te, dict):
                        continue
                    eid = te.get("entity_id") or te.get("id", "")
                    name = te.get("name", "")
                    if name and _seed_is_blocked(str(name), blocked_set, keyword_set):
                        if eid and eid not in exclude_entity_ids:
                            exclude_entity_ids.append(eid)
                        continue
                    if eid:
                        seed_entity_ids.append(eid)
                        resolved_entities.append(te)
                    if name:
                        resolved_taste_names.add(str(name))
                        if name not in seed_names:
                            seed_names.append(name)
            for name in seed_names:
                if name in resolved_taste_names or _seed_is_blocked(str(name), blocked_set, keyword_set):
                    continue
                try:
                    ent = await _resolve_anchor(client, name)
                except Exception as e:
                    logger.warning(f"qloo anchor resolve failed for {name!r}: {e}")
                    ent = None
                if not ent or not isinstance(ent, dict):
                    continue
                eid = ent.get("id") or ent.get("entity_id", "")
                if not eid:
                    continue
                if eid in seed_entity_ids:
                    # Same Qloo entity resolved from another seed (e.g. several
                    # core anchors landing on one artist) — already a signal, so
                    # never duplicate the anchor in the list or grounding panel.
                    continue
                if _seed_is_blocked(str(ent.get("name") or name), blocked_set, keyword_set):
                    # Resolved to a blacklisted entity — never a signal; exclude it
                    # from results instead (real Qloo filter.exclude.entities).
                    if eid not in exclude_entity_ids:
                        exclude_entity_ids.append(eid)
                    continue
                seed_entity_ids.append(eid)
                resolved_taste_names.add(str(name))
                # Keep the image URL and any Qloo match score so the web
                # Grounding panel can render a real thumbnail AND a score
                # (e.g. "92%") for each resolved anchor — the score is the
                # unfakeable visual proof this came from the taste graph.
                score = ent.get("score")
                if score is None:
                    score = ent.get("popularity")
                resolved_entities.append(
                    {
                        "entity_id": eid,
                        "name": ent.get("name") or name,
                        "type": ent.get("type", ""),
                        "domain": ent.get("domain", ""),
                        "image": ent.get("image") or "",
                        "score": score if isinstance(score, (int, float)) else None,
                    }
                )
            if not seed_entity_ids:
                return {
                    "qloo_enabled": True,
                    "qloo_seed_entity_ids": [],
                    "qloo_seed_names": seed_names,
                    "qloo_target_domain": target_domain,
                    "qloo_target_domains": target_domains,
                    "qloo_location_query": location_query,
                    "qloo_recommendations": [],
                    "qloo_cross_domain_results": {},
                    "qloo_taste_context": "",
                    "qloo_resolved_names": [],
                    "taste_entities": resolved_entities,
                }
            # Forward location only when present so fixed-signature test fakes
            # never receive an unexpected kwarg.
            rec_kwargs: dict[str, Any] = {}
            if location_query:
                rec_kwargs["location_query"] = location_query
            # The recommendation call additionally carries the resolved-blocked
            # URNs (Qloo filter.exclude.entities) — still only when present, so
            # fixed-signature test fakes never see an unexpected kwarg.
            rec_call_kwargs = dict(rec_kwargs)
            if exclude_entity_ids:
                rec_call_kwargs["exclude_entities"] = exclude_entity_ids
            rec_result: dict[str, Any] = {}
            try:
                rec_result = await get_taste_based_recommendations(
                    client, seed_entity_ids,
                    target_domain=(target_domains[0] if target_domains else None) or None,
                    limit=10, store=store, **rec_call_kwargs,
                )
            except Exception as e:
                logger.warning(f"qloo taste recommendations failed: {e}")
            rec_result = rec_result if isinstance(rec_result, dict) else {}
            # Result-side class exclusion ("all Italian pop/rap artists"): names
            # matching whole-class keywords are dropped even when the API filter
            # could not express the class (Qloo filter.exclude.entities needs
            # concrete URNs for resolved entities only).
            if keyword_set and rec_result.get("recommendations"):
                kept: list[dict[str, Any]] = []
                for r in rec_result["recommendations"]:
                    if _seed_is_blocked(str(r.get("name", "")), set(), keyword_set):
                        continue
                    kept.append(r)
                rec_result["recommendations"] = kept
            cross_result: dict[str, Any] = {}
            try:
                cross_result = await get_cross_domain_discovery(
                    client, seed_entity_ids, per_domain_limit=5, store=store, **rec_kwargs,
                )
            except Exception as e:
                logger.warning(f"qloo cross-domain discovery failed: {e}")
            if not isinstance(cross_result, dict):
                cross_result = {}
            taste_context = ""
            try:
                taste_context = await build_cultural_context_for_llm(
                    client, seed_names,
                    target_domain=target_domain or None,
                    target_domains=(target_domains or None),
                    limit=8, store=store, **rec_kwargs,
                )
            except Exception as e:
                logger.warning(f"qloo context build failed: {e}")
            if not isinstance(taste_context, str):
                taste_context = ""
            return {
                "qloo_enabled": True,
                "qloo_seed_entity_ids": seed_entity_ids,
                "qloo_seed_names": seed_names,
                "qloo_target_domain": target_domain,
                "qloo_target_domains": target_domains,
                "qloo_location_query": location_query,
                "qloo_recommendations": rec_result.get("recommendations", []),
                "qloo_cross_domain_results": cross_result,
                "qloo_taste_context": taste_context,
                "qloo_resolved_names": [str(e.get("name", "")) for e in resolved_entities if e.get("name")],
                "taste_entities": resolved_entities,
            }
        except Exception as e:
            logger.exception(e)
            return {"last_error": f"qloo_cultural_recommend异常:{str(e)}", "error_type": "business", "qloo_enabled": False}


def route_after_qloo(state: AgentState) -> str:
    if state.get("last_error"):
        return "error_fallback_node"
    return "taste_health_filter_node"


# ===== B档 Qloo Agent 编排节点（意图分支 + 重试回环 + 格式化/回退） =====
# 轻量文化锚点提取：与 chat.py 同源的规则实现，节点自包含（无 NLP 依赖）。

_LIKE_PATTERN = re.compile(
    r"(?:love|loves|like|likes|enjoy|enjoys|fan of|into)\s+([^.!?。！？\n;]{2,})",
    re.IGNORECASE,
)
_CLAUSE_STARTERS = re.compile(
    r"\b(but|where|what|how|who|which|when|because|needs?|would|can|to|that)\b",
    re.IGNORECASE,
)


def _clean_like_segments(phrase: str, max_likes: int = 6) -> list[str]:
    """切分 like 短语为候选文化锚点，并按句式引导词截断尾部（同 chat.py）。"""
    parts = re.split(r"\s+(?:and|&)\s*|\s+—\s*|\s*,\s*|，|、|;|；", phrase)
    out: list[str] = []
    for part in parts:
        part = part.strip(" \t_·-–—':;\",，。")
        if not part:
            continue
        cut = _CLAUSE_STARTERS.search(part)
        if cut:
            part = part[: cut.start()].strip(" \t-–—':;\",，。")
        part = re.sub(r"^(?:the|a|an)\s+", "", part, count=1, flags=re.I)
        if not part or part.lower() in out:
            continue
        out.append(part)
        if len(out) >= max_likes:
            break
    return out


def _extract_plain_list_likes(message: str, max_likes: int = 6) -> list[str]:
    """节点自包含版：无 like 动词的逗号清单也提取为文化锚点（同 chat.py）。"""
    msg = (message or "").strip()
    if msg.count(",") < 2 and msg.count("，") < 2 and msg.count("、") < 2:
        return []
    msg = re.sub(
        r"(?:\b(give|show|tell|help|recommend|suggest|advise)\s+(?:me|us)?\s*(?:an?|some)?\s*(?:advice|idea|ideas|tip|tips|recommendation|recommendations)?\b.*)$",
        "",
        msg,
        flags=re.IGNORECASE,
    )
    msg = msg.strip(" \t_·-–—':;\",，。")
    if not msg:
        return []
    parts = re.split(r"\s*,\s*|\s*，\s*|\s*、\s*", msg)
    out: list[str] = []
    for part in parts:
        part = part.strip(" \t_·-–—':;\",，。")
        if not part or len(part) < 2:
            continue
        if _CLAUSE_STARTERS.search(part):
            break
        part = re.sub(r"^(?:the|a|an)\s+", "", part, count=1, flags=re.I)
        if part.lower() in out:
            continue
        out.append(part)
        if len(out) >= max_likes:
            break
    return out


def _extract_message_likes(message: str, max_likes: int = 4) -> list[str]:
    """从自由文本中提取至多 max_likes 个文化锚点（节点自包含实现）。"""
    likes: list[str] = []
    for m in _LIKE_PATTERN.finditer(message or ""):
        for seg in _clean_like_segments(m.group(1), max_likes=max_likes):
            if seg.lower() not in [x.lower() for x in likes]:
                likes.append(seg)
            if len(likes) >= max_likes:
                return likes
    if likes:
        return likes
    for seg in _extract_plain_list_likes(message, max_likes=max_likes):
        if seg.lower() not in [x.lower() for x in likes]:
            likes.append(seg)
        if len(likes) >= max_likes:
            return likes
    return likes


def _seed_fallback_queries(seed: str, max_drop: int = 3) -> list[str]:
    """Progressive de-scoping so 'the films of Christopher Nolan' still resolves."""
    words = seed.split()
    return [" ".join(words[i:]) for i in range(max_drop + 1) if len(words) > i]


def _preferred_entity_types(seed: str) -> list[str] | None:
    """Return Qloo entity type URNs the anchor phrase most likely belongs to.

    NOT a hard constraint — it only triggers the type-specific re-search when the
    domain-free top hit is a place AND the phrase clearly names a film/music
    subject. This replaces the old behaviour that FORCED every anchor into the
    recommendation target domain ('eat' turned 'Christopher Nolan' into a
    beer-garden place; 'Chicago electric blues' into a venue).
    """
    text = seed.lower()
    prefer: list[str] = []
    if any(w in text for w in ("film", "movie", "director", "cinema", "nolan")):
        prefer.append("urn:entity:movie")
        prefer.append("urn:entity:person")
    if any(w in text for w in ("blues", "music", "song", "band", "jazz", "artist", "album", "singer", "electric")):
        prefer.append("urn:entity:artist")
    return prefer or None


def _entity_type_urn(entity: dict[str, Any]) -> str:
    """Resolve an entity's Qloo type URN from `type`, `subtype`, or `types`.

    `search_cultural_entities` normalizes hits to a singular `type` key, but
    tests and raw /search payloads may carry `types` (list) or `subtype`
    instead — mirror the project's `_resolve_subtype` so anchors resolve in
    every shape without weakening the signal-type guard.
    """
    raw = entity.get("type") or entity.get("subtype") or ""
    if isinstance(raw, str) and raw.startswith("urn:entity:"):
        return raw
    types = entity.get("types")
    if isinstance(types, list):
        for t in types:
            if isinstance(t, str) and t.startswith("urn:entity:"):
                return t
    return ""


def _seed_is_blocked(name: str, blocked: set[str], keywords: set[str]) -> bool:
    """True when a seed/resolved name hits the Qloo template's exclude list.

    `blocked` holds exact seed names (matched exactly or as a substring so the
    long "Croce Rossa Italiana - …" entry is caught by "croce rossa");
    `keywords` holds whole-class markers ("fellini", "italian pop") applied to
    resolved recommendation names too.
    """
    key = (name or "").strip().lower()
    if not key:
        return True
    if key in blocked:
        return True
    return any(b and len(b) >= 3 and b in key for b in blocked) or any(
        k and k in key for k in keywords
    )


async def _resolve_anchor(client: Any, seed: str) -> dict[str, Any] | None:
    """Resolve one cultural-anchor seed to a real Qloo entity.

    Domain-free first: anchors MUST resolve to their natural cultural type
    (director -> film, 'Chicago blues' -> artists), NOT be forced into the
    recommendation target domain. If the top hit is still a place while the
    phrase names a film/music subject, re-search with the preferred type so the
    anchor stays cultural (the demo grounding defect).

    Guard against non-signal entity types: Qloo /v2/insights rejects
    `signal.interests.entities` values that are album/author/other non-signal
    types with a 400 "invalid signal" error (verified live), which silently
    empties recommendations. When the domain-free top hit lands on such a type
    AND the seed phrase clearly names a film/music/person subject, we re-search
    with the preferred entity type — every re-search result is still a REAL
    Qloo hit (no fabricated anchors), and the chosen entity is guaranteed
    usable as an insights signal.
    """
    from app.services.qloo.taste import search_cultural_entities

    # Entity types Qloo accepts as `signal.interests.entities` in /v2/insights.
    # Anything outside this set (album, author, …) yields a 400 invalid-signal
    # error and must be re-searched into a signal-capable type.
    _SIGNAL_TYPES = {
        "urn:entity:artist", "urn:entity:movie", "urn:entity:tv_show",
        "urn:entity:book", "urn:entity:podcast", "urn:entity:brand",
        "urn:entity:destination", "urn:entity:place", "urn:entity:person",
    }

    for query in _seed_fallback_queries(seed):
        try:
            hits = await search_cultural_entities(client, query, limit=3)
        except Exception as e:
            logger.warning(f"qloo anchor search failed for {query!r}: {e}")
            hits = []
        if not hits or not isinstance(hits[0], dict):
            continue
        preferred = _preferred_entity_types(seed)
        top = hits[0]
        top_type = _entity_type_urn(top)
        top_signal_ok = top_type in _SIGNAL_TYPES
        if preferred and (
            not top_signal_ok
            or top.get("domain") == "dining"
            or top_type == "urn:entity:place"
        ):
            # Non-signal top hit (album/author) or a place for a film/music
            # subject — re-search against the preferred cultural type so the
            # anchor is both the right entity AND a valid insights signal.
            for etype in preferred:
                if etype not in ("urn:entity:movie", "urn:entity:person", "urn:entity:artist"):
                    continue
                try:
                    typed = await search_cultural_entities(client, query, entity_types=[etype], limit=1)
                except Exception as e:
                    logger.warning(f"qloo typed anchor search failed for {query!r}: {e}")
                    typed = []
                if typed and isinstance(typed[0], dict):
                    cand = typed[0]
                    cand_type = _entity_type_urn(cand)
                    if cand_type in _SIGNAL_TYPES and (cand.get("domain") or "").lower() != "dining":
                        return cand
        if top_signal_ok:
            return top
    return None


def input_node(state: AgentState) -> dict[str, Any]:
    """输入归一化：raw_query / session_id / entities / retry_count 类型与默认值兜底。

    不携带 feedback_store / taste_entities 等由外层注入或后续节点维护的字段，
    保证 LangGraph 状态合并不会意外清空它们。
    """
    entities = state.get("entities", {})
    if not isinstance(entities, dict):
        entities = {}
    cultural_likes = entities.get("cultural_likes", [])
    if not isinstance(cultural_likes, list):
        cultural_likes = [cultural_likes] if cultural_likes else []
    cultural_likes = [str(s) for s in cultural_likes if s]
    target_domain = entities.get("target_domain", "") or ""
    target_domains = entities.get("target_domains", [])
    if not isinstance(target_domains, list):
        target_domains = [target_domains] if target_domains else []
    target_domains = [str(d) for d in target_domains if d]
    location_query = entities.get("location_query", "") or ""
    if not isinstance(location_query, str):
        location_query = ""
    # Qloo structured-template excludes: preserved through the graph state merge
    # so qloo_cultural_recommend_node still receives the blacklist when invoked
    # inside build_qloo_agent_graph (input_node rebuilds the entities dict).
    exclude_seeds = entities.get("exclude_seeds", [])
    if not isinstance(exclude_seeds, list):
        exclude_seeds = [exclude_seeds] if exclude_seeds else []
    exclude_seeds = [str(s) for s in exclude_seeds if s]
    exclude_keywords = entities.get("exclude_keywords", [])
    if not isinstance(exclude_keywords, list):
        exclude_keywords = [exclude_keywords] if exclude_keywords else []
    exclude_keywords = [str(k) for k in exclude_keywords if k]
    # persona_mode（locked/mixed）透传：build_qloo_query 据此决定是否从问句提取
    # message likes（locked 必须 PURE read 档案锚点）；route_intent 据此决定是否
    # 用 persona 锚点兜底进入 Qloo 节点。
    persona_mode = str(entities.get("persona_mode") or "")
    try:
        retry_count = max(int(state.get("retry_count") or 0), 0)
    except (TypeError, ValueError):
        retry_count = 0
    return {
        "raw_query": str(state.get("raw_query") or ""),
        "session_id": str(state.get("session_id") or "default"),
        "entities": {
            "cultural_likes": cultural_likes,
            "target_domain": str(target_domain),
            "target_domains": target_domains,
            "location_query": str(location_query),
            "exclude_seeds": exclude_seeds,
            "exclude_keywords": exclude_keywords,
            "persona_mode": persona_mode,
        },
        "retry_count": retry_count,
        "last_error": None,
    }


def intent_node(state: AgentState) -> dict[str, Any]:
    """B档规则意图分类节点（无本地 LLM）：输出 intent / intent_confidence。"""
    from app.services.graph.checkers import QLOO_INTENT, UNKNOWN_INTENT, classify_intent

    intent = classify_intent(str(state.get("raw_query", "")))
    return {
        "intent": intent,
        "intent_confidence": 1.0 if intent == QLOO_INTENT else 0.0,
    }


def build_qloo_query(state: AgentState) -> dict[str, Any]:
    """构造 Qloo 查询负载：seed 名称（entities.cultural_likes）+ target_domain。

    消息内联的 like 锚点（如 "loves Frank Sinatra"）会补充进 seed 列表；
    seed 为空时才回退到 raw_query 整体作为兜底查询项。
    """
    entities = state.get("entities", {}) or {}
    likes = entities.get("cultural_likes", [])
    if not isinstance(likes, list):
        likes = [likes] if likes else []
    likes = [str(s) for s in likes if s]
    # persona_mode='locked'（终版契约④②）：种子是档案锚点的 PURE read，绝不从
    # 问句文本提取新的 message likes——用户锁上档案后问什么都用已校验锚点。
    if entities.get("persona_mode") != "locked":
        for m in _extract_message_likes(str(state.get("raw_query", ""))):
            if m.lower() not in [x.lower() for x in likes]:
                likes.append(m)
    if not likes:
        likes = [str(state.get("raw_query", "")) or "dinner"]
    target_domain = entities.get("target_domain", "") or ""
    target_domains = entities.get("target_domains", [])
    if not isinstance(target_domains, list):
        target_domains = [target_domains] if target_domains else []
    target_domains = [str(d) for d in target_domains if d]
    location_query = entities.get("location_query", "") or ""
    if not isinstance(location_query, str):
        location_query = ""
    return {
        "qloo_query": {
            "seed_names": likes,
            "target_domain": str(target_domain) or None,
            "target_domains": target_domains or None,
            "location_query": str(location_query) or None,
            "limit": 10,
        },
        "qloo_seed_names": likes,
        "qloo_target_domain": str(target_domain),
    }



async def qloo_call_node(state: AgentState) -> dict[str, Any]:
    """B档真实 Qloo 调用节点：复用 qloo_cultural_recommend_node 的全部内部逻辑。

    - 合并节点返回并写入 `qloo_raw_response`（解析实体 / 推荐 / 跨域结果摘要）。
    - 显式清空 `last_error`：只有本次尝试真正失败才保留，避免上一次重试的错误
      残留污染 `check_qloo_result` 的决策。
    """
    with NodeMetrics("qloo_call_node"):
        try:
            result = await qloo_cultural_recommend_node(state)
        except Exception as e:
            logger.exception(e)
            result = {
                "qloo_enabled": False,
                "last_error": f"qloo_call_node异常:{e}",
                "error_type": "business",
            }
    merged: dict[str, Any] = dict(result) if isinstance(result, dict) else {}
    if not merged.get("last_error"):
        merged["last_error"] = None
    merged["qloo_raw_response"] = {
        "resolved_names": merged.get("qloo_resolved_names", []),
        "recommendations": merged.get("qloo_recommendations", []),
        "cross_domain": merged.get("qloo_cross_domain_results", {}),
    }
    return merged


def retry_node(state: AgentState) -> dict[str, Any]:
    """B档重试节点：retry_count+1、清理 last_error、记录重试原因，回到 qloo_call_node。"""
    try:
        retries = int(state.get("retry_count") or 0) + 1
    except (TypeError, ValueError):
        retries = 1
    reason = ""
    if state.get("last_error"):
        reason = str(state["last_error"])[:200]
    elif not state.get("qloo_resolved_names") and not state.get("qloo_recommendations"):
        reason = "qloo returned no resolvable anchors (empty result)"
    else:
        reason = "qloo retry"
    inc_counter("qloo_retry_triggered_total")
    return {
        "retry_count": retries,
        "last_error": None,
        "retry_triggered": True,
        "qloo_retry_reason": reason,
    }


def format_output(state: AgentState) -> dict[str, Any]:
    """B档成功出口：保证 taste_data_source 标记 live（图内兜底为 preview）。"""
    data_source = state.get("taste_data_source", "") or ""
    if not data_source:
        data_source = "live" if state.get("qloo_enabled") else "preview"
    return {"taste_data_source": data_source}


def fallback_node(state: AgentState) -> dict[str, Any]:
    """B档回退出口：无 live 数据时降级为 preview，附回退原因（诚实降级，不伪造证据）。"""
    intent = state.get("intent", "")
    if state.get("last_error"):
        reason = f"qloo live call degraded: {state['last_error']}"
    elif intent and intent != "qloo_recommend":
        reason = f"intent '{intent}' is out of the qloo agent scope — plain reply"
    elif not state.get("qloo_enabled"):
        reason = "qloo disabled (no key) — preview/preference-only grounding"
    else:
        reason = "qloo returned no resolvable cultural anchors after retries"
    inc_counter("qloo_fallback_triggered_total")
    return {
        "qloo_enabled": False,
        "taste_data_source": "preview",
        "fallback_message": reason,
        "last_error": None,
    }


# ===== Senior Dining Sub-Graph Nodes =====

async def taste_context_extract_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("taste_context_extract_node"):
        try:
            from app.services.tools.executor import _exec_qloo_taste_context

            raw_query = state.get("raw_query", "")
            entities = state.get("entities", {})
            likes = entities.get("cultural_likes", []) if isinstance(entities.get("cultural_likes"), list) else []
            if not likes:
                likes = [w for w in raw_query.replace("，", ",").replace("、", ",").split(",") if w.strip()][:5]
            result = await _exec_qloo_taste_context({"likes": likes})
            data = result.get("data", result)
            return {
                "taste_entities": data.get("taste_entities", []),
                "taste_data_source": data.get("data_source", "none"),
                "qloo_enabled": data.get("qloo_enabled", False),
                "qloo_taste_context": data.get("qloo_context", ""),
            }
        except Exception as e:
            logger.exception(e)
            return {"taste_entities": [], "taste_data_source": "error", "last_error": f"taste_context_extract异常:{str(e)}"}


class HealthConstraintOutput(BaseModel):
    low_sugar: bool = Field(default=False, description="需要低糖/无糖饮食")
    low_sodium: bool = Field(default=False, description="需要低盐/低钠饮食")
    soft_chewable: bool = Field(default=False, description="需要软食/易咀嚼")
    medications: list[str] = Field(default_factory=list, description="当前用药列表，如降压药、降糖药、抗凝药")
    dietary_notes: list[str] = Field(default_factory=list, description="其他膳食注意事项，如过敏、忌口")
    reasoning: str = Field(default="", description="提取推理过程")


async def health_constraint_extract_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("health_constraint_extract_node"):
        try:
            raw_query = state.get("raw_query", "")
            existing = state.get("health_constraints", {})
            if existing and existing.get("_source") == "explicit":
                return {}
            prompt = (
                f"用户请求：{raw_query}\n\n"
                f"从上述对话中提取老年膳食健康约束信息。\n"
                f"如果没有明确提到健康约束，所有布尔字段返回 False，medications 和 dietary_notes 返回空列表。\n"
                f"常见关键词映射：\n"
                f"  - 低糖/无糖/控糖/糖尿病 → low_sugar=True\n"
                f"  - 低盐/低钠/少盐/高血压/降压 → low_sodium=True\n"
                f"  - 软食/易咀嚼/牙口不好/流食 → soft_chewable=True\n"
                f"  - 降压药/血压药 → medications含'antihypertensive'\n"
                f"  - 降糖药/胰岛素 → medications含'antidiabetic'\n"
                f"  - 抗凝药/华法林 → medications含'anticoagulant'\n"
                f"schema {HealthConstraintOutput.model_json_schema()}"
            )
            from app.services.llm.client import llm_parse_with_retry
            if LLM_MODE == "real":
                parsed, _ = await llm_parse_with_retry(prompt, HealthConstraintOutput)
            else:
                parsed = _mock_health_constraints(raw_query)
            if parsed is None:
                return {"health_constraints": {}, "health_constraint_labels": []}
            constraints = parsed.model_dump()
            constraints["_source"] = "llm_extracted"
            labels = []
            if constraints.get("low_sugar"):
                labels.append("low_sugar")
            if constraints.get("low_sodium"):
                labels.append("low_sodium")
            if constraints.get("soft_chewable"):
                labels.append("soft_chewable")
            if constraints.get("medications"):
                labels.append("medication_aware")
            return {"health_constraints": constraints, "health_constraint_labels": labels}
        except Exception as e:
            logger.exception(e)
            return {"health_constraints": {}, "health_constraint_labels": [], "last_error": f"health_constraint_extract异常:{str(e)}"}


def _mock_health_constraints(raw_query: str) -> HealthConstraintOutput:
    q = raw_query.lower()
    low_sugar = any(k in q for k in ("低糖", "无糖", "控糖", "糖尿病", "diabetes", "sugar"))
    low_sodium = any(k in q for k in ("低盐", "低钠", "少盐", "高血压", "血压", "hypertension", "sodium"))
    soft = any(k in q for k in ("软食", "易咀嚼", "牙口", "流食", "soft", "chew", "dentition", "teeth", "gum"))
    meds: list[str] = []
    if any(k in q for k in ("降压", "血压药")):
        meds.append("antihypertensive")
    if any(k in q for k in ("降糖", "胰岛素")):
        meds.append("antidiabetic")
    if any(k in q for k in ("抗凝", "华法林")):
        meds.append("anticoagulant")
    return HealthConstraintOutput(low_sugar=low_sugar, low_sodium=low_sodium, soft_chewable=soft, medications=meds)


def route_after_taste_extract(state: AgentState) -> str:
    if state.get("last_error"):
        return "error_fallback_node"
    return "health_constraint_extract_node"


def route_after_health_extract(state: AgentState) -> str:
    if state.get("last_error"):
        return "error_fallback_node"
    return "qloo_cultural_recommend_node"


async def taste_health_filter_node(state: AgentState) -> dict[str, Any]:
    with NodeMetrics("taste_health_filter_node"):
        try:
            from app.services.qloo.tastecare import (
                _annotate_health,
                _annotate_medication,
                _build_constraint_labels,
                _sort_candidates,
                MEDICATION_DISCLAIMER,
            )

            recommendations = state.get("qloo_recommendations", [])
            health_constraints = state.get("health_constraints", {})
            taste_entities = state.get("taste_entities", [])

            if not recommendations:
                return {
                    "filtered_recommendations": [],
                    "filter_summary": {"total": 0, "passed": 0, "flagged": 0, "active_labels": []},
                }

            active_labels = _build_constraint_labels(health_constraints)
            medications = health_constraints.get("medications", [])
            if isinstance(medications, str):
                medications = [medications]

            passed_count = 0
            flagged_count = 0
            filtered: list[dict[str, Any]] = []

            for rec in recommendations:
                entity = dict(rec)
                health = _annotate_health(entity, active_labels)
                med = _annotate_medication(entity, medications)
                entity["health"] = {
                    "passes": health["passes"] and med["passes"],
                    "labels": health["labels"] + med["labels"],
                    "warnings": health["warnings"] + med["warnings"],
                    "usda": health.get("usda"),
                }
                # Structured screening bucket (same contract as tastecare.recommend_meals):
                # "pass" = fully meets active constraints, "review" = culturally matched
                # but some menu items may exceed them. Derived from health.passes only.
                entity["screening"] = "pass" if entity["health"]["passes"] else "review"
                if entity["health"]["passes"]:
                    passed_count += 1
                else:
                    flagged_count += 1
                filtered.append(entity)

            filtered = _sort_candidates(filtered)

            taste_names = [t.get("name", "") for t in taste_entities if t.get("name")]

            summary = {
                "total": len(filtered),
                "passed": passed_count,
                "flagged": flagged_count,
                "active_labels": active_labels,
                "medication_aware": bool(medications),
                "taste_anchors": taste_names[:5],
                "data_source": state.get("taste_data_source", "none"),
            }

            return {
                "filtered_recommendations": filtered,
                "filter_summary": summary,
            }
        except Exception as e:
            logger.exception(e)
            return {
                "filtered_recommendations": state.get("qloo_recommendations", []),
                "filter_summary": {"error": str(e)},
                "last_error": f"taste_health_filter异常:{str(e)}",
            }


def _build_constraint_labels_gn(config_section_constraints: dict[str, Any]) -> list[str]:
    """Local mirror of tastecare._build_constraint_labels used by answer_generation_node."""
    out: list[str] = []
    if config_section_constraints.get("low_sodium"):
        out.append("low_sodium")
    if config_section_constraints.get("low_sugar"):
        out.append("low_sugar")
    if config_section_constraints.get("soft_chewable"):
        out.append("soft_chewable")
    return out


def _recommendation_rationale(
    rec: dict[str, Any],
    taste_anchors: list[str],
    active_labels: list[str],
) -> dict[str, Any]:
    """Build the two-part (cultural taste match + safety validation) rationale for one meal.

    Pure/deterministic — runnable without a live Qloo key. The cultural-match line is
    grounded in the actual taste anchors collected by `taste_context_extract_node` and
    the Qloo `why`/description when present; the safety line is grounded in the real
    health annotation computed by `taste_health_filter_node`. Nothing is invented.
    """
    name = rec.get("name", "")
    desc = rec.get("description") or ""
    health = rec.get("health") or {}

    if taste_anchors:
        cultural = (
            f"Matches your cultural tastes ({', '.join(taste_anchors[:3])}) "
            f"as grounded in the Qloo taste graph."
        )
    else:
        cultural = "Grounded in the Qloo cultural taste graph for your profile."
    if desc:
        cultural += f" {desc.strip()}"
    if rec.get("fit") is not None:
        try:
            pct = round(float(rec["fit"]) * 100)
            cultural += f" Cultural-match score {pct}%."
        except (TypeError, ValueError):
            pass

    labels = health.get("labels", [])
    warnings = health.get("warnings", [])
    passes = bool(health.get("passes"))
    if active_labels:
        safety = (
            f"Checked against your active constraints ({', '.join(active_labels)}) — "
            + ("all passed." if passes else "see warnings below.")
        )
    else:
        safety = "No active health constraints applied."
    if warnings:
        safety += " Warnings: " + " ".join(warnings) + "."

    return {
        "name": name,
        "cultural_match": cultural,
        "safety_validation": safety,
        "passes": passes,
    }
def route_after_taste_health_filter(state: AgentState) -> str:
    if state.get("last_error"):
        return "error_fallback_node"
    return "answer_generation_node"
async def answer_generation_node(state: AgentState) -> dict[str, Any]:
    """A1: generate the final recommendation answer from the filtered candidates.

    Consumes `filtered_recommendations` (produced by `taste_health_filter_node`) +
    `taste_entities` + `health_constraints`, and emits both a structured
    `recommendation_rationale` list (one per meal) and a plain-language `final_answer`
    for the agent to present. Mirrors the two-part rationale requirement so the UI can
    render exactly "✨ Cultural match" + "🛡️ Safety check" per card via the `rationale`.
    """
    with NodeMetrics("answer_generation_node"):
        try:
            try:
                from app.services.observability.langfuse_client import (
                    langfuse,
                    create_langfuse_span,
                )
            except ImportError:
                langfuse = None
                create_langfuse_span = None

            filtered = state.get("filtered_recommendations", []) or []
            taste_entities = state.get("taste_entities", []) or []
            health_constraints = state.get("health_constraints", {}) or {}
            labels = state.get("health_constraint_labels", []) or []
            filter_summary = state.get("filter_summary", {}) or {}

            active_labels = (
                list(labels)
                or filter_summary.get("active_labels", [])
                or _build_constraint_labels_gn(health_constraints)
            )
            taste_anchors = [
                t.get("name", "")
                for t in taste_entities
                if isinstance(t, dict) and t.get("name")
            ][:5]

            rationale = [
                _recommendation_rationale(r, taste_anchors, active_labels)
                for r in filtered
            ]

            if not rationale:
                final_answer = (
                    "I could not find dining options that both match your cultural "
                    "tastes and pass all of your health constraints. "
                    "Try broadening your tastes or relaxing a constraint."
                )
            else:
                top = rationale[0]
                passed = sum(1 for r in rationale if r["passes"])
                final_answer = (
                    f"Top pick for you: {top['name']}.\n\n"
                    f"✨ Cultural match — {top['cultural_match'].strip()}\n"
                    f"🛡️ Safety validation — {top['safety_validation'].strip()}\n\n"
                    f"Of {len(rationale)} recommendations screened, {passed} fit all your "
                    f"active constraints. Full list: "
                    + ", ".join(r["name"] for r in rationale[:6])
                    + "."
                )

            if create_langfuse_span and langfuse:
                span = create_langfuse_span(
                    langfuse,
                    "answer_generation_node",
                    input_data={
                        "candidate_count": len(filtered),
                        "taste_anchors": taste_anchors,
                        "active_labels": active_labels,
                        "data_source": state.get("taste_data_source", "none"),
                    },
                    metadata={
                        "rationale_count": len(rationale),
                        "passed_count": sum(1 for r in rationale if r["passes"]),
                    },
                )
                span.end()

            return {
                "answer_generation": {
                    "final_answer": final_answer,
                    "rationale": rationale,
                    "taste_anchors": taste_anchors,
                    "active_labels": active_labels,
                },
                "final_answer": final_answer,
            }
        except Exception as e:
            logger.exception(e)
            return {
                "final_answer": state.get("qloo_taste_context", "")
                or "Unable to generate a final recommendation.",
                "last_error": f"answer_generation异常:{str(e)}",
                "error_type": "business",
            }
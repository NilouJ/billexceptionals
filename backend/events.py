from schemas import AGENT_LABELS


def agent_running_event(case_id: str, agent_key: str) -> dict:
    return {
        "type":      "agent_status",
        "case_id":   case_id,
        "agent_key": agent_key,
        "agent":     AGENT_LABELS[agent_key],
        "status":    "running",
    }


def agent_done_event(case_id: str, agent_key: str, decision: str, reasons: list, rule_hits: list, evidence: dict | None = None) -> dict:
    return {
        "type":      "agent_status",
        "case_id":   case_id,
        "agent_key": agent_key,
        "agent":     AGENT_LABELS[agent_key],
        "status":    "done",
        "decision":  decision,
        "reasons":   reasons,
        "rule_hits": rule_hits,
        "evidence":  evidence or {},
    }


def final_result_event(case_id: str, result: dict, trace: list) -> dict:
    return {
        "type":    "final_result",
        "case_id": case_id,
        "result":  result,
        "trace":   trace,
    }


def error_event(case_id: str, message: str) -> dict:
    return {
        "type":    "error",
        "case_id": case_id,
        "message": message,
    }

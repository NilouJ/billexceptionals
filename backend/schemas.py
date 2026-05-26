AGENT_ORDER = [
    "case_intake_triage",
    "precheck",
    "groundrule",
    "sop_context",
    "screening_outcome",
]

AGENT_LABELS = {
    "case_intake_triage": "1 - Case Intake & Triage Agent",
    "precheck":           "2 - Pre-check Agent",
    "groundrule":         "3 - Ground-rule Agent",
    "sop_context":        "4 - SOP Context Agent",
    "screening_outcome":  "5 - Case Screening Outcome Agent",
}

AGENT_STATUS = {
    "PENDING": "pending",
    "RUNNING": "running",
    "DONE":    "done",
    "FAILED":  "failed",
}

DECISIONS = {
    "EXCLUDE":    "RETURN_TO_ONSHORE_EXCLUDED",
    "BLOCK":      "RETURN_TO_ONSHORE_BLOCKED",
    "UNWORKABLE": "RETURN_TO_ONSHORE_UNWORKABLE",
    "WORKABLE":   "WORKABLE",
    "NEEDS_DATA": "RETURN_TO_ONSHORE_NEEDS_SOP",
    "PROCEED":    "PROCEED",
}

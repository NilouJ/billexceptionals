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
    "EXCLUDE":    "EXCLUDE_TO_ONSHORE",
    "BLOCK":      "BLOCK_TO_ONSHORE",
    "UNWORKABLE": "UNWORKABLE_TO_ONSHORE",
    "WORKABLE":   "WORKABLE",
    "NEEDS_DATA": "NEEDS_MORE_DATA",
    "PROCEED":    "PROCEED",
}

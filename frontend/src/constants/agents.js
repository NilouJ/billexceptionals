export const AGENT_ORDER = [
  "case_intake_triage",
  "precheck",
  "groundrule",
  "sop_context",
  "screening_outcome",
];

export const AGENT_LABELS = {
  case_intake_triage: "Case Intake & Triage",
  precheck:           "Pre-check",
  groundrule:         "Ground-rule",
  sop_context:        "SOP Context",
  screening_outcome:  "Screening Outcome",
};

export const AGENT_STATUS = {
  PENDING: "pending",
  RUNNING: "running",
  DONE:    "done",
  FAILED:  "failed",
};

export const DECISIONS = {
  EXCLUDE:    "RETURN_TO_ONSHORE_EXCLUDED",
  BLOCK:      "RETURN_TO_ONSHORE_BLOCKED",
  UNWORKABLE: "RETURN_TO_ONSHORE_UNWORKABLE",
  WORKABLE:   "WORKABLE",
  NEEDS_DATA: "RETURN_TO_ONSHORE_NEEDS_SOP",
  PROCEED:    "PROCEED",
};
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
  EXCLUDE:    "EXCLUDE_TO_ONSHORE",
  BLOCK:      "BLOCK_TO_ONSHORE",
  UNWORKABLE: "UNWORKABLE_TO_ONSHORE",
  WORKABLE:   "WORKABLE",
  NEEDS_DATA: "NEEDS_MORE_DATA",
  PROCEED:    "PROCEED",
};
import { useState } from "react";
import { submitFeedback } from "../api/rest.js";

export default function FeedbackForm({ caseId, result }) {
  const [agree, setAgree] = useState(null);
  const [notes, setNotes] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    await submitFeedback({ case_id: caseId, agree, notes, system_result: result });
    setSubmitted(true);
  };

  if (submitted) return <p className="feedback-thanks">Thanks — feedback recorded.</p>;

  return (
    <form className="feedback-form" onSubmit={onSubmit}>
      <h3>Human Review</h3>
      <label>
        <input type="radio" checked={agree === true} onChange={() => setAgree(true)} /> Agree
      </label>
      <label>
        <input type="radio" checked={agree === false} onChange={() => setAgree(false)} /> Disagree
      </label>
      <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notes…" />
      <button type="submit" disabled={agree === null}>Submit Feedback</button>
    </form>
  );
}
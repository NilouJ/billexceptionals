import AgentCard from "./AgentCard.jsx";

export default function AgentPipeline({ agents }) {
  return (
    <section className="pipeline">
      {agents.map((a, i) => (
        <AgentCard key={a.key} agent={a} index={i + 1} />
      ))}
    </section>
  );
}
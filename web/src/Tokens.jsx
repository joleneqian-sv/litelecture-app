// Renders instructor "manipulatives" — groups of shapes (boxes for variables,
// dots for units) joined by + and =. A compact, deterministic way to show the
// objects an instructor draws, stored as counts (not pixels) in the .litelec.

function Group({ group }) {
  const items = Array.from({ length: group.count });
  return (
    <span className="tok-group">
      {items.map((_, j) => (
        <span key={j} className={"tok tok-" + (group.shape || "dot")}>
          {group.label || ""}
        </span>
      ))}
    </span>
  );
}

export default function Tokens({ spec }) {
  return (
    <div className="tokens">
      {spec.groups.map((g, i) => (
        <span key={i} className="tok-term">
          {i > 0 && <span className="tok-op">+</span>}
          <Group group={g} />
        </span>
      ))}
      {spec.equals && (
        <span className="tok-term">
          <span className="tok-op">=</span>
          <Group group={spec.equals} />
        </span>
      )}
    </div>
  );
}

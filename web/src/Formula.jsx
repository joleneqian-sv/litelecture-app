import { useMemo } from "react";
import katex from "katex";

// Renders a LaTeX string as proper math using KaTeX.
// If the LaTeX is malformed, fall back to the raw string instead of crashing.
export default function Formula({ latex }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(latex, {
        throwOnError: false,
        displayMode: true,
      });
    } catch {
      return null;
    }
  }, [latex]);

  if (html === null) {
    return <code className="formula-fallback">{latex}</code>;
  }
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

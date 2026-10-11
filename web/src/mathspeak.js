// Heuristic LaTeX -> spoken English. A readable fallback used by AccessLearn mode
// when a formula has no hand-written accessibility.math_speech entry.
// Not exhaustive — covers the common arithmetic/algebra patterns. Numbers and
// decimals are left as-is; the speech engine reads "0.18" as "zero point one eight".

const WORDS = [
  [/\\implies/g, " implies "],
  [/\\Rightarrow/g, " implies "],
  [/\\neq/g, " not equal to "],
  [/\\leq/g, " less than or equal to "],
  [/\\geq/g, " greater than or equal to "],
  [/\\times/g, " times "],
  [/\\cdot/g, " times "],
  [/\\div/g, " divided by "],
  [/\\pm/g, " plus or minus "],
  [/\\pi/g, " pi "],
  [/\\infty/g, " infinity "],
  [/\\%/g, " percent "],
  [/\\,/g, " "],
];

export function latexToSpeech(latex) {
  if (!latex) return "";
  let s = " " + latex + " ";

  // fractions (one brace level; repeat to catch a few)
  for (let i = 0; i < 5; i++) {
    s = s.replace(/\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, " $1 over $2 ");
  }
  s = s.replace(/\\sqrt\s*\{([^{}]*)\}/g, " square root of $1 ");

  // powers and subscripts
  s = s.replace(/\^\s*\{([^{}]*)\}/g, " to the power of $1 ");
  s = s.replace(/\^\s*2\b/g, " squared ");
  s = s.replace(/\^\s*3\b/g, " cubed ");
  s = s.replace(/\^\s*([a-zA-Z0-9])/g, " to the power of $1 ");
  s = s.replace(/_\s*\{([^{}]*)\}/g, " sub $1 ");
  s = s.replace(/_\s*([a-zA-Z0-9])/g, " sub $1 ");

  for (const [re, word] of WORDS) s = s.replace(re, word);

  // function notation: f(x) -> "f of x"
  s = s.replace(/([a-zA-Z])\s*\(\s*([^()]*?)\s*\)/g, "$1 of $2");

  // operators
  s = s.replace(/=/g, " equals ");
  s = s.replace(/\+/g, " plus ");
  s = s.replace(/-/g, " minus ");

  // drop any leftover LaTeX commands / braces and tidy whitespace
  s = s.replace(/\\[a-zA-Z]+/g, " ").replace(/[{}\\]/g, " ");
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

#!/usr/bin/env python3
"""
LaTeX canonicalizer for fair CER scoring.

Math-OCR systems emit LaTeX in a different but RENDER-EQUIVALENT dialect from
hand-written ground truth: \\operatorname{l o g} for \\log, \\left( for (,
\\cfrac for \\frac, x^{2} for x^2, stray \\space / \\, spacing, etc. Raw
string CER counts all of that as error, wildly overstating true extraction
error (and, unclamped, exceeds 100%).

normalize() maps both reference and prediction to one canonical dialect so CER
counts only REAL symbol differences (wrong digits, dropped terms, misread
operators). Apply to BOTH sides before Levenshtein.

Everything here is notation-preserving: two strings that render to the same
math normalize to the same string; strings that render differently stay
different.
"""
import re

_SPACING = [r"\\space", r"\\quad", r"\\qquad", r"\\,", r"\\;", r"\\:", r"\\!",
            r"(?<!\\)\\ ", r"~"]  # lookbehind: don't eat the \\ row separator
_SIZING = [r"\\left", r"\\right", r"\\biggl", r"\\biggr", r"\\bigl", r"\\bigr",
           r"\\Bigl", r"\\Bigr", r"\\big", r"\\Big", r"\\small", r"\\displaystyle",
           r"\\textstyle", r"\\mathop"]


def normalize(s):
    if not s:
        return ""
    # 1. collapse letter-spaced command args: {l o g} -> {log} (OCR artifact)
    for _ in range(3):
        s = re.sub(r"\{([a-zA-Z])((?:\s[a-zA-Z])+)\}",
                   lambda m: "{" + m.group(1) + m.group(2).replace(" ", "") + "}", s)
    # 2. spacing commands -> nothing
    for pat in _SPACING:
        s = re.sub(pat, " ", s)
    # 2b. \operatorname{log} / \operatorname*{gcd} / \mathrm{lcm} -> \log \gcd \lcm
    s = re.sub(r"\\(?:operatorname\*?|mathrm)\s*\{([a-zA-Z]+)\}", r"\\\1", s)
    # 3. fraction variants -> \frac ; \sp -> ^ ; \root n \of{x} -> \sqrt[n]{x}
    s = re.sub(r"\\[cdt]frac", r"\\frac", s)
    s = re.sub(r"\\sp\b", "^", s)
    s = re.sub(r"\\root\s+(\S+)\s+\\of", r"\\sqrt[\1]", s)
    # 4. absolute-value variants -> |
    s = re.sub(r"\\[lr]?vert\b", "|", s)
    # 5. relations / arrows synonyms
    s = re.sub(r"\\leq(?![a-zA-Z])", r"\\le", s)
    s = re.sub(r"\\geq(?![a-zA-Z])", r"\\ge", s)
    s = re.sub(r"\\Rightarrow(?![a-zA-Z])", r"\\implies", s)
    # 6. binomial written as a 2-row matrix -> \binom
    s = re.sub(r"\\left\(\s*\\begin\{matrix\}\s*\{?([^{}\\]+?)\}?\s*\\\\\s*"
               r"\{?([^{}\\]+?)\}?\s*(?:\\\\\s*)?\\end\{matrix\}\s*\\right\)",
               r"\\binom{\1}{\2}", s)
    # 7. sizing / font wrappers -> nothing (AFTER matrix rule, which needs \left)
    for pat in _SIZING:
        s = re.sub(pat + r"\b", "", s)
    # 8. drop stray trailing row breaks before \end{...}
    s = re.sub(r"\\\\\s*\\end\{", r"\\end{", s)
    # 9. kill ALL whitespace (CER was already whitespace-insensitive)
    s = re.sub(r"\s+", "", s)
    # 9b. strip decorative braces right after \begin{...} or a row break \\
    s = re.sub(r"(\\begin\{[a-zA-Z]+\})\{([^{}]*)\}", r"\1\2", s)
    s = re.sub(r"(\\\\)\{([^{}]*)\}", r"\1\2", s)
    # 10. ^{c} -> ^c and _{c} -> _c for single characters
    s = re.sub(r"([\^_])\{([a-zA-Z0-9])\}", r"\1\2", s)
    # 11. \frac12 / \frac1x -> \frac{1}{2} (canonical braced form)
    s = re.sub(r"\\frac([a-zA-Z0-9])([a-zA-Z0-9])", r"\\frac{\1}{\2}", s)
    # 12. remove redundant grouping braces: {...} not owned by a command/^/_
    prev = None
    while prev != s:
        prev = s
        out, i = [], 0
        while i < len(s):
            if s[i] == "{":
                j, depth = i + 1, 1
                while j < len(s) and depth:
                    if s[j] == "{":
                        depth += 1
                    elif s[j] == "}":
                        depth -= 1
                    j += 1
                inner = s[i + 1:j - 1]
                before = "".join(out)
                owned = bool(re.search(r"(\\[a-zA-Z]+\*?(\[[^\]]*\])?|\^|_|\})$", before))
                if not owned and "{" not in inner:
                    out.append(inner); i = j; continue
            out.append(s[i]); i += 1
        s = "".join(out)
    return s


def _lev(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def norm_cer(ref, pred):
    """CER on normalized LaTeX, clamped to [0, 1]."""
    r, p = normalize(ref), normalize(pred)
    if not r:
        return 0.0 if not p else 1.0
    return min(1.0, _lev(r, p) / len(r))


def self_test():
    equal = [
        ("(x^2)^3 = x^6", r"\left( x^{2} \right)^{3}=x^{6}"),
        (r"\log_b(xy) = \log_b x + \log_b y",
         r"\operatorname{l o g}_{b} ( x y )=\operatorname{l o g}_{b} x+\operatorname{l o g}_{b} y"),
        (r"\log_b x = \frac{\ln x}{\ln b}",
         r"\operatorname{l o g}_{b} x=\frac{\operatorname{l n} x} {\operatorname{l n} b}"),
        (r"(a + bi)(a - bi) = a^2 + b^2",
         r"( a+b i ) \space\space\space\left( a-b i \right)=a^{2}+b^{2}"),
        (r"\binom{n}{k} = \frac{n!}{k!(n-k)!}",
         r"\left( \begin{matrix} {n} \\ {k} \\ \end{matrix} \right)=\frac{n !} {k ! \left( n-k \right) !}"),
        (r"\frac{2}{3} \div \frac{4}{9} = \frac{3}{2}",
         r"\cfrac{2} {3} \div\cfrac{4} {9}=\cfrac{3} {2}"),
        (r"a^2 + b^2 = c^2", r"a^{2}+b^{2}=c^{2}"),
        (r"c = \sqrt{a^2 + b^2}", r"c=\sqrt{a \sp{2}+b \sp{2}}"),
        (r"x^{m/n} = \sqrt[n]{x^m}", r"x^{m / n}=\root n \of{x^{m}}"),
        (r"\lvert -7 \rvert = 7", r"\left\vert-7 \right\vert=7"),
        (r"A = \frac{1}{2} b h", r"A=\frac1 2 b h"),
        (r"-2x \le 8", r"- 2 x \leq8"),
        (r"f(x) = a(x - h)^2 + k", r"f ( x )=a {( x-h )}^{2}+k"),
        (r"b^{m} \cdot b^{n} = b^{m+n}",
         r"b^{\small m} \cdot b^{\small n}=b^{\small m+n}"),
        (r"\begin{cases} x + y = 5 \\ x - y = 1 \end{cases}",
         r"\begin{cases} {x+y=5} \\ {x-y=1} \\ \end{cases}"),
        (r"S_n = \frac{a_1(1 - r^n)}{1 - r}",
         r"S_{n}=\frac{a_{1} {\left( 1-r^{n} \right)}} {1-r}"),
        (r"a_n = a_1 r^{\,n-1}", r"a_{n}=a_{1} r^{n-1}"),
        (r"\gcd(12, 18) = 6", r"\operatorname* {g c d} ( 1 2 , 1 8 )=6"),
    ]
    different = [  # genuine OCR errors must KEEP a nonzero distance
        (r"25\% = \frac{1}{4}", r"2 5 \%_{0}=\frac{1} {4}"),
        (r"\frac{3}{4} = 75\%", r"\frac{3} {4}=7 5 9_{0}"),
        (r"7 + 5 = 12", r"7+5=1 3"),
    ]
    ok = True
    for ref, pred in equal:
        c = norm_cer(ref, pred)
        tag = "pass" if c == 0 else "FAIL"
        ok &= c == 0
        print(f"[{tag}] want 0.000 got {c:.3f}  {ref!r}")
        if c:
            print(f"       ref  -> {normalize(ref)!r}\n       pred -> {normalize(pred)!r}")
    for ref, pred in different:
        c = norm_cer(ref, pred)
        tag = "pass" if c > 0 else "FAIL"
        ok &= c > 0
        print(f"[{tag}] want >0    got {c:.3f}  {ref!r}")
    print("\nself-test:", "ALL PASS" if ok else "FAILURES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(self_test())

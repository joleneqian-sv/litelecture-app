#!/usr/bin/env python3
"""
L4 code oracle v2 — ENTRY-LEVEL Python and C++ (URTC paper).

60 ground-truth snippets a first-year student would actually see:
  py-basic (15), py-flow (15): variables, print, input, if, loops, simple defs
  cpp-basic (15), cpp-flow (15): cout/cin, int main, if, for, simple functions

Pipeline: render editor-style slides -> mp4 -> OCR frames back (Tesseract TSV,
indentation reconstructed from word x-coordinates) -> score:
  CER(content), same-program check, and VERIFICATION =
    Python: ast.parse + AST equality
    C++:    g++ -fsyntax-only + token-normalized equality
Wrong extraction that still passes the syntax check = SILENT ERROR (needs
ASR / human override) — reported explicitly.

Usage: python3 code_oracle2.py --make && python3 code_oracle2.py --score
"""
import ast, json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VID = os.path.join(HERE, "code_oracle.mp4")
TRUTH = os.path.join(HERE, "code_oracle_truth.json")
OUT = os.path.join(HERE, "code_oracle_results.json")
W, H, SEC = 1280, 720, 3

PY_BASIC = [
 'x = 5',
 'name = "Ada"',
 'print("Hello, world!")',
 'total = 3 + 4 * 2',
 'age = int(input("Age? "))',
 'pi = 3.14159',
 'is_ready = True',
 'print(x + y)',
 'half = 7 // 2',
 'rem = 7 % 2',
 'big = max(3, 9, 5)',
 'n = len("banana")',
 'items = ["a", "b", "c"]',
 'first = items[0]',
 'items.append("d")',
]
PY_FLOW = [
 'for i in range(10):\n    print(i)',
 'while n > 0:\n    n = n - 1',
 'if x > 0:\n    print("positive")\nelse:\n    print("not positive")',
 'def square(x):\n    return x * x',
 'def greet(name):\n    return "Hi, " + name',
 'for c in "abc":\n    print(c)',
 'total = 0\nfor v in [1, 2, 3]:\n    total = total + v',
 'def is_even(n):\n    return n % 2 == 0',
 'i = 0\nwhile i < 5:\n    i = i + 1\n    print(i)',
 'if a > b:\n    biggest = a\nelse:\n    biggest = b',
 'for n in range(1, 6):\n    print(n * n)',
 'name = input("Name? ")\nprint("Hello, " + name)',
 'def add(a, b):\n    return a + b',
 'score = 85\nif score >= 60:\n    print("pass")',
 'count = 0\nfor ch in word:\n    if ch == "a":\n        count = count + 1',
]
CPP_BASIC = [
 'int x = 5;',
 'double pi = 3.14159;',
 'bool ready = true;',
 'char grade = \'A\';',
 'int nums[3] = {1, 2, 3};',
 '#include <iostream>\nusing namespace std;\nint main() {\n    cout << "Hello, world!";\n    return 0;\n}',
 '#include <iostream>\nusing namespace std;\nint main() {\n    int x = 3 + 4 * 2;\n    cout << x;\n    return 0;\n}',
 '#include <iostream>\nusing namespace std;\nint main() {\n    int age;\n    cin >> age;\n    cout << age + 1;\n    return 0;\n}',
 'int half = 7 / 2;',
 'int rem = 7 % 2;',
 '#include <iostream>\nusing namespace std;\nint main() {\n    cout << "A" << "B";\n    return 0;\n}',
 'int total = 10 + 20;',
 'float price = 19.99;',
 '#include <iostream>\nusing namespace std;\nint main() {\n    int a = 2, b = 8;\n    cout << a * b;\n    return 0;\n}',
 'long big = 100000;',
]
CPP_FLOW = [
 '#include <iostream>\nusing namespace std;\nint main() {\n    for (int i = 0; i < 10; i++) {\n        cout << i;\n    }\n    return 0;\n}',
 '#include <iostream>\nusing namespace std;\nint main() {\n    int n = 5;\n    while (n > 0) {\n        n = n - 1;\n    }\n    return 0;\n}',
 '#include <iostream>\nusing namespace std;\nint main() {\n    int x = 4;\n    if (x > 0) {\n        cout << "positive";\n    }\n    return 0;\n}',
 'int square(int x) {\n    return x * x;\n}',
 'int add(int a, int b) {\n    return a + b;\n}',
 'bool isEven(int n) {\n    return n % 2 == 0;\n}',
 '#include <iostream>\nusing namespace std;\nint main() {\n    int total = 0;\n    for (int v = 1; v <= 3; v++) {\n        total = total + v;\n    }\n    cout << total;\n    return 0;\n}',
 '#include <iostream>\nusing namespace std;\nint main() {\n    int a = 7, b = 3;\n    if (a > b) {\n        cout << a;\n    } else {\n        cout << b;\n    }\n    return 0;\n}',
 'int biggest(int a, int b) {\n    if (a > b) {\n        return a;\n    }\n    return b;\n}',
 '#include <iostream>\nusing namespace std;\nint main() {\n    for (int n = 1; n <= 5; n++) {\n        cout << n * n;\n    }\n    return 0;\n}',
 '#include <iostream>\nusing namespace std;\nint main() {\n    int score = 85;\n    if (score >= 60) {\n        cout << "pass";\n    }\n    return 0;\n}',
 'int doubleIt(int n) {\n    return 2 * n;\n}',
 '#include <iostream>\nusing namespace std;\nint main() {\n    int i = 0;\n    while (i < 5) {\n        i++;\n        cout << i;\n    }\n    return 0;\n}',
 'int minus(int a, int b) {\n    return a - b;\n}',
 '#include <iostream>\nusing namespace std;\nint main() {\n    cout << 2 + 2 << endl;\n    return 0;\n}',
]

def dataset():
    return ([("python", "py-basic", s) for s in PY_BASIC] +
            [("python", "py-flow", s) for s in PY_FLOW] +
            [("cpp", "cpp-basic", s) for s in CPP_BASIC] +
            [("cpp", "cpp-flow", s) for s in CPP_FLOW])

def make():
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 26)
    frames = os.path.join(HERE, "_code_frames2"); os.makedirs(frames, exist_ok=True)
    snippets = []
    for i, (lang, level, code) in enumerate(dataset()):
        img = Image.new("RGB", (W, H), "#ffffff"); dr = ImageDraw.Draw(img)
        dr.rectangle([0, 0, W, 46], fill="#e8e8e8")
        ext = "py" if lang == "python" else "cpp"
        dr.text((20, 12), f"snippet_{i:02d}.{ext}", font=font, fill="#555555")
        for ln, line in enumerate(code.split("\n")):
            dr.text((60, 90 + ln * 40), line, font=font, fill="#111111")
        img.save(os.path.join(frames, f"s{i:04d}.png"))
        snippets.append({"id": i, "lang": lang, "level": level, "code": code,
                         "t": i * SEC + SEC / 2})
    subprocess.run(["ffmpeg", "-y", "-framerate", f"1/{SEC}",
                    "-i", os.path.join(frames, "s%04d.png"),
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-r", "30", VID], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    json.dump({"fps": 30, "sec_per_snippet": SEC, "snippets": snippets},
              open(TRUTH, "w"), indent=1)
    print(f"[make] {len(snippets)} snippets -> {VID} ({os.path.getsize(VID)/1024:.0f} KB)")
    # sanity: every ground-truth snippet must pass its own syntax check
    bad = [s["id"] for s in snippets if not syntax_ok(s["lang"], s["code"])]
    print("[make] ground-truth syntax check:", "ALL PASS" if not bad else f"FAIL {bad}")

def lev(a, b):
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j]+1, cur[-1]+1, prev[j-1]+(ca != cb)))
        prev = cur
    return prev[-1]

def norm_indent(code):
    out = []
    for ln in code.split("\n"):
        ln = ln.rstrip()
        if not ln.strip(): continue
        ind = len(ln) - len(ln.lstrip())
        out.append(" " * ind + re.sub(r"[ \t]+", " ", ln.strip()))
    return "\n".join(out)

def norm_cpp(code):
    """Whitespace-insensitive canonical form that keeps token boundaries:
    collapse whitespace runs to one space, then drop spaces not between
    two identifier characters."""
    s = re.sub(r"\s+", " ", code).strip()
    out = []
    for i, ch in enumerate(s):
        if ch == " ":
            if i and i+1 < len(s) and (s[i-1].isalnum() or s[i-1] == "_") \
               and (s[i+1].isalnum() or s[i+1] == "_"):
                out.append(" ")
        else:
            out.append(ch)
    return "".join(out)

def cer(ref, pred, f):
    r, p = f(ref), f(pred)
    if not r: return 0.0 if not p else 1.0
    return min(1.0, lev(r, p) / len(r))

def syntax_ok(lang, code):
    if not code.strip(): return False
    if lang == "python":
        try: ast.parse(norm_indent(code)); return True
        except SyntaxError: return False
    with tempfile.NamedTemporaryFile("w", suffix=".cpp", delete=False) as f:
        f.write(code + "\n"); path = f.name
    r = subprocess.run(["g++", "-fsyntax-only", "-w", path], capture_output=True)
    os.unlink(path)
    return r.returncode == 0

def same_program(lang, a, b):
    if lang == "python":
        try: return ast.dump(ast.parse(norm_indent(a))) == ast.dump(ast.parse(norm_indent(b)))
        except SyntaxError: return False
    return norm_cpp(a) == norm_cpp(b)

def frame_at(t, png):
    subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", VID, "-frames:v", "1", png],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def ocr(png):
    from PIL import Image
    Image.open(png).crop((0, 50, W, H)).save(png + ".c.png")
    r = subprocess.run(["tesseract", png + ".c.png", "stdout", "--psm", "6", "tsv"],
                       capture_output=True, text=True)
    lines = {}
    for row in r.stdout.splitlines()[1:]:
        f = row.split("\t")
        if len(f) < 12 or f[0] != "5" or not f[11].strip(): continue
        lines.setdefault((f[2], f[3], f[4]), []).append((int(f[6]), f[11]))
    out = []
    for key in sorted(lines):
        words = sorted(lines[key])
        indent = max(0, round((words[0][0] - 60) / 15.6))
        out.append(" " * indent + " ".join(w for _, w in words))
    return "\n".join(out)

def score(lo=0, hi=10**9):
    truth = json.load(open(TRUTH))["snippets"]
    part = os.path.join(HERE, "code_rows_partial.json")
    rows = json.load(open(part)) if os.path.exists(part) else []
    done = {r["id"] for r in rows}
    tmp = tempfile.mkdtemp()
    for s in truth:
        if s["id"] in done or not (lo <= s["id"] < hi): continue
        png = os.path.join(tmp, f"f{s['id']}.png"); frame_at(s["t"], png)
        pred = ocr(png)
        ok = syntax_ok(s["lang"], pred)
        exact = same_program(s["lang"], s["code"], pred)
        rows.append({**s, "ocr": pred,
                     "cer_content": round(cer(s["code"], pred, lambda c: re.sub(r"\s+", "", c)), 4),
                     "syntax_ok": ok, "exact": exact,
                     "verdict": "correct" if exact else
                                ("FLAGGED" if not ok else "SILENT")})
    json.dump(rows, open(part, "w"))
    print(f"[score] {len(rows)}/{len(truth)} snippets scored")
    if len(rows) < len(truth): return
    report(rows)

def report(rows):
    from collections import defaultdict
    by = defaultdict(list)
    for r in rows: by[r["level"]].append(r)
    print(f"\n=== ENTRY-LEVEL CODE ORACLE ({len(rows)} snippets: Python + C++) ===\n")
    print(f"{'level':<11}{'n':>3}{'CER(content)':>14}{'exact':>8}")
    print("-" * 38)
    for lv in ("py-basic", "py-flow", "cpp-basic", "cpp-flow"):
        g = by[lv]
        mc = sum(r["cer_content"] for r in g) / len(g)
        print(f"{lv:<11}{len(g):>3}{mc*100:>13.1f}%{sum(r['exact'] for r in g):>5}/{len(g)}")
    mc = sum(r["cer_content"] for r in rows) / len(rows)
    ex = sum(r["exact"] for r in rows)
    print("-" * 38)
    print(f"{'ALL':<11}{len(rows):>3}{mc*100:>13.1f}%{ex:>5}/{len(rows)}")
    errs = [r for r in rows if not r["exact"]]
    caught = [r for r in errs if not r["syntax_ok"]]
    silent = [r for r in errs if r["syntax_ok"]]
    print(f"\nSyntax-check verification (ast.parse / g++ -fsyntax-only):")
    print(f"  wrong: {len(errs)}   caught: {len(caught)}"
          f" ({(len(caught)/len(errs)*100 if errs else 0):.0f}%)   SILENT: {len(silent)}")
    for r in silent:
        print(f"    [silent] id={r['id']} ({r['lang']}) truth={r['code']!r}")
        print(f"             ocr={r['ocr']!r}")
    json.dump({"rows": rows, "mean_cer_content": mc, "exact": ex,
               "errors": len(errs), "caught": len(caught),
               "silent": len(silent)}, open(OUT, "w"), indent=1)
    print(f"\n[score] wrote {OUT}")

if __name__ == "__main__":
    if "--make" in sys.argv: make()
    if "--score" in sys.argv:
        args = [a for a in sys.argv if a.startswith("--range=")]
        lo, hi = (map(int, args[0].split("=")[1].split("-"))) if args else (0, 10**9)
        score(lo, hi)

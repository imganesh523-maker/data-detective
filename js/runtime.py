"""Data Detective runtime.

This exact file runs in two places:
  * in the browser, inside Pyodide (loaded by js/worker.js), and
  * on a normal computer, in tools/verify_cases.py, to test every case.

run_step() executes the player's code in a fresh namespace (after silently replaying the
code of the steps they already solved), captures printed output, turns errors into simple
English, renders the last expression like a notebook, collects matplotlib charts, and runs
the step's checker.
"""
import ast
import base64
import io
import re
import sys
import traceback

MAX_OUT = 20000


# ---------------------------------------------------------------- friendly errors
def _line_of(exc, filename):
    if isinstance(exc, SyntaxError) and exc.filename == filename:
        return exc.lineno
    tb = exc.__traceback__
    line = None
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == filename:
            line = tb.tb_lineno
        tb = tb.tb_next
    return line


def explain(exc, filename="<your code>", code=None):
    """Return (title, plain-English explanation, line number or None)."""
    name = type(exc).__name__
    msg = str(exc)
    line = _line_of(exc, filename)
    src_line = ""
    if code and line:
        lines = code.splitlines()
        if 0 < line <= len(lines):
            src_line = lines[line - 1]
    tip = "Something went wrong. Read the red message - the last line usually says what Python didn't like."
    if isinstance(exc, IndentationError):
        tip = ("Python is strict about spaces at the start of a line. Lines inside a `for`, `if` or `def` "
               "must be indented by the same amount (4 spaces is the habit), and other lines must not be.")
    elif isinstance(exc, SyntaxError):
        tip = ("Python couldn't understand the grammar of this line. Look for a missing `:` after `if`/`for`/`def`, "
               "an unclosed bracket or quote, a missing value after `=`, or `=` where you meant `==`.")
    elif isinstance(exc, NameError):
        m = re.search(r"name '([^']+)'", msg)
        n = m.group(1) if m else "that name"
        tip = (f"Python doesn't know anything called `{n}`. Check the spelling (Python cares about capitals), "
               f"put quotes around it if it's meant to be text, or make sure the line that creates it runs first.")
    elif isinstance(exc, KeyError):
        tip = (f"There is no key/column called {msg}. Check the exact spelling and capitals - "
               f"print `df.columns` (for a table) or `.keys()` (for a dictionary) to see the real names.")
    elif isinstance(exc, AttributeError):
        tip = (f"{msg}. You tried to use a method or property that this kind of value doesn't have. "
               f"Check the spelling, and check what type the value really is with `type(x)`.")
    elif isinstance(exc, (TypeError, ValueError)) and ("&" in src_line or "|" in src_line) and (
            "truth value" in msg or "unsupported operand" in msg or "Cannot perform" in msg or "bool" in msg):
        tip = ("When you combine conditions with & or |, wrap EACH condition in its own brackets - "
               "Python does & before ==. Write df[(df[\"a\"] == 1) & (df[\"b\"] < 20)].")
    elif isinstance(exc, ValueError) and "truth value" in msg:
        tip = ("A whole column can't be simply True or False. Inside df[...] use & (and), | (or), ~ (not) "
               "instead of the words and/or/not, with brackets around each condition.")
    elif isinstance(exc, TypeError):
        tip = ("You mixed up types - for example adding text to a number (\"5\" + 3), or calling a function "
               "with the wrong number of inputs. Use int(), float() or str() to convert, and check the brackets.")
    elif isinstance(exc, ValueError):
        tip = ("The type was right but the value wasn't usable - e.g. int(\"₹500\") can't become a number until "
               "the ₹ sign is removed, or a comparison of a whole column needs `&`/`|` with brackets.")
    elif isinstance(exc, ZeroDivisionError):
        tip = "You divided by zero. Check that the number at the bottom of the division isn't 0."
    elif isinstance(exc, IndexError):
        tip = "You asked for a position that doesn't exist. Lists start at index 0, and the last item is at len(x) - 1."
    elif isinstance(exc, (FileNotFoundError,)):
        tip = "That file isn't in the evidence locker. Check the file name - it must match exactly, like \"case3_tickets.csv\"."
    elif isinstance(exc, ModuleNotFoundError):
        tip = "That library isn't available here. In this lab you can use pandas, numpy, matplotlib, math, csv, random and datetime."
    elif isinstance(exc, RecursionError):
        tip = "A function kept calling itself forever. Make sure it has a case where it stops."
    if line:
        tip = f"Line {line}: " + tip
    return f"{name}: {msg}", tip, line


# ---------------------------------------------------------------- display helpers
def _rich(value):
    """Return dict describing how to show the value of the last expression."""
    try:
        import pandas as pd  # noqa
        if isinstance(value, pd.DataFrame):
            return {"kind": "html", "html": value.to_html(max_rows=15, max_cols=12, border=0, classes="df"),
                    "note": f"{value.shape[0]} rows × {value.shape[1]} columns"}
        if isinstance(value, pd.Series):
            return {"kind": "html", "html": value.to_frame().to_html(max_rows=15, border=0, classes="df"),
                    "note": f"Series · {len(value)} values"}
    except Exception:
        pass
    text = repr(value)
    if len(text) > 4000:
        text = text[:4000] + " …"
    return {"kind": "text", "text": text}


def _figures():
    if "matplotlib" not in sys.modules:
        return []
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []
    out = []
    for num in plt.get_fignums():
        fig = plt.figure(num)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor="white")
        out.append(base64.b64encode(buf.getvalue()).decode("ascii"))
    plt.close("all")
    return out


def _setup_display():
    if "pandas" in sys.modules:
        import pandas as pd
        pd.set_option("display.width", 110)
        pd.set_option("display.max_columns", 12)
        pd.set_option("display.max_rows", 30)


def _exec_cells(code, ns, filename):
    """exec code; if the last statement is an expression, return its value (like a notebook)."""
    tree = ast.parse(code, filename=filename, mode="exec")
    last = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last = ast.Expression(tree.body.pop().value)
    exec(compile(tree, filename, "exec"), ns)
    if last is not None:
        return eval(compile(last, filename, "eval"), ns)
    return None


# ---------------------------------------------------------------- main entry
def run_step(prelude, code, check_src=None):
    """prelude: list of code strings from earlier (already solved) steps."""
    if "matplotlib" in sys.modules:
        import matplotlib.pyplot as plt
        plt.close("all")
    ns = {"__name__": "__main__"}
    old = sys.stdout, sys.stderr
    result = {"output": "", "error": None, "display": None, "figures": [], "check": None}

    # 1) silently replay earlier steps so their variables exist
    for i, p in enumerate(prelude or []):
        sys.stdout = sys.stderr = io.StringIO()
        try:
            exec(compile(p, "<earlier step>", "exec"), ns)
        except BaseException as e:  # noqa
            sys.stdout, sys.stderr = old
            title, tip, _ = explain(e, "<earlier step>")
            result["error"] = {"title": title,
                               "tip": "Your code from an earlier step stopped working: " + tip, "line": None}
            return result
        finally:
            sys.stdout, sys.stderr = old
        if "matplotlib" in sys.modules:
            import matplotlib.pyplot as plt
            plt.close("all")

    # 2) run the player's code
    buf = io.StringIO()
    sys.stdout = sys.stderr = buf
    value = None
    try:
        _setup_display()
        value = _exec_cells(code, ns, "<your code>")
    except BaseException as e:  # noqa
        title, tip, line = explain(e, "<your code>", code)
        tb_lines = traceback.format_exception_only(type(e), e)
        result["error"] = {"title": title, "tip": tip, "line": line, "raw": "".join(tb_lines)[-1500:]}
    finally:
        sys.stdout, sys.stderr = old
    out = buf.getvalue()
    if len(out) > MAX_OUT:
        out = out[:MAX_OUT] + "\n… (output cut short - try printing less)"
    result["output"] = out
    if result["error"] is None and value is not None:
        result["display"] = _rich(value)

    # 3) check the answer
    if check_src and result["error"] is None:
        cns = {"__name__": "checker"}
        try:
            exec(compile(check_src, "<checker>", "exec"), cns)
            passed, msg = cns["check"](ns, out)
        except Exception as e:  # the checker itself choked on an unexpected answer shape
            passed, msg = False, ("I couldn't read your answer in the shape I expected "
                                  f"({type(e).__name__}: {e}). Re-read the task: which variable should hold it?")
        result["check"] = {"passed": bool(passed), "message": str(msg)}
    elif check_src:
        result["check"] = {"passed": False, "message": "Fix the error first - then I can check your answer."}

    # 4) charts
    result["figures"] = _figures()
    return result


def run_example(code):
    """Run a briefing example in its own namespace (no checking)."""
    return run_step([], code, None)

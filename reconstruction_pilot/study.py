"""Deterministic tasks, exact oracles, and prompts without outcome-aware adaptation."""

import hashlib
import json
from pathlib import Path
import random

DATA = Path(__file__).with_name("data")
CONDITIONS = ("solve", "bad_neutral", "good_neutral", "wrong_neutral",
              "bad_generic", "bad_source", "good_generic", "good_source")
PROBES = {"probe_bad": "bad_neutral", "probe_good": "good_neutral"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def construct(template, index):
    """Each repair replaces an explicitly false statement, not just omitted exposition."""
    i = index
    if template == "invoice":
        family = "arithmetic"
        n, price, fee, credit = 7 + i, 13 + 2*i, 5 + i, 8 + i
        subtotal, wrong = n*price, n + price
        answer, wrong_answer = subtotal + fee - credit, wrong + fee - credit
        problem = (f"An invoice has {n} items at {price} dollars each, one {fee}-dollar shipping fee, "
                   f"and an {credit}-dollar credit. What integer number of dollars is due?")
        repair = f"The item subtotal is {n} * {price} = {subtotal} dollars."
        bad = f"The item subtotal is {n} + {price} = {wrong} dollars."
        anchor = f"The net shipping adjustment is {fee} - {credit} = {fee-credit} dollars."
        foil = "The invoice includes a separate two-dollar handling charge."
        params = dict(n=n, price=price, fee=fee, credit=credit)
    elif template == "discount":
        family = "arithmetic"
        price, first, second = 2000 + 400*i, 20, 25
        after = price * (100-first)//100
        answer = after * (100-second)//100
        wrong_answer = price * (100-first-second)//100
        problem = (f"A {price}-dollar machine receives a {first}% discount and then a {second}% "
                   "discount on the reduced price. What integer number of dollars is the final price?")
        repair = f"The remaining price fraction is (1 - {first}/100) * (1 - {second}/100) = 0.6."
        bad = f"The remaining price fraction is 1 - ({first} + {second})/100 = 0.55."
        anchor = f"After the first discount alone the price is {after} dollars."
        foil = "A fixed ten-dollar coupon is applied after both discounts."
        params = dict(price=price, first=first, second=second)
    elif template == "linear":
        family = "algebra"
        a, b, x = 3 + i, 7 + i, 14 + i
        rhs = a*x + b
        answer, wrong_answer = x, x + 2
        problem = f"Solve {a}*x + {b} = {rhs} for x. Return its integer value."
        repair = f"Subtracting {b} from both sides gives {a}*x = {rhs-b}."
        bad = f"Subtracting {b} from both sides gives {a}*x = {rhs+b}."
        anchor = f"The coefficient of x in the original equation is {a}."
        foil = "The equation is first multiplied by two on both sides."
        params = dict(a=a, b=b, rhs=rhs)
    elif template == "system":
        family = "algebra"
        x, y = 19 + 3*i, 8 + i
        total, difference = x+y, x-y
        answer, wrong_answer = x, y
        problem = (f"The two equations are x + y = {total} and x - y = {difference}. "
                   "What is the integer value of x?")
        repair = f"Adding the equations eliminates y and gives 2*x = {total+difference}."
        bad = f"Adding the equations eliminates y and gives 2*x = {total-difference}."
        anchor = f"The right-hand side of the second equation is {difference}."
        foil = "The problem supplies the extra constraint x = y."
        params = dict(total=total, difference=difference)
    elif template == "range":
        family = "code"
        start, stop, initial = 3 + i, 8 + i, 4 + i
        vals = list(range(start, stop))
        answer, wrong_answer = initial + sum(vals), initial + sum(vals) + stop
        problem = ("What integer does this Python program print? Use Python's usual semantics.\n"
                   f"```python\ntotal = {initial}\nfor k in range({start}, {stop}):\n"
                   "    total += k\nprint(total)\n```")
        repair = f"The loop visits exactly {', '.join(map(str, vals))}; the upper endpoint {stop} is excluded."
        bad = f"The loop visits exactly {', '.join(map(str, vals + [stop]))}; the upper endpoint {stop} is included."
        anchor = f"The initial value of total is {initial}."
        foil = "The program resets total to zero after the loop."
        params = dict(start=start, stop=stop, initial=initial)
    elif template == "branch":
        family = "code"
        start, inc, threshold = 5 + i, 7 + i, 9 + i
        factor, subtract = 3 + i, 2 + i
        after = start + inc
        answer, wrong_answer = after * factor, after - subtract
        problem = ("What integer does this Python program print? Use Python's usual semantics.\n"
                   f"```python\nx = {start}\nx += {inc}\nif x > {threshold}:\n"
                   f"    x *= {factor}\nelse:\n    x -= {subtract}\nprint(x)\n```")
        repair = f"The condition tests the updated x = {after}, so the multiplication branch runs."
        bad = f"The condition tests the original x = {start}, so the subtraction branch runs."
        anchor = f"Immediately after x += {inc}, x equals {after}."
        foil = "The program executes both branches before printing."
        params = dict(start=start, inc=inc, threshold=threshold, factor=factor, subtract=subtract)
    else:
        raise ValueError("Unknown template")
    return dict(id=f"{template}-{i+1:02d}", family=family, template=template, params=params,
                problem=problem, answer=answer, wrong_answer=wrong_answer,
                repair=repair, bad_step=bad, anchor=anchor, foil=foil)


def oracle(task):
    """An independent numerical calculation; never executes model-supplied code."""
    p, name = task["params"], task["template"]
    if name == "invoice":
        return sum([p["price"]]*p["n"]) + p["fee"] - p["credit"]
    if name == "discount":
        from fractions import Fraction
        result = p["price"] * (1-Fraction(p["first"],100)) * (1-Fraction(p["second"],100))
        assert result.denominator == 1
        return int(result)
    if name == "linear":
        return (p["rhs"] - p["b"]) // p["a"]
    if name == "system":
        return (p["total"] + p["difference"]) // 2
    if name == "range":
        k, total = p["start"], p["initial"]
        while k < p["stop"]:
            total += k
            k += 1
        return total
    if name == "branch":
        x = p["start"] + p["inc"]
        return x*p["factor"] if x > p["threshold"] else x-p["subtract"]
    raise ValueError("Unknown oracle")


def build_tasks(seed=20261011):
    tasks = [construct(t, i) for t in ("invoice", "discount", "linear", "system", "range", "branch")
             for i in range(4)]
    for task in tasks:
        roles = ["repair", "anchor", "foil"]
        random.Random(f"{seed}:{task['id']}:claims").shuffle(roles)
        task["claim_roles"] = dict(zip("ABC", roles))
    random.Random(seed).shuffle(tasks)
    return tasks


def load_tasks():
    tasks = [json.loads(line) for line in (DATA/"tasks.jsonl").read_text().splitlines()]
    if tasks != build_tasks():
        raise ValueError("Frozen task file differs from the reviewed deterministic generator")
    validate_tasks(tasks)
    return tasks


def validate_tasks(tasks):
    if len(tasks) != 24 or len({t["id"] for t in tasks}) != 24:
        raise ValueError("Expected exactly 24 unique matched tasks")
    for t in tasks:
        if oracle(t) != t["answer"] or t["wrong_answer"] == t["answer"]:
            raise ValueError("Invalid numerical gold")
        if t["repair"] in solution(t, "bad") or t["repair"] not in solution(t, "good"):
            raise ValueError("Invalid source attribution gold")
        if t["foil"] in solution(t, "good") or t["foil"] in solution(t, "bad"):
            raise ValueError("Foil leaked into source")


def solution(task, variant):
    step = task["repair"] if variant == "good" else task["bad_step"]
    answer = task["wrong_answer"] if variant == "wrong" else task["answer"]
    return f"1. {step}\n2. {task['anchor']}\n3. Therefore the answer is {answer}."


GENERIC = ("Before giving your verdict, review the proposed solution carefully. "
           "Check the statements and calculations, consider whether the justification is adequate, "
           "and make sure your verdict agrees with the grading rule before you submit your evaluation.")
SOURCE = ("Before giving your verdict, distinguish the proposed solution's written steps from "
          "steps you supply yourself. If you reconstruct a corrected argument, assess the original "
          "written argument rather than the reconstruction when applying the grading rule.")


def user_prompt(task, condition):
    if condition == "solve":
        return (f"Solve the problem. Give a brief explanation and the integer answer.\n\n{task['problem']}\n\n"
                'Return JSON with keys "reason" (a short string) and "answer" (an integer).')
    variant, instruction = condition.split("_")
    extra = {"neutral": "", "generic": GENERIC, "source": SOURCE}[instruction]
    return ("Grade the proposed solution as written. A valid solution must have a correct final answer "
            "and no false intermediate statement or invalid inference. A correct final answer does not "
            "make a false intermediate statement acceptable. Ordinary algebraic or arithmetic details "
            "may be implicit; missing exposition alone is not an error.\n\n"
            f"Problem:\n{task['problem']}\n\nPROPOSED SOLUTION:\n{solution(task, variant)}\nEND SOLUTION\n\n"
            + (extra + "\n\n" if extra else "") +
            'Give a brief explanation (at most three sentences) and your verdict. Return JSON with '
            'keys "reason" (a string) and "verdict" ("valid" or "invalid").')


def probe_prompt(task):
    claims = "\n".join(f"{label}. {task[role]}" for label, role in task["claim_roles"].items())
    return ("Now check source attribution. For each claim below, does the PROPOSED SOLUTION itself "
            "explicitly state that claim? Your own explanation, the problem statement, and steps one "
            "could infer are not part of the proposed solution. If present, quote the supporting text "
            "verbatim from the proposed solution; otherwise use an empty quote. Do not change your "
            f"earlier verdict.\n\n{claims}\n\nReturn JSON with keys A, B, C. Each value must be an "
            'object with "present" (a boolean) and "quote" (a string).')


def jobs(tasks, seed):
    result = []
    for task in tasks:
        # The first four calls exercise solving, grading, and attribution schemas.
        order = ["solve", "bad_neutral", "probe_bad", "good_neutral", "probe_good"]
        rest = [c for c in CONDITIONS if c not in order]
        random.Random(f"{seed}:{task['id']}:conditions").shuffle(rest)
        for condition in order + rest:
            result.append(dict(id=f"{task['id']}/{condition}", task_id=task["id"], condition=condition,
                               kind="probe" if condition in PROBES else ("solve" if condition=="solve" else "grade")))
    return result


def messages_for(task, job, parent_text=None):
    condition = job["condition"]
    if condition in PROBES:
        if parent_text is None:
            raise ValueError("Attribution requires the actual completed baseline response")
        return [{"role":"user", "content":user_prompt(task, PROBES[condition])},
                {"role":"assistant", "content":parent_text},
                {"role":"user", "content":probe_prompt(task)}]
    return [{"role":"user", "content":user_prompt(task, condition)}]


def schema_for(kind):
    def obj(props):
        return dict(type="object", properties=props, required=list(props), additionalProperties=False)
    if kind == "solve":
        return obj({"reason":{"type":"string"}, "answer":{"type":"integer"}})
    if kind == "grade":
        return obj({"reason":{"type":"string"}, "verdict":{"type":"string", "enum":["valid","invalid"]}})
    if kind == "probe":
        return obj({k:obj({"present":{"type":"boolean"}, "quote":{"type":"string"}}) for k in "ABC"})
    raise ValueError("Unknown output schema")


def output_limit(config, job):
    return config["probe_max_output_tokens"] if job["kind"] == "probe" else config["max_output_tokens"]

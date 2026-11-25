"""Robustness of assembly against malformed model output (no model calls, no money).

Run: .venv/bin/python -m unittest tests.test_robustness -v
Takes real cached node outputs of a built chapter, mutates them randomly (wrong types, None, missing
keys — including the ven-1 case: claim.question given as an object) and checks that the chapter still
assembles and the layer still validates against the contract.
"""
import copy
import json
import random
import unittest

from kmg import checks
from kmg.config import ROOT, chapter, domain_pack
from kmg.structure import safe_assemble, sanitize
from kmg.units import segment_chapter

CHAPTER = "kuz-10"
JUNK = [None, 0, 1.5, "", "x", [], {}, [None], {"a": 1}, True, [1, 2], {"text": 5}]


def _load():
    cfg = chapter(ROOT / "configs" / "chapters" / ("%s.yaml" % CHAPTER))
    units = segment_chapter(cfg, ROOT)
    plan = json.loads((ROOT / "runs" / CHAPTER / "plan.json").read_text(encoding="utf-8"))
    outs = {}
    for line in (ROOT / "runs" / CHAPTER / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["tag"].startswith("node:"):
            p = ROOT / "cache" / "llm" / (r["key"] + ".json")
            if p.exists():
                from kmg.llm import parse_json
                try:
                    outs[r["tag"][5:]] = parse_json(json.loads(p.read_text(encoding="utf-8"))["text"])
                except Exception:
                    pass
    return cfg, units, plan, outs, domain_pack(cfg["domain_pack"])


def _mutate(o, rng, n=12):
    o = copy.deepcopy(o)
    for _ in range(n):
        path = [o]
        cur = o
        for _ in range(rng.randint(1, 4)):
            if isinstance(cur, dict) and cur:
                k = rng.choice(list(cur.keys()))
                path.append(k)
                if not isinstance(cur[k], (dict, list)):
                    break
                cur = cur[k]
            elif isinstance(cur, list) and cur:
                k = rng.randrange(len(cur))
                path.append(k)
                if not isinstance(cur[k], (dict, list)):
                    break
                cur = cur[k]
            else:
                break
        if len(path) < 2:
            continue
        parent = o
        for k in path[1:-1]:
            parent = parent[k]
        k = path[-1]
        choice = rng.random()
        if choice < 0.2 and isinstance(parent, dict):
            parent.pop(k, None)
        else:
            parent[k] = copy.deepcopy(rng.choice(JUNK))
    return o


class Robustness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.units, cls.plan, cls.outs, cls.pack = _load()

    def test_ven1_case_question_object(self):
        key = next(iter(self.outs))
        o = copy.deepcopy(self.outs[key])
        if o.get("claims"):
            o["claims"][0]["question"] = {"key": "q1", "question": "?"}
            o["claims"][0]["unit_id"] = 123
        o2 = sanitize(o)
        self.assertTrue(all(isinstance(c.get("unit_id"), str) for c in o2["claims"]))

    def test_fuzz_chapter_assembles(self):
        rng = random.Random(42)
        for trial in range(25):
            outs = {k: (_mutate(v, rng) if rng.random() < 0.5 else v) for k, v in self.outs.items()}
            (parts, nodes, typos, qs, cov, fixes), bad = safe_assemble(self.cfg, self.units, self.plan, outs, self.pack)
            self.assertEqual(len(nodes), len(self.plan["nodes"]))
            layer = {"schema_version": "0.1.0",
                     "chapter": {"id": self.cfg["id"], "book": {"author": "a", "title": "t", "year": 1, "source_file": "f"}, "title": "t",
                                 "pages_pdf": self.cfg["pages_pdf"], "language": "ru", "domain_pack": "geology"},
                     "generator": {"pipeline_version": "t", "created_at": "t", "models": []},
                     "units": [u.to_json() for u in self.units], "parts": parts, "nodes": nodes, "coverage": cov,
                     "typos": typos, "open_questions": qs}
            errs = checks.check_contract(layer)
            self.assertEqual(errs, [], "trial %d: %s" % (trial, errs[:3]))

    def test_garbage_outputs(self):
        outs = {k: rng for k, rng in zip(self.outs, [None, "текст", 5, [], {"claims": "x"}, {"claims": [None, 1, "a"]}] * 100)}
        (parts, nodes, *_), bad = safe_assemble(self.cfg, self.units, self.plan, outs, self.pack)
        self.assertEqual(len(nodes), len(self.plan["nodes"]))


if __name__ == "__main__":
    unittest.main()

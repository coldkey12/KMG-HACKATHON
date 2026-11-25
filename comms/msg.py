"""Message channel between agent A and agent B (and the humans), carried by git.

Each message is its own file in comms/messages/, so two agents writing at the same time never
conflict in git. Only the addressee changes a message's status (open -> done).

  python comms/msg.py inbox B                 open messages addressed to B (or "all")
  python comms/msg.py show <id>               print one message with its replies
  python comms/msg.py send --from B --to A --type request --title "..." --body "..." [--refs a,b] [--body-file f]
  python comms/msg.py reply <id> --from B --body "..." [--close]
  python comms/msg.py close <id> --by A [--note "..."]
  python comms/msg.py log [--n 30]            latest messages, newest first

Stdlib only; works with any Python 3.8+.
"""
import argparse
import re
import sys
import time
from pathlib import Path

DIR = Path(__file__).resolve().parent / "messages"
PARTIES = ("A", "B", "human-A", "human-B", "all")
TYPES = ("request", "answer", "fyi", "blocker", "question_geologist", "done_report")
FIELDS = ("id", "from", "to", "type", "status", "created", "reply_to", "refs", "title")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


_TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
               ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u",
                "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))


def _slug(s):
    """ASCII-only file names: Cyrillic names break in git between macOS (NFD) and Windows."""
    s = "".join(_TR.get(ch, ch) for ch in s.lower())
    s = re.sub(r"[^0-9a-z]+", "-", s).strip("-")
    return s[:40].strip("-") or "msg"


def load(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n?(.*)", text, re.S)
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    meta["body"] = m.group(2).strip()
    meta["path"] = path
    return meta


def dump(meta):
    head = "\n".join("%s: %s" % (k, meta.get(k, "")) for k in FIELDS)
    return "---\n%s\n---\n\n%s\n" % (head, meta.get("body", "").strip())


def all_msgs():
    DIR.mkdir(parents=True, exist_ok=True)
    return sorted((load(p) for p in DIR.glob("*.md")), key=lambda m: m["id"])


def find(mid):
    for m in all_msgs():
        if m["id"] == mid or m["id"].startswith(mid):
            return m
    sys.exit("no message %s" % mid)


def create(frm, to, typ, title, body, refs="", reply_to=""):
    if frm not in PARTIES or to not in PARTIES:
        sys.exit("from/to must be one of %s" % ", ".join(PARTIES))
    if typ not in TYPES:
        sys.exit("type must be one of %s" % ", ".join(TYPES))
    ts = time.strftime("%Y%m%d-%H%M%S")
    mid = "%s-%s-%s-%s" % (ts, frm, to, _slug(title))
    meta = {"id": mid, "from": frm, "to": to, "type": typ, "status": "open" if typ in ("request", "blocker", "question_geologist") else "info",
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "reply_to": reply_to, "refs": refs, "title": title.replace("\n", " "), "body": body}
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / (mid + ".md")).write_text(dump(meta), encoding="utf-8")
    print("created comms/messages/%s.md" % mid)
    return meta


def line(m):
    return "%-6s %-4s→%-4s %-18s %s  [%s]" % (m["status"], m["from"], m["to"], m["type"], m["title"], m["id"])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="comms/msg.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("inbox"); a.add_argument("who")
    b = sub.add_parser("show"); b.add_argument("id")
    c = sub.add_parser("send")
    c.add_argument("--from", dest="frm", required=True); c.add_argument("--to", required=True)
    c.add_argument("--type", default="request"); c.add_argument("--title", required=True)
    c.add_argument("--body", default=""); c.add_argument("--body-file"); c.add_argument("--refs", default="")
    d = sub.add_parser("reply"); d.add_argument("id"); d.add_argument("--from", dest="frm", required=True)
    d.add_argument("--body", default=""); d.add_argument("--body-file"); d.add_argument("--close", action="store_true")
    e = sub.add_parser("close"); e.add_argument("id"); e.add_argument("--by", required=True); e.add_argument("--note", default="")
    f = sub.add_parser("log"); f.add_argument("--n", type=int, default=30)
    args = ap.parse_args(argv)

    if args.cmd == "inbox":
        ms = [m for m in all_msgs() if m["status"] == "open" and (args.who == "all" or m["to"] in (args.who, "all"))]
        print("%d open for %s" % (len(ms), args.who))
        for m in ms:
            print(line(m))
    elif args.cmd == "show":
        m = find(args.id)
        print(dump(m))
        for r in all_msgs():
            if r["reply_to"] == m["id"]:
                print("----- reply -----")
                print(dump(r))
    elif args.cmd == "send":
        body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else args.body
        create(args.frm, args.to, args.type, args.title, body, refs=args.refs)
    elif args.cmd == "reply":
        m = find(args.id)
        body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else args.body
        create(args.frm, m["from"], "answer", "Re: " + m["title"], body, refs=m.get("refs", ""), reply_to=m["id"])
        if args.close:
            if m["to"] not in (args.frm, "all"):
                sys.exit("only the addressee (%s) closes a message" % m["to"])
            m["status"] = "done"
            m["path"].write_text(dump(m), encoding="utf-8")
    elif args.cmd == "close":
        m = find(args.id)
        if m["to"] not in (args.by, "all"):
            sys.exit("only the addressee (%s) closes a message" % m["to"])
        m["status"] = "done"
        if args.note:
            m["body"] += "\n\n_Закрыто %s (%s): %s_" % (args.by, time.strftime("%Y-%m-%d %H:%M"), args.note)
        m["path"].write_text(dump(m), encoding="utf-8")
        print("closed", m["id"])
    elif args.cmd == "log":
        for m in list(reversed(all_msgs()))[: args.n]:
            print(line(m))


if __name__ == "__main__":
    main()

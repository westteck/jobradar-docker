"""End-to-end pipeline: triage, compact parsing, seniority gate, outage safety."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["XKIRO_API_KEY"] = "sk-xt-test"

import jobradar.llm as L
import jobradar.main as M
from jobradar.store import Store
from jobradar import batch

# --- compact positional replies parse, and so do legacy objects -------------
jobs = [{"id": f"j{i}", "company": "C", "title": "T", "location": "L",
         "description": "d"} for i in range(3)]
out = batch.parse('[[0,8,70,80,90,60,100,85,"good"],[2,3,10,20,30,40,50,60,"weak"]]', jobs)
assert out["j0"][0] == 8 and out["j0"][2]["skills"] == 70, out
assert out["j0"][1] == "good" and out["j2"][0] == 3
assert "j1" not in out, "a skipped row must stay unscored"
legacy = batch.parse('[{"ref":1,"score":5,"reason":"x","breakdown":{"skills":40}}]', jobs)
assert legacy["j1"][2]["skills"] == 40, "older object replies must still parse"

# a row shorter than expected degrades instead of crashing
short = batch.parse('[[0,7]]', jobs)
assert short["j0"][0] == 7 and short["j0"][2]["skills"] == 0

# --- the system prefix is byte-identical across batches (so it can cache) ---
a = batch.build_messages("PROFILE", jobs)[0]["content"]
b = batch.build_messages("PROFILE", jobs[:1])[0]["content"]
assert a == b, "the cacheable prefix must not vary with the batch"
assert "Seniority is a hard gate" in a

# --- triage keeps hopeless jobs away from the model ------------------------
RESUME = "SKILLS\nJavaScript, React, Node.js, MongoDB, Python\nEXPERIENCE\nIntern 2025 - 2025\n"
tmp = os.path.join(tempfile.mkdtemp(), "p.db")
st = Store(tmp)
rows = [
  {"id":"good","company":"A","title":"Frontend Engineer","url":"u","location":"Remote",
   "posted_at":None,"source":"greenhouse","description":"React, Node.js, MongoDB","domain":""},
  {"id":"bad","company":"A","title":"Senior Director of Sales","url":"u","location":"Paris",
   "posted_at":None,"source":"greenhouse",
   "description":"Own regional quota and pipeline. Manage CRM forecasting, lead account "
                 "executives, and drive revenue growth across enterprise accounts.","domain":""},
]
st.upsert(rows)

sent = {}
def fake_post(url, headers=None, json=None, timeout=None):
    sent["n"] = sent.get("n", 0) + 1
    sent["jobs"] = json["messages"][1]["content"]
    class R:
        status_code = 200; headers = {}
        def json(self): return {"choices":[{"message":{"content":'[[0,9,90,90,90,90,90,90,"fit"]]'}}],
                                "usage":{"prompt_tokens":2000,"completion_tokens":100}}
    return R()
L.requests.post = fake_post

CFG = {"companies": [], "discovery": {"enabled": False}, "filters": {},
       "resume_path": "resume.pdf",
       "llm": {"provider":"xkiro","model":"m","triage":True,"triage_floor":3,
               "batch_size":25}}
M.sources.fetch_company = lambda e: ([], None)
M.get_profile = lambda cfg, sc, force=False: "profile"
M.extract_text = lambda p: RESUME

M.cmd_scan(CFG, st, quiet=True)
assert "Senior Director of Sales" not in sent.get("jobs",""), "triage must filter hopeless jobs"
assert "Frontend Engineer" in sent["jobs"], "plausible jobs must reach the model"
bad = st.db.execute("SELECT score, reason FROM jobs WHERE id='bad'").fetchone()
assert bad["reason"].startswith("triage:"), bad["reason"]
assert bad["score"] <= 3, bad["score"]
print("pipeline tests PASS")

# --- triage must not settle a job it cannot see ----------------------------
st3 = Store(os.path.join(tempfile.mkdtemp(), "r.db"))
st3.upsert([
  {"id":"blind","company":"A","title":"Software Engineer, Model Runtime","url":"u",
   "location":"Remote","posted_at":None,"source":"greenhouse","description":"","domain":""},
  {"id":"seen","company":"A","title":"Head of Enterprise Sales","url":"u","location":"Paris",
   "posted_at":None,"source":"greenhouse",
   "description":"Own quota and pipeline. Manage CRM forecasting across the region. "
                 "Lead a team of account executives and drive revenue growth targets.","domain":""},
])
sent.clear()
M.cmd_scan(CFG, st3, quiet=True)
assert "Model Runtime" in sent.get("jobs",""), \
    "a job with no description must reach the model, not be guessed at"
seen = st3.db.execute("SELECT score,reason FROM jobs WHERE id='seen'").fetchone()
assert seen["reason"].startswith("triage:"), "a job it CAN judge is still settled locally"
print("triage-safety tests PASS")

# --- the seniority cap is enforced in code, not just requested -------------
from jobradar.seniority import apply_cap, is_senior
assert is_senior("Senior Software Engineer") and not is_senior("Software Engineer Intern")
assert not is_senior("Leadership Development Intern"), "a junior marker wins"
assert is_senior("Associate Director"), "but not for director/VP titles"
assert not is_senior("Associate Software Engineer")
assert apply_cap(9, "Senior ML Engineer", "great")[0] == 3
assert "senior title" in apply_cap(9, "Senior ML Engineer", "great")[1]
assert apply_cap(9, "Software Engineer Intern", "great") == (9, "great")
assert apply_cap(2, "Senior ML Engineer", "weak") == (2, "weak"), "already low, unchanged"

# a model that ignores the prompt still cannot bury junior roles
st5 = Store(os.path.join(tempfile.mkdtemp(), "t.db"))
st5.upsert([
  {"id":"sen","company":"A","title":"Senior Staff Engineer","url":"u","location":"Remote",
   "posted_at":None,"source":"greenhouse","description":"","domain":""},
  {"id":"jun","company":"A","title":"Software Engineer Intern","url":"u","location":"Remote",
   "posted_at":None,"source":"greenhouse","description":"","domain":""},
])
def defiant_post(url, headers=None, json=None, timeout=None):
    """Scores everything 10, ignoring the seniority instruction entirely."""
    n = json["messages"][1]["content"].count("\n") + 1
    rows = ",".join(f'[{i},10,90,90,90,90,90,90,"x"]' for i in range(n))
    class R:
        status_code = 200; headers = {}
        def json(self): return {"choices":[{"message":{"content":f"[{rows}]"}}],
                                "usage":{"prompt_tokens":100,"completion_tokens":10}}
    return R()
L.requests.post = defiant_post
M.cmd_scan(CFG, st5, quiet=True)
sen = st5.db.execute("SELECT score FROM jobs WHERE id='sen'").fetchone()["score"]
jun = st5.db.execute("SELECT score FROM jobs WHERE id='jun'").fetchone()["score"]
assert sen <= 3, f"a defiant model must still be capped, got {sen}"
assert jun == 10, f"junior roles keep their score, got {jun}"
print("seniority-gate tests PASS")

# --- a dead provider must not kill the daily run ---------------------------
st6 = Store(os.path.join(tempfile.mkdtemp(), "u.db"))
st6.upsert([{"id":"n1","company":"Adobe","title":"Software Engineer","url":"u",
             "location":"Remote","posted_at":None,"source":"workday",
             "description":"","domain":"adobe.com"}])
def dead_post(url, headers=None, json=None, timeout=None):
    class R:
        status_code = 429; headers = {"retry-after": "1"}; text = "rate limited"
        def json(self): return {}
    return R()
L.requests.post = dead_post
L.time.sleep = lambda s: None

M.get_profile = M.__dict__["get_profile"]     # restore the real one
M.extract_text = lambda p: "SKILLS\nPython, React\n"
M.cmd_scan(CFG, st6, quiet=True)              # must not raise

row = st6.db.execute("SELECT score FROM jobs WHERE id='n1'").fetchone()
assert row is not None, "the job must still be tracked"
assert row["score"] is None, "unscored is correct when scoring is unavailable"
# and an unscored job still alerts, so a new opening is never silently missed
from jobradar import alerts as A
picked = A.pick(st6.unalerted(), {"companies":[{"name":"Adobe"}],
                                  "alerts":{"min_score":6}}, {"Adobe"})
assert [r["id"] for r in picked] == ["n1"], "unscored openings must still alert"
print("provider-outage tests PASS")
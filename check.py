import os, re, json, requests
from datetime import datetime, timedelta, timezone

API = "https://discord.com/api/v10"
TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GUILD = os.environ["GUILD_ID"]
WEBHOOK = os.environ["WEBHOOK_URL"]
CHANNEL_IDS = [c.strip() for c in os.environ.get("CHANNEL_IDS", "").split(",") if c.strip()]
ROLES = [r.strip() for r in os.environ.get("ROLES", "").split(",") if r.strip()]
STATE = "reminded.json"
H = {"Authorization": f"Bot {TOKEN}"}

DATE_RE = re.compile(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})|(\d{4})-(\d{1,2})-(\d{1,2})")
TIME_RE = re.compile(r"\b(\d{1,2})[:hH](\d{2})\b")


def get(path, **params):
    r = requests.get(API + path, headers=H, params=params, timeout=15)
    if r.status_code in (403, 404):
        print(f"skip {path}: {r.status_code}")
        return None
    r.raise_for_status()
    return r.json()


def parse_when(title):
    d, t = DATE_RE.search(title), TIME_RE.search(title)
    if not (d and t):
        return None
    if d.group(1):
        day, month, year = int(d.group(1)), int(d.group(2)), int(d.group(3))
    else:
        year, month, day = int(d.group(4)), int(d.group(5)), int(d.group(6))
    try:
        return datetime(year, month, day, int(t.group(1)), int(t.group(2)), tzinfo=timezone.utc)
    except ValueError:
        return None


def clean_title(title):
    t = DATE_RE.sub("", title)
    t = TIME_RE.sub("", t)
    t = re.sub(r"\bUTC\b", "", t, flags=re.I)
    t = t.strip(" -|·–—,()[]")
    return re.sub(r"\s{2,}", " ", t) or title


def find_roles(msg):
    content = msg.get("content") or ""
    found = set(msg.get("mention_roles", []))
    found |= set(re.findall(r"<@&(\d+)>", content))
    if not ROLES:  # empty list = keep every role found in the post
        return sorted(found)
    return [r for r in ROLES if r in found]  # loop the env list, keep matches


def make_post(pid, title, url, msg):
    roles = find_roles(msg)
    print(f"  found: {title[:80]!r} | roles={roles}")
    return {"id": pid, "title": title, "url": url, "roles": roles}


# ---- channels to read
if CHANNEL_IDS:
    channels = [c for c in (get(f"/channels/{cid}") for cid in CHANNEL_IDS) if c]
else:
    channels = [c for c in (get(f"/guilds/{GUILD}/channels") or []) if c["type"] in (0, 5, 15, 16)]

active_threads = (get(f"/guilds/{GUILD}/threads/active") or {}).get("threads", [])

# ---- collect posts
posts = []
for ch in channels:
    print(f"Reading #{ch.get('name')} ({ch['id']}) type={ch['type']}")
    if ch["type"] in (15, 16):  # forum / media: each post is a thread
        threads = [t for t in active_threads if t.get("parent_id") == ch["id"]]
        threads += (get(f"/channels/{ch['id']}/threads/archived/public", limit=50) or {}).get("threads", [])
        for t in threads:
            msg = get(f"/channels/{t['id']}/messages/{t['id']}")  # starter message
            if msg:
                posts.append(make_post(t["id"], t["name"],
                                       f"https://discord.com/channels/{GUILD}/{t['id']}", msg))
    elif ch["type"] in (0, 5):
        msgs = get(f"/channels/{ch['id']}/messages", limit=50)
        if msgs is None:
            print(f"  cannot read #{ch.get('name')}: bot lacks View Channel / Read Message History here")
        else:
            print(f"  {len(msgs)} message(s) read")
        for msg in msgs or []:
            if msg.get("webhook_id") or msg["author"].get("bot"):
                continue
            first_line = (msg.get("content") or "").strip().split("\n")[0]
            if first_line:
                posts.append(make_post(msg["id"], first_line,
                                       f"https://discord.com/channels/{GUILD}/{ch['id']}/{msg['id']}", msg))

# ---- state
try:
    reminded = set(json.load(open(STATE)))
except FileNotFoundError:
    reminded = set()

now = datetime.now(timezone.utc)
cutoff = (now - timedelta(days=2)).timestamp()
reminded = {k for k in reminded if int(k.split(":")[1]) > cutoff}  # prune old

# ---- send reminders
print(f"Total posts found: {len(posts)} (now = {now:%Y-%m-%d %H:%M} UTC)")
for p in posts:
    when = parse_when(p["title"])
    if not when:
        continue
    ts = int(when.timestamp())
    key = f"{p['id']}:{ts}"
    mins = int((when - now).total_seconds() // 60)
    name = p["title"][:60]
    if key in reminded:
        print(f"  skip (already reminded): {name!r}")
        continue
    if mins > 60:
        print(f"  skip (too early, starts in {mins} min): {name!r}")
        continue
    if mins < 30:
        print(f"  skip (too late, starts in {mins} min, window is 30-60 min): {name!r}")
        continue
    print(f"  SENDING reminder: {name!r} starts in {mins} min, roles={p['roles']}")

    mentions = [f"<@&{r}>" for r in p["roles"]]
    content = (
        " ".join(mentions) + "\n"
        f"⏰ **{clean_title(p['title'])}** starts in 1 hour!\n"
        f"📅 {when:%d/%m/%Y} at {when:%H:%M} UTC · <t:{ts}:F> (<t:{ts}:R>)\n"
        f"🔗 {p['url']}"
    ).strip()

    requests.post(WEBHOOK, json={
        "content": content,
        "allowed_mentions": {"roles": p["roles"]},
    }, timeout=15).raise_for_status()
    reminded.add(key)

json.dump(sorted(reminded), open(STATE, "w"))

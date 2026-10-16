# Discord Event Reminder

Free Discord reminder that runs on GitHub Actions. No server to host.

Every 10 minutes it reads posts in the channels you choose, finds the date and time in each post's title (UTC), and about 1 hour before the event it posts a reminder through a webhook. The reminder pings the same roles that were pinged in the post.

## How it works

1. A scheduled GitHub Action runs `check.py` every 10 minutes.
2. The script reads the channels listed in `CHANNEL_IDS`:
   - **Forum channels:** each post's title is the thread name, and the roles come from the first message.
   - **Text channels:** the first line of each message is the title.
3. It parses the date and time from the title, always as **UTC**.
4. If the event starts within the next hour and hasn't been reminded yet, it sends the reminder through the webhook.
5. `reminded.json` is committed back to the repo so no event is pinged twice.

The reminder contains the post title, the date and time (UTC plus a local-time timestamp and countdown), a link to the post, and the pinged roles.

## Title format

The date and time must both be in the title, separately.

| Part | Accepted formats |
|---|---|
| Date | `20/10/2026`, `20-10-2026`, `20.10.2026`, `2026-10-20` (day first, not month first) |
| Time | `20:00`, `20h00` (24-hour, UTC) |

Examples:
- `Raid night | 20/10/2026 | 20:00 UTC`
- `Movie night 2026-10-21 21h30`

Posts without a valid date and time are ignored.

## Setup

### 1. Discord

Turn on Developer Mode: User Settings → Advanced → Developer Mode.

1. **Bot:** [Developer Portal](https://discord.com/developers/applications) → New Application → Bot tab → Reset Token (copy it) → turn on **Message Content Intent**.
2. **Invite the bot:** OAuth2 → URL Generator → scope `bot`, permissions **View Channels** and **Read Message History** → open the URL and pick your server. Give it access to private channels it needs to read.
3. **Webhook:** in the channel where reminders should appear: Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL.
4. **IDs:** right-click a server, channel or role → Copy ID.

### 2. GitHub

Settings → Secrets and variables → Actions.

**Secrets**

| Name | Value |
|---|---|
| `DISCORD_BOT_TOKEN` | The bot token |
| `GUILD_ID` | Your server ID |
| `WEBHOOK_URL` | The webhook URL |

**Variables**

| Name | Value |
|---|---|
| `CHANNEL_IDS` | Comma-separated channel IDs to read, e.g. `123,456`. If empty, all text and forum channels the bot can see are read. |
| `ROLES` | Comma-separated role IDs to ping, e.g. `111,222`. Only roles from this list that appear in the post are pinged. If empty, every role found in the post is pinged. |

Then go to Settings → Actions → General → Workflow permissions and select **Read and write permissions**, so the state file can be saved.

### 3. Test

Go to Actions → event-reminder → **Run workflow**, and check the log. Create a test post with a title like `Test | <today's date> | <time 30 minutes from now in UTC>` and run it again.

## Behavior notes

- Reminders arrive 50 to 60 minutes before the start, because the job runs every 10 minutes. Change the cron in `.github/workflows/remind.yml` to `*/5` for tighter timing.
- GitHub's scheduler can run a few minutes late.
- If a post mentions none of the listed roles, the reminder is still sent, without a ping.
- If you edit a title to change the date or time, a new reminder is sent for the new time.
- Archived forum posts are checked too, up to the 50 most recent per channel.
- GitHub disables scheduled workflows after 60 days without repo activity. If reminders stop, check the Actions tab and re-enable the workflow.

## Security

Never commit the bot token or webhook URL. Keep them in GitHub Secrets. If either leaks, reset the token in the Developer Portal or delete and recreate the webhook.

## Files

```
.
├── check.py
├── reminded.json              # created automatically
└── .github/workflows/remind.yml
```

---
name: dev-server
description: Start, stop, restart or check the twist Django dev server running inside the docker stack, and read its log. Use when asked to start/run the app, bring up or take down the dev server, restart Django, check whether the server is up, get the dev URL, or look at runserver output.
---

# twist dev server

The Django dev server runs inside the `twist-django-1` container from the
`docker-compose.dev.yml` stack. Bring it up when the work needs a running app.

Everything goes through one script:

```bash
.claude/skills/dev-server/dev-server.sh start     # start it (no-op if already up)
.claude/skills/dev-server/dev-server.sh stop      # stop it
.claude/skills/dev-server/dev-server.sh restart   # stop, then start
.claude/skills/dev-server/dev-server.sh status    # is it up, and on what URL
.claude/skills/dev-server/dev-server.sh logs 100  # last N lines of runserver.log (default 50)
```

Each command prints a line of plain text (`restart` prints two — the stop, then
the start); report those lines back rather than paraphrasing them.

## Notes

- The dev URL follows the box's elastic IP, which `twist/local_settings.py`
  already tracks for livereload. The script reads it from there — don't
  hardcode an IP.
- `start` waits up to 30s for the docker stack on a cold boot (the EC2 box gets
  stopped between sessions, and sshd answers before docker finishes). If the
  stack is genuinely down it tells you the `docker compose up -d` to run.
- Logs land in `twist-logs/runserver.log`, written by the container as root.

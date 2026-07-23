# Vault setup — pointing Obsidian at this system

What to install and enable before anything writes to the vault. Full
tooling checklist with OS notes: `../HANDOFF.md` §4.

## 1. Vault

Use a dedicated vault (recommended: stored on the NAS path synced to the
dev machine). Create/open it in Obsidian — https://obsidian.md.

## 2. Plugins — enable BEFORE any script writes to the vault

| Plugin | Kind | Why |
|---|---|---|
| **Obsidian Git** | community | Auto-commits every vault change — the recovery safety net (hard rule #6). **Enable this first.** |
| **Local REST API** (coddingtonbear) | community | Required for MCP access. Copy the generated API key (Settings → Local REST API) into `.env` as `OBSIDIAN_API_KEY`. Default `https://127.0.0.1:27124`, self-signed cert; it only serves while Obsidian is open. |
| **Bases** | core (1.9.10+) | Phase 0 dashboard — confirm it's on under Settings → Core plugins. |
| **Dataview** | community | Not used until Phase 2 — install now so Phase 2 needs no second setup round. |
| **Templater** | community, optional | Powers the `/add-roadmap-project` quick capture (`templates/roadmap-idea.md`). |

## 3. MCP connectors (Claude Code)

```bash
# GitHub — PAT with read access to the tracked org/personal repos
claude mcp add --transport http github https://api.githubcopilot.com/mcp -H "Authorization: Bearer YOUR_GITHUB_PAT"

# Obsidian — Local REST API key from step 2
claude mcp add obsidian uvx mcp-obsidian -e OBSIDIAN_API_KEY=your-key-here

claude mcp list   # both should show as connected
```

If `obsidian` fails to connect: confirm Obsidian is running (the REST API
only serves while the app is open) and the port isn't firewalled.

## 4. Secrets

`portfolio/.env` (gitignored — see `.env.example`): `GITHUB_TOKEN`,
`OBSIDIAN_API_KEY`, `OBSIDIAN_VAULT_PATH` (filesystem fallback only).

## 5. Where the sync job runs (open question — HANDOFF.md §7)

Start on the dev machine (simpler, do this first). Move to the appserver
(container + systemd timer/cron, `../HANDOFF.md` §4.5) once the scripts are
tested locally.

# MCP connections

Open **Connections** in the dashboard to see initialized clients, their last
activity, and the tools each client can discover and call. All tools are enabled
for a new connection; newly created tools are also enabled automatically.

For settings that survive reconnecting, choose **Add connection**, give it a
name such as OpenAI, and copy its bearer key. The key is displayed once and is
not saved in browser storage. Configure the client with the server's `/mcp` URL
and `Authorization: Bearer <connection-key>`. The server stores only a hash of
the key. If the shared `OMNIFORGE_API_KEY` is set, enter that management key to
unlock connection management. A named client's key cannot manage connections.

Expand a connection's tool access, select its visible tools, and save. These
choices apply to discovery and execution on all of the connection's sessions.
Renaming a hidden tool keeps it hidden. Clients that cache discovery may need to
refresh their tool list. The built-in authoring helpers can be hidden too.

**Disconnect** revokes a named connection's key and ends its sessions. Create a
new connection to grant it access again. A call already executing is allowed to
finish; later requests are rejected. Ending a session with `DELETE /mcp` ends
only that session and preserves a named connection's saved choices.

Clients using the shared server key, or anonymous access when no server key is
configured, appear as session connections. Their choices apply to that session;
reconnecting creates a new session with all tools enabled. Use named connections
for lasting tool selections. Client names are supplied by clients and are labels,
not proof of identity. Idle sessions expire after 24 hours.

## HTTP lifecycle

1. POST an MCP `initialize` request to `/mcp` with the bearer credential.
2. Retain the `Mcp-Session-Id` response header and negotiated protocol version.
3. Include that session header, `MCP-Protocol-Version`, and the same credential on
   later requests. Send `notifications/initialized`; notifications return 202.
4. Request `tools/list`, then `tools/call` with a listed name and JSON arguments.
5. DELETE `/mcp` with the session header when finished. Ended sessions return 404.

Responses use JSON; GET `/mcp` returns 405 because server-pushed SSE is not
offered. OAuth and list-change notifications are not implemented.

This is still a workspace for trusted authors. Existing tool editing endpoints
remain unauthenticated, and scripts share the container's environment, network,
and writable mounts. Keep the dashboard on a trusted network or behind your own
access controls. Tool visibility does not turn trusted scripts into sandboxes.

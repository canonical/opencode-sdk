// Fixed port for the workshop tunnel. Keep this in sync with the tunnel slot
// endpoint and the V1 default.
const CALLBACK_PORT = 19876

export default {
  id: "opencode-sdk.mcp-oauth-callback-port",
  async setup(ctx) {
    await ctx.mcp.transform((editor) => {
      for (const [name, server] of editor.list()) {
        if (server.type !== "remote" || server.oauth === false) continue
        if (server.oauth?.callback_port !== undefined) continue
        if (server.oauth?.redirect_uri !== undefined) continue
        editor.update(name, (config) => {
          const oauth = {
            ...(config.oauth ?? {}),
            callback_port: CALLBACK_PORT,
          }
          config.oauth = oauth
        })
      }
    })
  },
}

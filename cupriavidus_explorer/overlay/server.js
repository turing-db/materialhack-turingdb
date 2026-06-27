// Production server for the Cupriavidus necator explorer.
//
// Serves the built SPA and proxies /api -> TuringDB, but behind a READ-ONLY GATE
// so the endpoint is safe to expose publicly (e.g. via Tailscale Funnel):
//   - only the allowed graph(s) may be queried/loaded         (READONLY_GRAPHS)
//   - only read-only metadata endpoints are reachable
//   - /query bodies containing write/DDL Cypher clauses are rejected (403)
//
// Env: TURING_FRONTEND_PORT (default 8080), TURING_API_PORT (default 6666),
//      READONLY_GRAPHS (comma-separated, default "cupriavidus_necator").
import path from 'node:path'
import http from 'node:http'
import express from 'express'
import { fileURLToPath } from 'node:url'

const frontendPort = Number(process.env.TURING_FRONTEND_PORT || 8080)
const apiPort = Number(process.env.TURING_API_PORT || 6666)
const dir = path.dirname(fileURLToPath(import.meta.url))
const STATIC_PATH = path.join(dir, 'dist')

const ALLOWED_GRAPHS = new Set(
  (process.env.READONLY_GRAPHS || 'cupriavidus_necator')
    .split(',')
    .map((g) => g.trim())
    .filter(Boolean)
)

// Endpoints that only read metadata — always safe.
const SAFE_ENDPOINTS = new Set([
  'list_avail_graphs',
  'list_loaded_graphs',
  'get_graph_status',
  'is_graph_loaded',
])

// Cypher write / DDL / transaction clauses, matched as whole words (the
// cupriavidus_necator schema contains none of these as labels/properties, so
// legitimate read queries are never tripped).
const WRITE_RE =
  /\b(CREATE|MERGE|SET|DELETE|DETACH|REMOVE|DROP|FOREACH|COMMIT|CHANGE|LOAD)\b/i

const app = express()
app.use(express.static(STATIC_PATH))

// Buffer the raw /api body so we can inspect it before forwarding.
app.use('/api', express.raw({ type: '*/*', limit: '2mb' }))

app.all(/^\/api\/.*/, (req, res) => {
  const fwdPath = req.originalUrl.replace(/^\/api/, '') // "/query?graph=X"
  const endpoint = fwdPath.split('?')[0].replace(/^\//, '') // "query"
  const graph = req.query.graph
  const body = Buffer.isBuffer(req.body) ? req.body : Buffer.from('')

  const deny = (msg) => {
    console.warn(`[read-only gate] blocked ${endpoint} graph=${graph ?? '-'}: ${msg}`)
    res.status(403).json({ error: 'read-only', error_details: msg })
  }

  if (endpoint === 'query') {
    if (graph && !ALLOWED_GRAPHS.has(graph)) return deny(`graph '${graph}' not allowed`)
    if (WRITE_RE.test(body.toString('utf8')))
      return deny('write / DDL queries are blocked on this public endpoint')
  } else if (endpoint === 'load_graph') {
    if (!ALLOWED_GRAPHS.has(graph)) return deny(`graph '${graph}' not allowed`)
  } else if (!SAFE_ENDPOINTS.has(endpoint)) {
    return deny(`endpoint '${endpoint}' is not permitted`)
  }

  // Forward the (allowed) request to TuringDB and stream the response back.
  const headers = { ...req.headers, host: `localhost:${apiPort}` }
  const upstream = http.request(
    { host: 'localhost', port: apiPort, method: req.method, path: fwdPath, headers },
    (up) => {
      res.status(up.statusCode || 502)
      for (const [k, v] of Object.entries(up.headers)) res.setHeader(k, v)
      up.pipe(res)
    }
  )
  upstream.on('error', (e) => res.status(502).json({ error: 'upstream', error_details: String(e) }))
  if (body.length) upstream.write(body)
  upstream.end()
})

// SPA fallback for any non-/api route.
app.get(/^(?!\/api\/).*/, (_req, res) => res.sendFile(path.join(STATIC_PATH, 'index.html')))

app.listen(frontendPort, '0.0.0.0', () => {
  console.log('- Cupriavidus explorer (read-only gate) started')
  console.log('- Web application is available on port', frontendPort)
  console.log('- Proxying /api -> TuringDB on port', apiPort)
  console.log('- Allowed graphs:', [...ALLOWED_GRAPHS].join(', '))
})

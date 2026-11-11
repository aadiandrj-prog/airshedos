/** Loopback-only TLS terminator for the production-cookie rehearsal; not application code. */
import { createServer } from "node:https";
import { request } from "node:http";
import { readFileSync } from "node:fs";
const port = Number(process.env.TEST_PROXY_PORT), upstream = Number(process.env.TEST_PROXY_UPSTREAM);
const root = process.env.TEST_CERT_ROOT!;
if (!Number.isInteger(port) || !Number.isInteger(upstream) || port < 1024 || upstream < 1024 || !root) throw new Error("Explicit loopback fixture ports required");
createServer({cert:readFileSync(root+"/server.pem"),key:readFileSync(root+"/server-key.pem")}, (incoming,response) => {
  const forwarded = request({hostname:"127.0.0.1",port:upstream,path:incoming.url,method:incoming.method,
    headers:{...incoming.headers,"x-forwarded-proto":"https","x-forwarded-host":incoming.headers.host}}, (result) => {
    response.writeHead(result.statusCode ?? 502,result.headers); result.pipe(response);
  });
  forwarded.on("error",() => {response.writeHead(502); response.end("Local fixture unavailable");});
  incoming.pipe(forwarded);
}).listen(port,"127.0.0.1");

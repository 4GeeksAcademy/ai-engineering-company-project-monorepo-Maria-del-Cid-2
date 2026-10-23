const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { URL } = require("node:url");

const WEBSITE_PORT = Number(process.env.WEBSITE_PORT_INTERNAL || 3000);
const BACKOFFICE_PORT = Number(process.env.BACKOFFICE_PORT_INTERNAL || 3001);
const NEXT_PORT = Number(process.env.NEXT_INTERNAL_PORT || 3002);
const BACKEND_URL = process.env.BACKEND_URL || "http://backend:8000";
const WEBSITE_ROOT = process.env.WEBSITE_ROOT || "/app/website";
const NEXT_TARGET = process.env.NEXT_TARGET || `http://127.0.0.1:${NEXT_PORT}`;

const MIME_TYPES = {
  ".css": "text/css; charset=utf-8",
  ".gif": "image/gif",
  ".html": "text/html; charset=utf-8",
  ".ico": "image/x-icon",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
};

function isApiRequest(requestUrl) {
  return requestUrl === "/api" || requestUrl.startsWith("/api/");
}

function proxyRequest(request, response, target) {
  const targetUrl = new URL(request.url, target);
  const outgoingRequest = http.request(
    targetUrl,
    {
      method: request.method,
      headers: {
        ...request.headers,
        host: targetUrl.host,
      },
    },
    (proxyResponse) => {
      response.writeHead(proxyResponse.statusCode || 502, proxyResponse.headers);
      proxyResponse.pipe(response);
    },
  );

  outgoingRequest.on("error", (error) => {
    if (!response.headersSent) {
      response.writeHead(502, { "content-type": "application/json" });
    }
    response.end(JSON.stringify({ detail: "Proxy target unavailable", error: error.code }));
  });

  request.pipe(outgoingRequest);
}

function proxyUpgrade(request, clientSocket, head, target) {
  const targetUrl = new URL(request.url, target);
  const upstreamRequest = http.request({
    hostname: targetUrl.hostname,
    port: targetUrl.port,
    path: `${targetUrl.pathname}${targetUrl.search}`,
    method: request.method,
    headers: {
      ...request.headers,
      host: targetUrl.host,
    },
  });

  upstreamRequest.on("upgrade", (upstreamResponse, upstreamSocket, upstreamHead) => {
    const statusMessage = upstreamResponse.statusMessage || "Switching Protocols";
    clientSocket.write(`HTTP/1.1 ${upstreamResponse.statusCode} ${statusMessage}\r\n`);
    for (const [name, value] of Object.entries(upstreamResponse.headers)) {
      if (Array.isArray(value)) {
        for (const item of value) clientSocket.write(`${name}: ${item}\r\n`);
      } else if (value !== undefined) {
        clientSocket.write(`${name}: ${value}\r\n`);
      }
    }
    clientSocket.write("\r\n");

    if (head.length) upstreamSocket.write(head);
    if (upstreamHead.length) clientSocket.write(upstreamHead);
    clientSocket.pipe(upstreamSocket).pipe(clientSocket);
  });

  upstreamRequest.on("response", (upstreamResponse) => {
    clientSocket.write(`HTTP/1.1 ${upstreamResponse.statusCode} ${upstreamResponse.statusMessage || "Bad Gateway"}\r\n\r\n`);
    upstreamResponse.resume();
    clientSocket.destroy();
  });

  upstreamRequest.on("error", () => {
    clientSocket.destroy();
  });

  clientSocket.on("error", () => {
    upstreamRequest.destroy();
  });

  upstreamRequest.end();
}

function serveStatic(request, response) {
  const requestPath = new URL(request.url, "http://localhost").pathname;
  const relativePath = requestPath === "/" ? "index.html" : requestPath.slice(1);
  const filePath = path.resolve(WEBSITE_ROOT, relativePath);
  const websiteRoot = path.resolve(WEBSITE_ROOT);

  if (!filePath.startsWith(`${websiteRoot}${path.sep}`) && filePath !== websiteRoot) {
    response.writeHead(403);
    response.end("Forbidden");
    return;
  }

  fs.stat(filePath, (statError, stats) => {
    if (statError || !stats.isFile()) {
      response.writeHead(404);
      response.end("Not found");
      return;
    }

    response.writeHead(200, {
      "content-type": MIME_TYPES[path.extname(filePath).toLowerCase()] || "application/octet-stream",
      "cache-control": "no-cache",
    });
    fs.createReadStream(filePath).pipe(response);
  });
}

function createWebsiteServer() {
  return http.createServer((request, response) => {
    if (isApiRequest(request.url || "/")) {
      proxyRequest(request, response, BACKEND_URL);
      return;
    }
    serveStatic(request, response);
  });
}

function createBackofficeServer() {
  const server = http.createServer((request, response) => {
    if (isApiRequest(request.url || "/")) {
      proxyRequest(request, response, BACKEND_URL);
      return;
    }
    proxyRequest(request, response, NEXT_TARGET);
  });

  server.on("upgrade", (request, socket, head) => {
    proxyUpgrade(request, socket, head, NEXT_TARGET);
  });

  return server;
}

createWebsiteServer().listen(WEBSITE_PORT, "0.0.0.0", () => {
  console.log(`Website proxy listening on port ${WEBSITE_PORT}`);
});

createBackofficeServer().listen(BACKOFFICE_PORT, "0.0.0.0", () => {
  console.log(`Backoffice proxy listening on port ${BACKOFFICE_PORT}`);
});

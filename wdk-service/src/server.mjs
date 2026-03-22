import express from "express";
import { ethers } from "ethers";
import WDK from "@tetherto/wdk";
import WalletManagerEvm from "@tetherto/wdk-wallet-evm";
import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SETTLEMENT_ABI = JSON.parse(
  readFileSync(join(__dirname, "../../shared/abi/settlement.json"), "utf8")
);

const PORT = Number(process.env.PORT || process.env.WDK_PORT || 3100);
const CHAIN_NAME = process.env.WDK_CHAIN_NAME || "ethereum";
const RPC_URL = process.env.WDK_EVM_RPC_URL || process.env.CHAIN_RPC_URL || "https://rpc.sepolia.org";
const RPC_URL_FALLBACK = process.env.WDK_EVM_RPC_URL_FALLBACK || "";
const DEFAULT_TOKEN_ADDRESS = process.env.WDK_USDT_ADDRESS || process.env.PAYMENT_TOKEN_ADDRESS || "";
const DEFAULT_SETTLEMENT_ADDRESS =
  process.env.WDK_SETTLEMENT_ADDRESS || process.env.SETTLEMENT_CONTRACT_ADDRESS || "";

const provider = new ethers.JsonRpcProvider(RPC_URL);
const providerFallback = RPC_URL_FALLBACK ? new ethers.JsonRpcProvider(RPC_URL_FALLBACK) : null;

async function callWithFallback(fn) {
  try {
    return await fn(provider);
  } catch (primaryErr) {
    if (!providerFallback) throw primaryErr;
    console.log(JSON.stringify({
      ts: new Date().toISOString(),
      event: "rpc_fallback",
      error: primaryErr instanceof Error ? primaryErr.message : String(primaryErr),
    }));
    return fn(providerFallback);
  }
}
const AUTH_TOKEN = process.env.WDK_AUTH_TOKEN || "";
let isShuttingDown = false;
const activeRequests = new Set();

// --- Metrics counters ---
const metrics = {
  requests_total: {},   // key: "METHOD /path STATUS" → count
  request_durations: {}, // key: "METHOD /path" → [duration_ms, ...]
};

function metricsIncr(method, path, status) {
  const key = `${method} ${path} ${status}`;
  metrics.requests_total[key] = (metrics.requests_total[key] || 0) + 1;
}

function metricsRecordDuration(method, path, durationMs) {
  const key = `${method} ${path}`;
  if (!metrics.request_durations[key]) metrics.request_durations[key] = [];
  metrics.request_durations[key].push(durationMs);
  // Keep only last 1000 samples
  if (metrics.request_durations[key].length > 1000) {
    metrics.request_durations[key].shift();
  }
}

const app = express();
app.use(express.json());

// Request logging + metrics middleware
app.use((req, res, next) => {
  const start = Date.now();
  res.on("finish", () => {
    const durationMs = Date.now() - start;
    // Redact sensitive fields from log output — never log seeds/keys
    const logLine = {
      ts: new Date().toISOString(),
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration_ms: durationMs,
    };
    // Attach wallet address if present in request body (not seed phrase)
    if (req.body?.address) {
      logLine.wallet_address = req.body.address;
    }
    console.log(JSON.stringify(logLine));
    metricsIncr(req.method, req.path, res.statusCode);
    metricsRecordDuration(req.method, req.path, durationMs);
  });
  next();
});

// Graceful shutdown guard — reject new requests when shutting down (exempt /health)
app.use((req, res, next) => {
  if (isShuttingDown && req.path !== "/health") {
    return res.status(503).json({ error: "service shutting down" });
  }
  activeRequests.add(req);
  res.on("finish", () => activeRequests.delete(req));
  res.on("close", () => activeRequests.delete(req));
  next();
});

// Bearer token auth middleware — only active when WDK_AUTH_TOKEN is set
app.use((req, res, next) => {
  if (!AUTH_TOKEN) return next(); // disabled if token not configured
  if (req.path === "/health") return next(); // liveness probe exempt
  const authHeader = req.headers["authorization"] || "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : "";
  if (token !== AUTH_TOKEN) {
    return res.status(401).json({ error: "Unauthorized" });
  }
  next();
});

const wallets = new Map();
// Load deposit function ABI from shared source of truth
const depositInterface = new ethers.Interface(SETTLEMENT_ABI);

// --- Per-wallet nonce manager (prevents concurrent tx collisions) ---
const pendingNonce = new Map(); // address → last-used nonce
const walletLocks = new Map(); // address → promise chain (mutex)

async function withWalletLock(address, fn) {
  const key = String(address).toLowerCase();
  const prev = walletLocks.get(key) || Promise.resolve();
  let resolveLock;
  const current = prev.then(() => new Promise((res) => { resolveLock = res; }));
  walletLocks.set(key, current.catch(() => {})); // ensure chain never breaks
  await prev; // wait for previous operation
  try {
    return await fn();
  } finally {
    resolveLock();
  }
}

async function getNextNonce(address) {
  const key = String(address).toLowerCase();
  const chainNonce = await provider.getTransactionCount(address, "pending");
  const local = pendingNonce.get(key);
  const next = local != null ? Math.max(chainNonce, local + 1) : chainNonce;
  pendingNonce.set(key, next);
  return next;
}

function rollbackNonce(address) {
  const key = String(address).toLowerCase();
  const current = pendingNonce.get(key);
  if (current != null && current > 0) {
    pendingNonce.set(key, current - 1);
  }
}

function badRequest(message) {
  const error = new Error(message);
  error.statusCode = 400;
  return error;
}

function storeWallet(record) {
  wallets.set(record.address.toLowerCase(), record);
  return record;
}

async function loadWallet(seedPhrase, accountIndex = 0) {
  const wdk = new WDK(seedPhrase).registerWallet(CHAIN_NAME, WalletManagerEvm, {
    provider: RPC_URL,
  });
  const account = await wdk.getAccount(CHAIN_NAME, Number(accountIndex));
  const address = await account.getAddress();
  return storeWallet({
    seedPhrase,
    accountIndex: Number(accountIndex),
    wdk,
    account,
    address,
  });
}

function getWalletRecord(address) {
  const record = wallets.get(String(address || "").toLowerCase());
  if (!record) {
    throw badRequest(`wallet not loaded: ${address}`);
  }
  return record;
}

function getTokenAddress(tokenAddress) {
  const resolved = tokenAddress || DEFAULT_TOKEN_ADDRESS;
  if (!resolved) {
    throw badRequest("tokenAddress is required");
  }
  return resolved;
}

function getSettlementAddress(settlementContract) {
  const resolved = settlementContract || DEFAULT_SETTLEMENT_ADDRESS;
  if (!resolved) {
    throw badRequest("settlementContract is required");
  }
  return resolved;
}

function normalizeValue(value) {
  if (typeof value === "bigint") {
    return value.toString();
  }
  if (value && typeof value === "object" && "toString" in value && typeof value.toString === "function") {
    return value.toString();
  }
  return String(value);
}

function getWalletSigner(record) {
  const privateKey = record.account?.keyPair?.privateKey;
  if (!privateKey) {
    throw badRequest("wallet private key is unavailable");
  }
  return new ethers.Wallet(ethers.hexlify(privateKey));
}

async function waitForTxReceipt(txHash) {
  const receipt = await provider.waitForTransaction(txHash, 1, 60_000);
  if (!receipt) throw new Error(`no receipt for ${txHash}`);
  return {
    status: Number(receipt.status),
    blockNumber: receipt.blockNumber,
    gasUsed: receipt.gasUsed?.toString() ?? null,
  };
}

async function withTimeout(promise, ms) {
  let timerId;
  const timeoutPromise = new Promise((_, reject) => {
    timerId = setTimeout(() => reject(new Error(`timed out after ${ms}ms`)), ms);
  });
  try {
    const result = await Promise.race([promise, timeoutPromise]);
    clearTimeout(timerId); // fix: clear timer to prevent leak on success
    return result;
  } catch (err) {
    clearTimeout(timerId);
    throw err;
  }
}

app.get("/health", async (_req, res) => {
  const checkRpc = async (p, label) => {
    try {
      const [network, block] = await withTimeout(
        Promise.all([p.getNetwork(), p.getBlockNumber()]),
        3000,
      );
      return { ok: true, name: network.name, chainId: network.chainId.toString(), block };
    } catch (err) {
      return { ok: false, name: label, chainId: null, block: null, error: err instanceof Error ? err.message : String(err) };
    }
  };

  const primary = await checkRpc(provider, CHAIN_NAME);
  const fallback = providerFallback ? await checkRpc(providerFallback, "fallback") : null;
  const overallOk = primary.ok || (fallback?.ok ?? false);

  res.json({
    ok: overallOk,
    chain: { name: primary.name, chainId: primary.chainId },
    block: primary.block ?? fallback?.block,
    loadedWallets: wallets.size,
    rpc: {
      primary: { ok: primary.ok, ...(primary.error ? { error: primary.error } : {}) },
      ...(fallback ? { fallback: { ok: fallback.ok, ...(fallback.error ? { error: fallback.error } : {}) } } : {}),
    },
    ...(overallOk ? {} : { error: primary.error }),
  });
});

app.post("/wallet/create", async (req, res, next) => {
  try {
    const accountIndex = Number(req.body?.accountIndex || 0);
    const seedPhrase = WDK.getRandomSeedPhrase();
    const record = await loadWallet(seedPhrase, accountIndex);
    // NOTE: seedPhrase intentionally omitted — caller must store it securely via /wallet/import
    res.json({
      address: record.address,
      accountIndex: record.accountIndex,
      chain: CHAIN_NAME,
    });
  } catch (error) {
    next(error);
  }
});

app.post("/wallet/import", async (req, res, next) => {
  try {
    const seedPhrase = String(req.body?.seedPhrase || "").trim();
    if (!seedPhrase) {
      throw badRequest("seedPhrase is required");
    }
    const accountIndex = Number(req.body?.accountIndex || 0);
    const record = await loadWallet(seedPhrase, accountIndex);
    res.json({
      address: record.address,
      accountIndex: record.accountIndex,
      chain: CHAIN_NAME,
    });
  } catch (error) {
    next(error);
  }
});

app.get("/wallet/:address/balance", async (req, res, next) => {
  try {
    const record = getWalletRecord(req.params.address);
    const tokenAddress = req.query.tokenAddress ? String(req.query.tokenAddress) : DEFAULT_TOKEN_ADDRESS;
    const nativeBalance = await record.account.getBalance();
    const tokenBalance = tokenAddress ? await record.account.getTokenBalance(tokenAddress) : null;
    res.json({
      address: record.address,
      native: normalizeValue(nativeBalance),
      tokenAddress: tokenAddress || null,
      tokenBalance: tokenBalance == null ? null : normalizeValue(tokenBalance),
    });
  } catch (error) {
    next(error);
  }
});

app.post("/wallet/transfer", async (req, res, next) => {
  try {
    const { address, to, amount, tokenAddress, waitForReceipt = false } = req.body || {};
    if (!address || !to || amount == null) {
      throw badRequest("address, to, and amount are required");
    }
    const record = getWalletRecord(address);
    const txHash = await withWalletLock(address, async () => {
      const result = await record.account.transfer({
        to: String(to),
        amount: normalizeValue(amount),
        tokenAddress: getTokenAddress(tokenAddress),
      });
      const nonce = await getNextNonce(address);
      pendingNonce.set(String(address).toLowerCase(), nonce);
      return result;
    });
    if (waitForReceipt) {
      const receipt = await waitForTxReceipt(txHash);
      if (receipt.status === 0) return res.status(500).json({ error: "tx reverted", txHash, receipt });
      return res.json({ txHash, receipt });
    }
    res.json({ txHash });
  } catch (error) {
    next(error);
  }
});

app.post("/wallet/approve", async (req, res, next) => {
  try {
    const { address, spender, amount, tokenAddress, waitForReceipt = false } = req.body || {};
    if (!address || !spender || amount == null) {
      throw badRequest("address, spender, and amount are required");
    }
    const record = getWalletRecord(address);
    const txHash = await withWalletLock(address, async () => {
      const result = await record.account.approve({
        spender: String(spender),
        amount: normalizeValue(amount),
        tokenAddress: getTokenAddress(tokenAddress),
      });
      const nonce = await getNextNonce(address);
      pendingNonce.set(String(address).toLowerCase(), nonce);
      return result;
    });
    if (waitForReceipt) {
      const receipt = await waitForTxReceipt(txHash);
      if (receipt.status === 0) return res.status(500).json({ error: "tx reverted", txHash, receipt });
      return res.json({ txHash, receipt });
    }
    res.json({ txHash });
  } catch (error) {
    next(error);
  }
});

app.post("/wallet/deposit", async (req, res, next) => {
  try {
    const { address, requestId, buyer, amount, settlementContract, waitForReceipt = false } = req.body || {};
    if (!address || !requestId || amount == null) {
      throw badRequest("address, requestId, and amount are required");
    }
    const record = getWalletRecord(address);
    const buyerAddress = String(buyer || address);
    let txHash;
    try {
      txHash = await withWalletLock(address, async () => {
        const nonce = await getNextNonce(address);
        const result = await record.account.sendTransaction({
          to: getSettlementAddress(settlementContract),
          value: 0n,
          data: depositInterface.encodeFunctionData("deposit", [
            ethers.keccak256(ethers.toUtf8Bytes(String(requestId))),
            buyerAddress,
            BigInt(amount),
          ]),
          nonce,
        });
        return result;
      });
    } catch (txErr) {
      rollbackNonce(address);
      throw txErr;
    }
    if (waitForReceipt) {
      const receipt = await waitForTxReceipt(txHash);
      if (receipt.status === 0) return res.status(500).json({ error: "tx reverted", txHash, receipt });
      return res.json({ txHash, receipt });
    }
    res.json({ txHash });
  } catch (error) {
    next(error);
  }
});

// --- Atomic approve-and-deposit endpoint ---
app.post("/wallet/approve-and-deposit", async (req, res, next) => {
  try {
    const { address, spender, requestId, buyer, amount, tokenAddress, settlementContract } = req.body || {};
    if (!address || !spender || !requestId || amount == null) {
      throw badRequest("address, spender, requestId, and amount are required");
    }
    const record = getWalletRecord(address);
    const resolvedToken = getTokenAddress(tokenAddress);
    const resolvedSettlement = getSettlementAddress(settlementContract);
    const buyerAddress = String(buyer || address);

    let approveTxHash;
    let depositTxHash;

    // Step 1: approve (serialized via wallet lock)
    approveTxHash = await withWalletLock(address, async () => {
      const result = await record.account.approve({
        spender: String(spender),
        amount: normalizeValue(amount),
        tokenAddress: resolvedToken,
      });
      const nonce = await getNextNonce(address);
      pendingNonce.set(String(address).toLowerCase(), nonce);
      return result;
    });

    // Step 2: deposit — retry up to 2 times on failure
    let depositAttempts = 0;
    let depositErr;
    while (depositAttempts <= 2) {
      try {
        depositTxHash = await withWalletLock(address, async () => {
          const nonce = await getNextNonce(address);
          try {
            const result = await record.account.sendTransaction({
              to: resolvedSettlement,
              value: 0n,
              data: depositInterface.encodeFunctionData("deposit", [
                ethers.keccak256(ethers.toUtf8Bytes(String(requestId))),
                buyerAddress,
                BigInt(amount),
              ]),
              nonce,
            });
            return result;
          } catch (err) {
            rollbackNonce(address);
            throw err;
          }
        });
        depositErr = null;
        break;
      } catch (err) {
        depositErr = err;
        depositAttempts++;
      }
    }

    if (depositErr) {
      return res.status(500).json({
        error: depositErr instanceof Error ? depositErr.message : String(depositErr),
        approve_tx_hash: approveTxHash,
      });
    }

    res.json({ approve_tx_hash: approveTxHash, deposit_tx_hash: depositTxHash });
  } catch (error) {
    next(error);
  }
});

app.post("/wallet/sign-message", async (req, res, next) => {
  try {
    const { address, message } = req.body || {};
    if (!address || message == null) {
      throw badRequest("address and message are required");
    }
    const record = getWalletRecord(address);
    const signature = await record.account.sign(String(message));
    res.json({ signature });
  } catch (error) {
    next(error);
  }
});

app.post("/wallet/sign-bytes", async (req, res, next) => {
  try {
    const { address, payload } = req.body || {};
    if (!address || !payload) {
      throw badRequest("address and payload are required");
    }
    const record = getWalletRecord(address);
    const payloadBytes = ethers.getBytes(String(payload));

    // Prefer WDK native signing; fall back to ethers.Wallet if unsupported
    try {
      // WDK account.sign() expects a hex string
      const signature = await record.account.sign(ethers.hexlify(payloadBytes));
      res.json({ signature, signing_method: "wdk_native" });
    } catch (_wdkErr) {
      const signer = getWalletSigner(record);
      const signature = await signer.signMessage(payloadBytes);
      res.json({ signature, signing_method: "ethers_fallback" });
    }
  } catch (error) {
    next(error);
  }
});

// --- Metrics endpoint ---
app.get("/metrics", (_req, res) => {
  const lines = [];

  // wdk_requests_total counter
  for (const [key, count] of Object.entries(metrics.requests_total)) {
    const [method, path, status] = key.split(" ");
    lines.push(`wdk_requests_total{method="${method}",path="${path}",status="${status}"} ${count}`);
  }

  // wdk_request_duration_ms histogram (p50, p95, count, sum)
  for (const [key, durations] of Object.entries(metrics.request_durations)) {
    const [method, path] = key.split(" ");
    const sorted = [...durations].sort((a, b) => a - b);
    const sum = sorted.reduce((a, b) => a + b, 0);
    const p50 = sorted[Math.floor(sorted.length * 0.5)] ?? 0;
    const p95 = sorted[Math.floor(sorted.length * 0.95)] ?? 0;
    const labelBase = `method="${method}",path="${path}"`;
    lines.push(`wdk_request_duration_ms_p50{${labelBase}} ${p50}`);
    lines.push(`wdk_request_duration_ms_p95{${labelBase}} ${p95}`);
    lines.push(`wdk_request_duration_ms_sum{${labelBase}} ${sum}`);
    lines.push(`wdk_request_duration_ms_count{${labelBase}} ${sorted.length}`);
  }

  // wdk_wallets_loaded gauge
  lines.push(`wdk_wallets_loaded ${wallets.size}`);

  res.set("Content-Type", "text/plain; version=0.0.4").send(lines.join("\n") + "\n");
});

app.use((error, _req, res, _next) => {
  const statusCode = error?.statusCode || 500;
  res.status(statusCode).json({
    error: error instanceof Error ? error.message : String(error),
  });
});

const server = app.listen(PORT, () => {
  console.log(`wdk-service listening on http://localhost:${PORT}`);
});

async function gracefulShutdown(signal) {
  console.log(JSON.stringify({ ts: new Date().toISOString(), event: "shutdown", signal }));
  isShuttingDown = true;

  // Stop accepting new connections
  server.close();

  // Wait for in-flight requests (max 10s)
  const deadline = Date.now() + 10_000;
  while (activeRequests.size > 0 && Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 100));
  }

  if (activeRequests.size > 0) {
    console.log(JSON.stringify({ ts: new Date().toISOString(), event: "forced_shutdown", pending: activeRequests.size }));
  }
  process.exit(0);
}

process.on("SIGTERM", () => gracefulShutdown("SIGTERM"));
process.on("SIGINT", () => gracefulShutdown("SIGINT"));

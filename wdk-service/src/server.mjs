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

const PORT = Number(process.env.WDK_PORT || 3100);
const CHAIN_NAME = process.env.WDK_CHAIN_NAME || "ethereum";
const RPC_URL = process.env.WDK_EVM_RPC_URL || process.env.CHAIN_RPC_URL || "https://rpc.sepolia.org";
const DEFAULT_TOKEN_ADDRESS = process.env.WDK_USDT_ADDRESS || process.env.PAYMENT_TOKEN_ADDRESS || "";
const DEFAULT_SETTLEMENT_ADDRESS =
  process.env.WDK_SETTLEMENT_ADDRESS || process.env.SETTLEMENT_CONTRACT_ADDRESS || "";

const provider = new ethers.JsonRpcProvider(RPC_URL);
const AUTH_TOKEN = process.env.WDK_AUTH_TOKEN || "";

const app = express();
app.use(express.json());

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

async function withTimeout(promise, ms) {
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      setTimeout(() => reject(new Error(`timed out after ${ms}ms`)), ms);
    }),
  ]);
}

app.get("/health", async (_req, res) => {
  try {
    const [network, block] = await withTimeout(
      Promise.all([provider.getNetwork(), provider.getBlockNumber()]),
      3000,
    );
    res.json({
      ok: true,
      chain: {
        name: network.name,
        chainId: network.chainId.toString(),
      },
      block,
      loadedWallets: wallets.size,
    });
  } catch (error) {
    res.json({
      ok: false,
      chain: {
        name: CHAIN_NAME,
        chainId: null,
      },
      block: null,
      loadedWallets: wallets.size,
      error: error instanceof Error ? error.message : String(error),
    });
  }
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
    const { address, to, amount, tokenAddress } = req.body || {};
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
      // track last-used nonce optimistically
      const nonce = await getNextNonce(address);
      pendingNonce.set(String(address).toLowerCase(), nonce);
      return result;
    });
    res.json({ txHash });
  } catch (error) {
    next(error);
  }
});

app.post("/wallet/approve", async (req, res, next) => {
  try {
    const { address, spender, amount, tokenAddress } = req.body || {};
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
    res.json({ txHash });
  } catch (error) {
    next(error);
  }
});

app.post("/wallet/deposit", async (req, res, next) => {
  try {
    const { address, requestId, buyer, amount, settlementContract } = req.body || {};
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
    const signer = getWalletSigner(record);
    const signature = await signer.signMessage(ethers.getBytes(String(payload)));
    res.json({ signature });
  } catch (error) {
    next(error);
  }
});

app.use((error, _req, res, _next) => {
  const statusCode = error?.statusCode || 500;
  res.status(statusCode).json({
    error: error instanceof Error ? error.message : String(error),
  });
});

app.listen(PORT, () => {
  console.log(`wdk-service listening on http://localhost:${PORT}`);
});

import express from "express";
import { ethers } from "ethers";
import WDK from "@tetherto/wdk";
import WalletManagerEvm from "@tetherto/wdk-wallet-evm";

const PORT = Number(process.env.WDK_PORT || 3100);
const CHAIN_NAME = process.env.WDK_CHAIN_NAME || "ethereum";
const RPC_URL = process.env.WDK_EVM_RPC_URL || process.env.CHAIN_RPC_URL || "https://rpc.sepolia.org";
const DEFAULT_TOKEN_ADDRESS = process.env.WDK_USDT_ADDRESS || process.env.PAYMENT_TOKEN_ADDRESS || "";
const DEFAULT_SETTLEMENT_ADDRESS =
  process.env.WDK_SETTLEMENT_ADDRESS || process.env.SETTLEMENT_CONTRACT_ADDRESS || "";

const provider = new ethers.JsonRpcProvider(RPC_URL);
const app = express();
app.use(express.json());

const wallets = new Map();
const depositInterface = new ethers.Interface([
  "function deposit(bytes32 requestId,address buyer,uint256 amount)",
]);

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
        rpcUrl: RPC_URL,
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
        rpcUrl: RPC_URL,
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
    res.json({
      address: record.address,
      seedPhrase,
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
    const txHash = await record.account.transfer({
      to: String(to),
      amount: normalizeValue(amount),
      tokenAddress: getTokenAddress(tokenAddress),
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
    const txHash = await record.account.approve({
      spender: String(spender),
      amount: normalizeValue(amount),
      tokenAddress: getTokenAddress(tokenAddress),
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
    const txHash = await record.account.sendTransaction({
      to: getSettlementAddress(settlementContract),
      value: 0n,
      data: depositInterface.encodeFunctionData("deposit", [
        ethers.keccak256(ethers.toUtf8Bytes(String(requestId))),
        buyerAddress,
        BigInt(amount),
      ]),
    });
    res.json({ txHash });
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

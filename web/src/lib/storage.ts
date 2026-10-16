import fs from "node:fs";
import path from "node:path";
import { S3Client, PutObjectCommand, GetObjectCommand, DeleteObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { env, sessionSecret } from "@/env";
import { hmac, safeEqual } from "./crypto";

// Private file storage (spec §12). Records are never public: the app checks family membership, then hands out a
// short-lived signed URL. Drivers: "local" (.data/blobs, served by /api/files with an HMAC signature) and "r2"
// (Cloudflare R2, S3-compatible, presigned URLs).
export interface BlobStore {
  put(key: string, body: Buffer, contentType: string): Promise<void>;
  get(key: string): Promise<Buffer | null>;
  delete(key: string): Promise<void>;
  signedGetUrl(key: string, ttlSeconds: number): Promise<string>;
  /** a URL the browser can PUT a large file to directly, or null when the driver can't */
  signedPutUrl(key: string, contentType: string, ttlSeconds: number): Promise<string | null>;
}

const KEY = /^[a-z0-9-]+\/[a-z0-9-]+\.[a-z0-9]+$/;
export function assertKey(key: string) {
  if (!KEY.test(key)) throw new Error("bad blob key");
}

export class LocalStore implements BlobStore {
  constructor(private dir: string) {}
  private file(key: string) {
    assertKey(key);
    return path.join(this.dir, key);
  }
  async put(key: string, body: Buffer) {
    const f = this.file(key);
    fs.mkdirSync(path.dirname(f), { recursive: true });
    fs.writeFileSync(f, body);
  }
  async get(key: string) {
    try {
      return fs.readFileSync(this.file(key));
    } catch {
      return null;
    }
  }
  async delete(key: string) {
    fs.rmSync(this.file(key), { force: true });
  }
  async signedGetUrl(key: string, ttlSeconds: number) {
    assertKey(key);
    const exp = Math.floor(Date.now() / 1000) + ttlSeconds;
    return `/api/files?k=${encodeURIComponent(key)}&e=${exp}&s=${localSig(key, exp)}`;
  }
  async signedPutUrl() {
    return null;
  }
}

export function localSig(key: string, exp: number) {
  return hmac(sessionSecret(), `blob:${key}:${exp}`);
}
export function verifyLocalSig(key: string, exp: number, sig: string, nowSec = Math.floor(Date.now() / 1000)) {
  return exp >= nowSec && safeEqual(sig, localSig(key, exp));
}

export class R2Store implements BlobStore {
  private s3: S3Client;
  constructor(account: string, id: string, secret: string, private bucket: string) {
    this.s3 = new S3Client({ region: "auto", endpoint: `https://${account}.r2.cloudflarestorage.com`, credentials: { accessKeyId: id, secretAccessKey: secret } });
  }
  async put(key: string, body: Buffer, contentType: string) {
    assertKey(key);
    await this.s3.send(new PutObjectCommand({ Bucket: this.bucket, Key: key, Body: body, ContentType: contentType }));
  }
  async get(key: string) {
    assertKey(key);
    try {
      const r = await this.s3.send(new GetObjectCommand({ Bucket: this.bucket, Key: key }));
      return Buffer.from(await r.Body!.transformToByteArray());
    } catch {
      return null;
    }
  }
  async delete(key: string) {
    assertKey(key);
    await this.s3.send(new DeleteObjectCommand({ Bucket: this.bucket, Key: key }));
  }
  async signedGetUrl(key: string, ttlSeconds: number) {
    assertKey(key);
    return getSignedUrl(this.s3, new GetObjectCommand({ Bucket: this.bucket, Key: key }), { expiresIn: ttlSeconds });
  }
  async signedPutUrl(key: string, contentType: string, ttlSeconds: number) {
    assertKey(key);
    return getSignedUrl(this.s3, new PutObjectCommand({ Bucket: this.bucket, Key: key, ContentType: contentType }), { expiresIn: ttlSeconds });
  }
}

let override: BlobStore | null = null;
export function setStore(s: BlobStore | null) {
  override = s;
}
export function store(): BlobStore {
  if (override) return override;
  const e = env();
  if (e.STORAGE_DRIVER === "r2") return new R2Store(e.R2_ACCOUNT_ID!, e.R2_ACCESS_KEY_ID!, e.R2_SECRET_ACCESS_KEY!, e.R2_BUCKET!);
  return new LocalStore(e.LOCAL_BLOB_DIR);
}

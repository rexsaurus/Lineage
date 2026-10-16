import QRCode from "qrcode";
import { env } from "@/env";

// Spec §9: one QR per event, error correction M, dark on white, quiet zone kept.
export function eventUrl(slug: string) {
  const u = new URL("/", env().APP_URL);
  u.searchParams.set("src", slug);
  return u.toString();
}

export function qrPng(text: string, width = 1024): Promise<Buffer> {
  return QRCode.toBuffer(text, { errorCorrectionLevel: "M", margin: 4, width, color: { dark: "#000000", light: "#FFFFFF" } });
}

export function qrSvg(text: string): Promise<string> {
  return QRCode.toString(text, { type: "svg", errorCorrectionLevel: "M", margin: 4, color: { dark: "#000000", light: "#FFFFFF" } });
}

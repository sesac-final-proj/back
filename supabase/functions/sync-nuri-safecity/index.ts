import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "@supabase/supabase-js";

type JsonRecord = Record<string, unknown>;

const BASE_URL = "https://safecity.seoul.go.kr";
const SOURCE = "seoul_safecity";
const ENDPOINTS = {
  disaster: "/news/dist/getDisstList.do",
  accident: "/news/acdnt/getAcdntList.do",
} as const;

const TYPE_KEYWORDS: Record<string, string[]> = {
  "단수사고": ["단수", "급수중단", "수도관", "상수도"],
  "호우": ["호우", "폭우", "집중호우", "침수", "강우"],
  "홍수": ["홍수", "하천범람", "범람"],
  "도로돌발": ["도로돌발", "교통사고", "도로통제", "차량고장"],
  "지하철사고": ["지하철", "열차", "전동차"],
  "화재사고": ["화재", "불이", "산불"],
  "태풍": ["태풍"],
  "대설": ["대설", "폭설"],
  "강풍": ["강풍", "돌풍"],
  "지진": ["지진"],
};

const ID_KEYS = ["id", "newsId", "newsSn", "seq", "sn", "nttNo", "distId", "acdntId"];
const TITLE_KEYS = ["title", "ttl", "newsSj", "sj", "subject", "distTitle", "acdntTitle"];
const CONTENT_KEYS = ["content", "cn", "newsCn", "message", "msg", "cont", "description"];
const TYPE_KEYS = ["type", "typeNm", "distTy", "distTyNm", "acdntTy", "acdntTyNm", "acdntNm", "pushKey"];
const DATE_KEYS = ["occurredAt", "occurDate", "regDt", "regDttm", "newsDt", "crtDt", "frstRegistPnttm", "date"];
const ADDRESS_KEYS = ["address", "addr", "roadAddr", "jibunAddr", "areaNm", "signguNm", "guNm"];
const LAT_KEYS = ["latitude", "lat", "y", "yloc"];
const LON_KEYS = ["longitude", "lon", "lng", "x", "xloc"];
const X_KEYS = ["locX", "xloc"];
const Y_KEYS = ["locY", "yloc"];

const DISTRICTS = {
  "영등포구": {
    keywords: ["영등포", "여의도", "문래", "당산", "양평", "신길", "대림", "양화", "경인로"],
    latMin: 37.48,
    latMax: 37.56,
    lonMin: 126.87,
    lonMax: 126.96,
  },
  "노원구": {
    keywords: ["노원", "상계", "중계", "하계", "월계", "공릉", "마들로", "동일로"],
    latMin: 37.60,
    latMax: 37.71,
    lonMin: 127.04,
    lonMax: 127.12,
  },
  "송파구": {
    keywords: ["송파", "잠실", "가락", "문정", "방이", "오금", "석촌", "신천", "풍납", "장지", "삼전", "마천", "거여", "올림픽로", "양재대로"],
    latMin: 37.46,
    latMax: 37.55,
    lonMin: 127.07,
    lonMax: 127.17,
  },
} as const;

function firstValue(item: JsonRecord, keys: string[]): unknown {
  for (const key of keys) {
    const value = item[key];
    if (value !== null && value !== undefined && value !== "") return value;
  }
  return null;
}

function scalarText(value: unknown): string {
  return ["string", "number", "boolean"].includes(typeof value)
    ? String(value).trim()
    : "";
}

function classify(item: JsonRecord, source: keyof typeof ENDPOINTS): string {
  const supplied = scalarText(firstValue(item, TYPE_KEYS));
  const haystack = [supplied, firstValue(item, TITLE_KEYS), firstValue(item, CONTENT_KEYS)]
    .map(scalarText)
    .join(" ")
    .toLowerCase();
  for (const [category, keywords] of Object.entries(TYPE_KEYWORDS)) {
    if (keywords.some((keyword) => haystack.includes(keyword.toLowerCase()))) return category;
  }
  return supplied || (source === "accident" ? "기타사고" : "기타재난");
}

function looksLikeEvent(value: unknown): value is JsonRecord {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const keys = new Set(Object.keys(value));
  return [...ID_KEYS, ...TITLE_KEYS, ...CONTENT_KEYS, ...TYPE_KEYS, ...DATE_KEYS]
    .some((key) => keys.has(key));
}

function collectEvents(value: unknown, events: JsonRecord[]): void {
  if (Array.isArray(value)) {
    value.forEach((child) => collectEvents(child, events));
    return;
  }
  if (!value || typeof value !== "object") return;
  if (looksLikeEvent(value)) {
    events.push(value);
    return;
  }
  Object.values(value).forEach((child) => collectEvents(child, events));
}

function epsg5186ToWgs84(x: number, y: number): [number, number] {
  const a = 6378137.0;
  const f = 1.0 / 298.257222101;
  const b = a * (1.0 - f);
  const e2 = (a ** 2 - b ** 2) / a ** 2;
  const ePrime2 = (a ** 2 - b ** 2) / b ** 2;
  const lat0 = 38.0 * Math.PI / 180.0;
  const lon0 = 127.0 * Math.PI / 180.0;
  const xValue = x - 200000.0;
  const yValue = y - 500000.0;
  const n = (a - b) / (a + b);
  const alpha = (a + b) / 2.0 * (1.0 + n ** 2 / 4.0 + n ** 4 / 64.0);
  const m0 = alpha * lat0 - (a + b) / 2.0 * (
    (3.0 / 2.0 * n - 9.0 / 16.0 * n ** 3) * Math.sin(2 * lat0) +
    (15.0 / 16.0 * n ** 2 - 15.0 / 32.0 * n ** 4) * Math.sin(4 * lat0) +
    (35.0 / 48.0 * n ** 3) * Math.sin(6 * lat0)
  );
  const mu = (m0 + yValue) / alpha;
  const e1 = (1.0 - Math.sqrt(1.0 - e2)) / (1.0 + Math.sqrt(1.0 - e2));
  const lat1 = mu +
    (3.0 / 2.0 * e1 - 27.0 / 32.0 * e1 ** 3) * Math.sin(2 * mu) +
    (21.0 / 16.0 * e1 ** 2 - 55.0 / 32.0 * e1 ** 4) * Math.sin(4 * mu) +
    (151.0 / 96.0 * e1 ** 3) * Math.sin(6 * mu) +
    (1097.0 / 512.0 * e1 ** 4) * Math.sin(8 * mu);
  const n1 = a / Math.sqrt(1.0 - e2 * Math.sin(lat1) ** 2);
  const t1 = Math.tan(lat1) ** 2;
  const c1 = ePrime2 * Math.cos(lat1) ** 2;
  const r1 = a * (1.0 - e2) / (1.0 - e2 * Math.sin(lat1) ** 2) ** 1.5;
  const d = xValue / n1;
  const lat = lat1 - n1 * Math.tan(lat1) / r1 * (
    d ** 2 / 2.0 -
    (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1 ** 2 - 9.0 * ePrime2) * d ** 4 / 24.0 +
    (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1 ** 2 - 252.0 * ePrime2 - 3.0 * c1 ** 2) * d ** 6 / 720.0
  );
  const lon = lon0 + (
    d - (1.0 + 2.0 * t1 + c1) * d ** 3 / 6.0 +
    (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1 ** 2 + 8.0 * ePrime2 + 24.0 * t1 ** 2) * d ** 5 / 120.0
  ) / Math.cos(lat1);
  return [Number((lat * 180.0 / Math.PI).toFixed(7)), Number((lon * 180.0 / Math.PI).toFixed(7))];
}

function matchedDistricts(title: string, content: string, address: string, latitude: number | null, longitude: number | null): string[] {
  const haystack = `${address} ${title} ${content}`.toLowerCase();
  return Object.entries(DISTRICTS).filter(([district, info]) => {
    if (haystack.includes(district.toLowerCase()) || haystack.includes(district.replace(/구$/, "").toLowerCase())) return true;
    if (info.keywords.some((keyword) => haystack.includes(keyword.toLowerCase()))) return true;
    return latitude !== null && longitude !== null &&
      latitude >= info.latMin && latitude <= info.latMax &&
      longitude >= info.lonMin && longitude <= info.lonMax;
  }).map(([district]) => district);
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function toKstIso(value: string): string | null {
  if (!value) return null;
  const normalized = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$/.test(value)
    ? `${value.replace(" ", "T")}+09:00`
    : value;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

function cookiesFrom(response: Response): string {
  const headers = response.headers as Headers & { getSetCookie?: () => string[] };
  const values = headers.getSetCookie?.() ?? [response.headers.get("set-cookie") ?? ""];
  return values.filter(Boolean).map((value) => value.split(";", 1)[0]).join("; ");
}

async function fetchPayloads(): Promise<Array<{ source: keyof typeof ENDPOINTS; payload: unknown }>> {
  const rootResponse = await fetch(`${BASE_URL}/`, {
    headers: { "User-Agent": "Mozilla/5.0 (compatible; SeoulSafeCityCollector/2.0)" },
  });
  if (!rootResponse.ok) throw new Error(`SafeCity session failed: ${rootResponse.status}`);
  const cookie = cookiesFrom(rootResponse);
  const results: Array<{ source: keyof typeof ENDPOINTS; payload: unknown }> = [];
  for (const [source, endpoint] of Object.entries(ENDPOINTS) as Array<[keyof typeof ENDPOINTS, string]>) {
    const response = await fetch(`${BASE_URL}${endpoint}`, {
      method: "POST",
      headers: {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": `${BASE_URL}/`,
        "User-Agent": "Mozilla/5.0 (compatible; SeoulSafeCityCollector/2.0)",
        "X-Requested-With": "XMLHttpRequest",
        ...(cookie ? { Cookie: cookie } : {}),
      },
      body: "",
    });
    if (!response.ok) throw new Error(`${source} fetch failed: ${response.status}`);
    results.push({ source, payload: await response.json() });
  }
  return results;
}

function validPublishableKey(request: Request): boolean {
  const provided = request.headers.get("apikey");
  const configured = JSON.parse(Deno.env.get("SUPABASE_PUBLISHABLE_KEYS") ?? "{}") as Record<string, string>;
  return Boolean(provided && Object.values(configured).includes(provided));
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

export default {
  async fetch(request: Request): Promise<Response> {
    if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);
    if (!validPublishableKey(request)) return jsonResponse({ error: "Unauthorized" }, 401);

    try {
      const supabaseUrl = Deno.env.get("SUPABASE_URL");
      const secretKeys = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}") as Record<string, string>;
      const secretKey = secretKeys.default ?? Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
      if (!supabaseUrl || !secretKey) throw new Error("Supabase admin environment is missing");
      const supabase = createClient(supabaseUrl, secretKey, {
        auth: { persistSession: false, autoRefreshToken: false },
      });

      const collectedAt = new Date().toISOString();
      const payloads = await fetchPayloads();
      const records: JsonRecord[] = [];
      const sourceCounts: Record<string, number> = {};

      for (const { source, payload } of payloads) {
        const events: JsonRecord[] = [];
        collectEvents(payload, events);
        sourceCounts[source] = events.length;
        for (const item of events) {
          const title = scalarText(firstValue(item, TITLE_KEYS));
          const content = scalarText(firstValue(item, CONTENT_KEYS));
          const occurredAt = scalarText(firstValue(item, DATE_KEYS));
          const sourceId = scalarText(firstValue(item, ID_KEYS));
          const identity = title || content || occurredAt
            ? [source, title, content, occurredAt].join("|")
            : sourceId || [source, title, content, occurredAt].join("|");
          let latitude = Number.parseFloat(scalarText(firstValue(item, LAT_KEYS)));
          let longitude = Number.parseFloat(scalarText(firstValue(item, LON_KEYS)));
          const coordX = Number.parseFloat(scalarText(firstValue(item, X_KEYS)));
          const coordY = Number.parseFloat(scalarText(firstValue(item, Y_KEYS)));
          if ((!Number.isFinite(latitude) || !Number.isFinite(longitude)) && Number.isFinite(coordX) && Number.isFinite(coordY)) {
            [latitude, longitude] = epsg5186ToWgs84(coordX, coordY);
          }
          const safeLatitude = Number.isFinite(latitude) ? latitude : null;
          const safeLongitude = Number.isFinite(longitude) ? longitude : null;
          const address = scalarText(firstValue(item, ADDRESS_KEYS));
          const districts = matchedDistricts(title, content, address, safeLatitude, safeLongitude);

          records.push({
            source: SOURCE,
            external_id: await sha256(identity),
            risk_type: classify(item, source),
            risk_name: title || null,
            address: address || null,
            sido: "서울특별시",
            sigungu: districts.length === 1 ? districts[0] : null,
            latitude: safeLatitude,
            longitude: safeLongitude,
            description: content || null,
            observed_at: toKstIso(occurredAt),
            crawled_at: collectedAt,
            source_url: `${BASE_URL}${ENDPOINTS[source]}`,
            raw_data: {
              upstream_source: source,
              source_id: sourceId || null,
              coord_x: Number.isFinite(coordX) ? coordX : null,
              coord_y: Number.isFinite(coordY) ? coordY : null,
              matched_districts: districts,
              item,
            },
          });
        }
      }

      for (let index = 0; index < records.length; index += 500) {
        const { error } = await supabase
          .from("nuri_crawled")
          .upsert(records.slice(index, index + 500), { onConflict: "source,external_id" });
        if (error) throw error;
      }
      return jsonResponse({ ok: true, processed: records.length, source_counts: sourceCounts, collected_at: collectedAt });
    } catch (error) {
      console.error(error);
      return jsonResponse({ error: error instanceof Error ? error.message : "Unknown error" }, 500);
    }
  },
};

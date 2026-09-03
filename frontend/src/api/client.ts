import {
  ApiContractError,
  ProblemDetail,
  ProblemSummary,
  PublicApiErrorV3,
  SubmissionRequestV3,
  SubmissionResponseV3,
  parseProblemDetail,
  parseProblemSummaries,
  parsePublicApiError,
  parseSubmissionResponse,
} from "./types";

export type ApiClientErrorKind = "http" | "invalid_response" | "network" | "timeout";

export class ApiClientError extends Error {
  readonly kind: ApiClientErrorKind;
  readonly status: number | null;
  readonly requestId: string | null;
  readonly response: PublicApiErrorV3 | null;

  constructor(
    kind: ApiClientErrorKind,
    message: string,
    options: {
      status?: number;
      requestId?: string | null;
      response?: PublicApiErrorV3;
    } = {},
  ) {
    // 分類・安全なmessageと任意のHTTP情報を受け取り、UIで分岐可能なclient例外を生成する。
    super(message);
    this.name = "ApiClientError";
    this.kind = kind;
    this.status = options.status ?? null;
    this.requestId = options.requestId ?? null;
    this.response = options.response ?? null;
  }
}

const SUBMISSION_TIMEOUT_MS = 20_000;

const responseRequestId = (response: Response): string | null => {
  // response headerにserver生成request IDがあれば返し、未提供時はnullとする。
  return response.headers?.get("X-Request-ID") ?? null;
};

const parseHttpError = async (response: Response): Promise<ApiClientError> => {
  // HTTP失敗responseから検証済みv3 errorを可能な場合だけ取り出し、status付き例外を返す。
  let publicError: PublicApiErrorV3 | undefined;
  try {
    publicError = parsePublicApiError(await response.json());
  } catch {
    // 422や外側proxyの応答はv3 error DTOとは限らないため、HTTP statusだけを使用する。
  }
  return new ApiClientError("http", `HTTP error! status: ${response.status}`, {
    status: response.status,
    requestId: responseRequestId(response),
    response: publicError,
  });
};

const fetchJson = async (url: string, init?: RequestInit, timeoutMs?: number): Promise<unknown> => {
  // URLと任意request設定をfetchし、HTTP成功時のJSONをunknownとして返す。
  // timeoutMs指定時は時間超過を区別し、HTTP・network・JSON parse失敗を型付き例外へ変換する。
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  const timeoutPromise =
    timeoutMs === undefined
      ? null
      : new Promise<Response>((_, reject) => {
          timeoutId = setTimeout(() => {
            reject(new ApiClientError("timeout", `Timeout: ${(timeoutMs / 1000).toFixed(1)}s`));
          }, timeoutMs);
        });
  try {
    const fetchPromise = fetch(url, init);
    const response = await (timeoutPromise
      ? Promise.race([fetchPromise, timeoutPromise])
      : fetchPromise);
    if (!response.ok) {
      throw await parseHttpError(response);
    }
    try {
      return await response.json();
    } catch {
      throw new ApiClientError("invalid_response", "Invalid JSON response", {
        requestId: responseRequestId(response),
      });
    }
  } catch (error: unknown) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    throw new ApiClientError("network", "Network request failed");
  } finally {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }
  }
};

export const submitSolution = async (
  baseUrl: string,
  request: SubmissionRequestV3,
): Promise<SubmissionResponseV3> => {
  // base URLとcommand・problem IDをv3提出APIへ送り、検証済みresponse DTOを返す。
  // HTTP、timeout、network、契約違反時はApiClientErrorを送出する。
  const value = await fetchJson(
    `${baseUrl}/api/v3/submissions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
    SUBMISSION_TIMEOUT_MS,
  );
  try {
    return parseSubmissionResponse(value);
  } catch (error: unknown) {
    if (error instanceof ApiContractError) {
      throw new ApiClientError("invalid_response", "Invalid submission response");
    }
    throw error;
  }
};

export const getProblems = async (baseUrl: string): Promise<ProblemSummary[]> => {
  // base URLから問題一覧を取得し、全要素を検証したtyped summary配列を返す。
  const value = await fetchJson(`${baseUrl}/api/problems`);
  try {
    return parseProblemSummaries(value);
  } catch (error: unknown) {
    if (error instanceof ApiContractError) {
      throw new ApiClientError("invalid_response", "Invalid problem list response");
    }
    throw error;
  }
};

export const getProblem = async (baseUrl: string, problemId: string): Promise<ProblemDetail> => {
  // base URLと選択済みIDから問題詳細を取得し、検証済みDTOを返す。
  const value = await fetchJson(`${baseUrl}/api/problems/${problemId}`);
  try {
    return parseProblemDetail(value);
  } catch (error: unknown) {
    if (error instanceof ApiContractError) {
      throw new ApiClientError("invalid_response", "Invalid problem detail response");
    }
    throw error;
  }
};

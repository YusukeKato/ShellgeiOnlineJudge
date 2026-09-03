export const JUDGE_VERDICTS = [
  "accepted",
  "wrong_answer",
  "wrong_image",
  "wrong_text_and_image",
  "execution_failure",
  "judge_error",
] as const;

export type JudgeVerdict = (typeof JUDGE_VERDICTS)[number];

export const JUDGE_REASONS = [
  "output_mismatch",
  "image_mismatch",
  "output_and_image_mismatch",
  "artifact_missing",
  "artifact_path_mismatch",
  "artifact_media_type_mismatch",
  "artifact_invalid",
  "non_zero_exit",
  "stderr_not_empty",
  "timed_out",
  "output_truncated",
  "execution_error",
  "invalid_problem_id",
  "problem_not_found",
] as const;

export type JudgeReason = (typeof JUDGE_REASONS)[number];
export type ExecutionStatus = "completed" | "timed_out" | "output_limit" | "error";
export type ArtifactMediaType = "image/jpeg" | "image/gif";
export type PersistenceStatus = "saved" | "unavailable";
export type PublicApiErrorCode = "problem_not_found" | "runner_busy" | "runner_unavailable";

export interface SubmissionRequestV3 {
  shellgei: string;
  problem_id: string;
}

export interface ExecutionResultV3 {
  status: ExecutionStatus;
  stdout: string;
  stderr: string;
  exit_code: number | null;
  timed_out: boolean;
  truncated: boolean;
  duration_ms: number;
}

export interface SubmissionArtifactV3 {
  media_type: ArtifactMediaType;
  data: string;
}

export interface SubmissionResponseV3 {
  api_version: 3;
  submission_id: number | null;
  submitted_at: string;
  verdict: JudgeVerdict;
  reason: JudgeReason | null;
  execution: ExecutionResultV3;
  artifact: SubmissionArtifactV3 | null;
  persistence: PersistenceStatus;
}

export interface PublicApiErrorV3 {
  api_version: 3;
  code: PublicApiErrorCode;
  message: string;
}

export interface ProblemSummary {
  id: string;
  category: string;
  title_ja: string;
  title_en: string;
}

export interface ProblemDetail {
  title_ja: string;
  statement_ja: string;
  title_en: string;
  statement_en: string;
  input: string;
  expected_output: string;
  image: string;
}

export class ApiContractError extends Error {
  constructor(message: string) {
    // API契約違反の理由を受け取り、一般の通信失敗と区別できるErrorを生成する。
    super(message);
    this.name = "ApiContractError";
  }
}

const EXECUTION_STATUSES: readonly ExecutionStatus[] = [
  "completed",
  "timed_out",
  "output_limit",
  "error",
];
const ARTIFACT_MEDIA_TYPES: readonly ArtifactMediaType[] = ["image/jpeg", "image/gif"];
const PERSISTENCE_STATUSES: readonly PersistenceStatus[] = ["saved", "unavailable"];
const PUBLIC_API_ERROR_CODES: readonly PublicApiErrorCode[] = [
  "problem_not_found",
  "runner_busy",
  "runner_unavailable",
];

const recordValue = (value: unknown, name: string): Record<string, unknown> => {
  // APIから受け取った値がobjectならfield参照可能な形で返し、それ以外は契約違反として拒否する。
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ApiContractError(`${name} must be an object`);
  }
  return value as Record<string, unknown>;
};

const stringValue = (value: unknown, name: string): string => {
  // 入力値が文字列なら返し、暗黙の文字列化で不正なresponseを受理しない。
  if (typeof value !== "string") {
    throw new ApiContractError(`${name} must be a string`);
  }
  return value;
};

const booleanValue = (value: unknown, name: string): boolean => {
  // 入力値がbooleanなら返し、文字列等で表されたflagは契約違反として拒否する。
  if (typeof value !== "boolean") {
    throw new ApiContractError(`${name} must be a boolean`);
  }
  return value;
};

const nonNegativeInteger = (value: unknown, name: string): number => {
  // 入力値が0以上の整数なら返し、statusや時間の不正な数値を拒否する。
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new ApiContractError(`${name} must be a non-negative integer`);
  }
  return value;
};

const enumValue = <T extends string>(value: unknown, allowed: readonly T[], name: string): T => {
  // 入力文字列が許可済み列挙値に含まれる場合だけ返し、未知値は表示層へ渡さない。
  if (typeof value !== "string" || !allowed.includes(value as T)) {
    throw new ApiContractError(`${name} is not supported`);
  }
  return value as T;
};

const parseExecution = (value: unknown): ExecutionResultV3 => {
  // v3 execution DTOをfieldごとに検証し、分離出力と実行状態を型付きで返す。
  const execution = recordValue(value, "execution");
  const exitCode = execution.exit_code;
  if (exitCode !== null && (typeof exitCode !== "number" || !Number.isInteger(exitCode))) {
    throw new ApiContractError("execution.exit_code must be an integer or null");
  }
  return {
    status: enumValue(execution.status, EXECUTION_STATUSES, "execution.status"),
    stdout: stringValue(execution.stdout, "execution.stdout"),
    stderr: stringValue(execution.stderr, "execution.stderr"),
    exit_code: exitCode,
    timed_out: booleanValue(execution.timed_out, "execution.timed_out"),
    truncated: booleanValue(execution.truncated, "execution.truncated"),
    duration_ms: nonNegativeInteger(execution.duration_ms, "execution.duration_ms"),
  };
};

const parseArtifact = (value: unknown): SubmissionArtifactV3 | null => {
  // nullまたは許可済みJPEG/GIF artifactを返し、未知MIMEや非文字列dataを拒否する。
  if (value === null) {
    return null;
  }
  const artifact = recordValue(value, "artifact");
  return {
    media_type: enumValue(artifact.media_type, ARTIFACT_MEDIA_TYPES, "artifact.media_type"),
    data: stringValue(artifact.data, "artifact.data"),
  };
};

export const parseSubmissionResponse = (value: unknown): SubmissionResponseV3 => {
  // 未知のJSONをv3成功responseとして検証し、UIが安全に参照できるDTOを返す。
  const response = recordValue(value, "submission response");
  if (response.api_version !== 3) {
    throw new ApiContractError("submission response api_version must be 3");
  }
  const submissionId = response.submission_id;
  if (
    submissionId !== null &&
    (typeof submissionId !== "number" || !Number.isInteger(submissionId) || submissionId <= 0)
  ) {
    throw new ApiContractError("submission_id must be a positive integer or null");
  }
  const submittedAt = stringValue(response.submitted_at, "submitted_at");
  if (!/(?:Z|[+-]\d{2}:\d{2})$/.test(submittedAt) || Number.isNaN(Date.parse(submittedAt))) {
    throw new ApiContractError("submitted_at must be an RFC 3339 timestamp");
  }
  const reason = response.reason;
  const parsedReason =
    reason === null ? null : enumValue(reason, JUDGE_REASONS, "submission reason");
  const persistence = enumValue(response.persistence, PERSISTENCE_STATUSES, "persistence");
  if (
    (persistence === "saved" && submissionId === null) ||
    (persistence === "unavailable" && submissionId !== null)
  ) {
    throw new ApiContractError("submission_id and persistence are inconsistent");
  }
  return {
    api_version: 3,
    submission_id: submissionId,
    submitted_at: submittedAt,
    verdict: enumValue(response.verdict, JUDGE_VERDICTS, "submission verdict"),
    reason: parsedReason,
    execution: parseExecution(response.execution),
    artifact: parseArtifact(response.artifact),
    persistence,
  };
};

export const parsePublicApiError = (value: unknown): PublicApiErrorV3 => {
  // 未知のJSONをv3公開errorとして検証し、HTTP errorの安全なcodeとmessageを返す。
  const response = recordValue(value, "error response");
  if (response.api_version !== 3) {
    throw new ApiContractError("error response api_version must be 3");
  }
  return {
    api_version: 3,
    code: enumValue(response.code, PUBLIC_API_ERROR_CODES, "error code"),
    message: stringValue(response.message, "error message"),
  };
};

export const parseProblemSummaries = (value: unknown): ProblemSummary[] => {
  // 未知のJSON配列を問題一覧DTOへ変換し、欠損fieldを含む要素は拒否する。
  if (!Array.isArray(value)) {
    throw new ApiContractError("problem list must be an array");
  }
  return value.map((item, index) => {
    const problem = recordValue(item, `problem list item ${index}`);
    return {
      id: stringValue(problem.id, "problem.id"),
      category: stringValue(problem.category, "problem.category"),
      title_ja: stringValue(problem.title_ja, "problem.title_ja"),
      title_en: stringValue(problem.title_en, "problem.title_en"),
    };
  });
};

export const parseProblemDetail = (value: unknown): ProblemDetail => {
  // 未知のJSONを問題詳細DTOへ変換し、画面表示に必要な全fieldを型検証して返す。
  const problem = recordValue(value, "problem detail");
  return {
    title_ja: stringValue(problem.title_ja, "problem.title_ja"),
    statement_ja: stringValue(problem.statement_ja, "problem.statement_ja"),
    title_en: stringValue(problem.title_en, "problem.title_en"),
    statement_en: stringValue(problem.statement_en, "problem.statement_en"),
    input: stringValue(problem.input, "problem.input"),
    expected_output: stringValue(problem.expected_output, "problem.expected_output"),
    image: stringValue(problem.image, "problem.image"),
  };
};

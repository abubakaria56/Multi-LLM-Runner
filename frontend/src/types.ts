export type ModelRun = {
  prompt: string;
  response: string;
  error: string | null;
};
export type ApiResult = {
  count_prompts: number;
  results: Record<string, ModelRun[]>;
};

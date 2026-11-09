import axios from "axios";

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000" });
const KEY = "qmx_token";
export const getToken = () => sessionStorage.getItem(KEY);
export const setToken = (t: string | null) => (t ? sessionStorage.setItem(KEY, t) : sessionStorage.removeItem(KEY));

api.interceptors.request.use((c) => {
  const t = getToken();
  if (t) c.headers.Authorization = `Bearer ${t}`;
  return c;
});

export const errText = (e: unknown): string => {
  const d = (e as any)?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg).join("; ");
  return (e as Error)?.message ?? "Request failed";
};

export interface Dataset { dataset_id: number; name: string; target_column: string | null; row_count: number; column_count: number; duplicate_rows: number; uploaded_at: string; }
export interface Result { experiment_id: number; model_family: string; algorithm: string; accuracy: number; precision_score: number; recall: number; f1_score: number; roc_auc: number | null; train_seconds: number; backend_info: string; }
